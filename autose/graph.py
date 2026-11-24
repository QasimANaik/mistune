"""The AutoSE LangGraph graphs (see architecture/views/autose-workflow.drawio).

Build graph (jobs `build` and `rework`):
  START -> intake -> (build: understand | rework: design or implement)
  understand -(testable)-> design | -(retry)-> understand | -(not testable)-> clarify -> END
  design -(ok)-> implement | -(retry)-> design | -(fail)-> stop
  implement -(ok, tests needed)-> orchestrator | -(ok, tests exist)-> merge | -(retry)-> implement | -(fail)-> stop
  orchestrator -Send x N-> criterion_worker (+ e2e_worker when 2+ workers) -> merge   (parallel, own worktrees)
  merge -(pass)-> release | -(AC uncovered, once)-> orchestrator (weak criteria only)
        -(tests fail)-> implement (<=2) -> design (<=1) -> stop
  release -(PR open, CI green)-> END | -(CI fails, once)-> implement | -> stop
  stop -> END

Review graph (jobs `review-1`, `review-2`; read-only token, different model):
  START -> intake_pr -> reviewer -> judge -(invalid, once)-> reviewer | -> render -> END

Every routing function reads check results from the state; no agent decides where the run goes.
"""

import time
from typing import Any, Callable

from common import log
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from nodes import Ctx, Nodes, StopRun
from state import AutoSEState, ReviewState
from workers import build_worker_graph


def _wrap(name: str, fn: Callable[[Any], dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """Log each node; a StopRun (budget/limit) becomes a stop instead of a crash."""

    def wrapped(state: Any) -> dict[str, Any]:
        t0 = time.time()
        log(f"> {name}")
        try:
            out = dict(fn(state) or {})
        except StopRun as e:
            out = {"status": "failed", "stopped_at": e.stage, "stop_reason": e.reason, "last_ok": False}
        log(f"< {name} ({time.time() - t0:.0f}s){' status=' + out['status'] if out.get('status') else ''}")
        return out

    return wrapped


def build_graph(ctx: Ctx, checkpointer: Any = None) -> Any:
    n = Nodes(ctx)
    r = ctx.cfg["retries"]
    worker = build_worker_graph(ctx)

    def failed(s: AutoSEState) -> bool:
        return s.get("status") == "failed"

    def tries(s: AutoSEState, stage: str) -> int:
        return int((s.get("attempts") or {}).get(stage, 0))

    def loops(s: AutoSEState, key: str) -> int:
        return int((s.get("loops") or {}).get(key, 0))

    # -------------------------------------------------- worker nodes (only the WorkerResult reaches the main state)
    def run_worker(payload: dict[str, Any]) -> dict[str, Any]:
        item = payload["item"]
        try:
            out = worker.invoke(payload, {"recursion_limit": 25})
            res = out["result"]
        except Exception as e:  # noqa: BLE001 - one failed worker must not stop the others
            log(f"worker {item['id']} crashed: {type(e).__name__}: {e}")
            res = {"work_item_id": item["id"], "kind": item["kind"], "criterion_ids": item["criterion_ids"],
                   "status": "error", "test_file": item["test_file"], "content": "", "tests": [], "covered": {},
                   "pytest": "", "reasons": [f"{type(e).__name__}: {str(e)[:300]}"], "tokens": 0, "tries": 0}
        return {"results": [res], "tokens": int(res.get("tokens") or 0),
                "events": [{"t": "", "stage": "test", "msg": f"worker {item['id']}: {res['status']}"}]}

    # -------------------------------------------------- routes
    def after_intake(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("mode") == "rework":
            return "design" if (s.get("review") or {}).get("route") == "approach" else "implement"
        return "understand"

    def after_understand(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("last_ok"):
            return END if ctx.stop_after == "spec" else "design"
        return "understand" if tries(s, "spec") <= r["spec"] else "clarify"

    def after_design(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("last_ok"):
            return END if ctx.stop_after == "design" else "implement"
        return "design" if tries(s, "design") <= r["design"] else "stop"

    def after_implement(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("last_ok"):
            return "orchestrator" if s.get("need_tests", True) else "merge"
        return "implement" if tries(s, "implement") <= r["build"] else "stop"

    def send_workers(s: AutoSEState) -> Any:
        if failed(s):
            return "stop"
        diff = ""
        p = ctx.out / "diff.patch"
        if p.exists():
            diff = p.read_text()
        fb = (s.get("feedback") or {}).get("tests", "")
        if not s.get("work_items"):
            return "stop"  # nothing to test: an empty Send list would end the graph silently
        return [Send("criterion_worker" if it["kind"] == "criterion" else "e2e_worker",
                     {"item": it, "issue": s["issue"], "diff": diff, "feedback": fb})
                for it in s.get("work_items") or []]

    def after_merge(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("last_ok"):
            return END if ctx.stop_after == "test" else "release"
        if s.get("weak") and loops(s, "cover") < r["tests_cover"]:
            return "loop_cover"
        if (s.get("redo_items") and not s.get("impl_changed", True)
                and loops(s, "dispute") < r.get("test_dispute", 1)):
            return "loop_dispute"  # only new tests fail and the implementer kept its code: re-check the tests
        if loops(s, "impl_after_test") < r["implement_after_test_fail"]:
            return "loop_implement"
        if loops(s, "redesign") < r["redesign"]:
            return "loop_redesign"
        return "stop"

    def after_release(s: AutoSEState) -> str:
        if failed(s):
            return "stop"
        if s.get("status") == "pr_open":
            return END
        return "loop_ci" if loops(s, "ci") < r["ci"] else "stop"

    # -------------------------------------------------- loop-back bookkeeping nodes (code)
    def loop(key: str, reset: str, **extra: Any) -> Callable[[AutoSEState], dict[str, Any]]:
        def node(s: AutoSEState) -> dict[str, Any]:
            lp = dict(s.get("loops") or {})
            lp[key] = lp.get(key, 0) + 1
            at = dict(s.get("attempts") or {})
            at[reset] = 0
            log(f"loop-back {key} #{lp[key]} -> {reset}")
            return {"loops": lp, "attempts": at, "last_ok": False, **extra,
                    "events": [{"t": "", "stage": "control", "msg": f"loop-back {key} #{lp[key]} -> {reset}"}]}
        return node

    g = StateGraph(AutoSEState)
    for name in ("intake", "understand", "clarify", "design", "implement", "orchestrator", "merge", "release", "stop"):
        g.add_node(name, _wrap(name, getattr(n, name)))
    g.add_node("criterion_worker", run_worker)
    g.add_node("e2e_worker", run_worker)
    g.add_node("loop_cover", loop("cover", "test"))
    g.add_node("loop_dispute", loop("dispute", "test"))
    g.add_node("loop_implement", loop("impl_after_test", "implement", need_tests=False))
    g.add_node("loop_redesign", loop("redesign", "design", need_tests=False))
    g.add_node("loop_ci", loop("ci", "implement", need_tests=False))

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", after_intake, ["understand", "design", "implement", "stop"])
    g.add_conditional_edges("understand", after_understand, ["design", "understand", "clarify", "stop", END])
    g.add_edge("clarify", END)
    g.add_conditional_edges("design", after_design, ["implement", "design", "stop", END])
    g.add_conditional_edges("implement", after_implement, ["orchestrator", "merge", "implement", "stop"])
    g.add_conditional_edges("orchestrator", send_workers, ["criterion_worker", "e2e_worker", "stop"])
    g.add_edge("criterion_worker", "merge")  # merge waits for every worker
    g.add_edge("e2e_worker", "merge")
    g.add_conditional_edges("merge", after_merge,
                            ["release", "loop_cover", "loop_dispute", "loop_implement", "loop_redesign", "stop", END])
    g.add_edge("loop_cover", "orchestrator")
    g.add_edge("loop_dispute", "orchestrator")
    g.add_edge("loop_implement", "implement")
    g.add_edge("loop_redesign", "design")
    g.add_conditional_edges("release", after_release, ["loop_ci", "stop", END])
    g.add_edge("loop_ci", "implement")
    g.add_edge("stop", END)
    return g.compile(checkpointer=checkpointer)


def build_review_graph(nodes: Any, checkpointer: Any = None) -> Any:
    """nodes: an object with intake_pr, reviewer, judge, render methods (see review.py)."""

    def after_judge(s: ReviewState) -> str:
        return "reviewer" if s.get("raw") is None and int(s.get("attempt") or 0) < 2 else "render"

    g = StateGraph(ReviewState)
    for name in ("intake_pr", "reviewer", "judge", "render"):
        g.add_node(name, _wrap(name, getattr(nodes, name)))
    g.add_edge(START, "intake_pr")
    g.add_edge("intake_pr", "reviewer")
    g.add_edge("reviewer", "judge")
    g.add_conditional_edges("judge", after_judge, ["reviewer", "render"])
    g.add_edge("render", END)
    return g.compile(checkpointer=checkpointer)
