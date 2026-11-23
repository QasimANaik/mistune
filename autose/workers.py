"""Stage 4 test workers (LangGraph subgraphs), sent in parallel by the orchestrator node.

Each worker works in its OWN git worktree at the implementation commit, writes tests for its slice of
acceptance criteria into one file, runs that file, and returns a WorkerResult. Workers never see each
other; only the WorkerResult (file content, coverage, pytest summary, tokens) reaches the main graph.

    receive_slice -> agent -> check -(file missing / AC uncovered, once)-> agent
                                    \\-> return_result
"""

import ast
import itertools
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from agent import run_agent
from checks import AC_ID_RE, changed_paths
from common import git, log, prompt, sh
from langgraph.graph import END, START, StateGraph
from state import WorkerState

_names = itertools.count(1)
_git_lock = threading.Lock()  # parallel workers must not run `git worktree` at the same time


def build_worker_graph(ctx: Any) -> Any:
    repo: Path = ctx.repo

    def receive_slice(s: WorkerState) -> dict[str, Any]:
        wt = Path(tempfile.mkdtemp(prefix=f"autose-wt-{s['item']['id']}-"))
        wt.rmdir()
        with _git_lock:
            git(repo, "worktree", "add", "-q", "--detach", str(wt), "HEAD")
        (wt / ".venv").symlink_to(repo / ".venv")
        return {"worktree": str(wt), "tries": 0, "tokens": 0}

    def agent(s: WorkerState) -> dict[str, Any]:
        item = s["item"]
        acs = "\n".join(f"- {k}: {v}" for k, v in item["acs"].items())
        text = prompt(
            "test_worker.md" if item["kind"] == "criterion" else "e2e_worker.md",
            N=str(s["issue"]), FILE=item["test_file"], ACS=acs, DIFF=s["diff"][:30000],
            FEEDBACK=s.get("feedback", ""),
        )
        name = f"{ctx.cmd}{ctx.rnd}-w{next(_names):02d}-{item['id']}"
        res = run_agent(name, text, ctx.cfg["models"]["builder"], "builder.toml", Path(s["worktree"]), ctx.out,
                        ctx.cfg, fallback_model=ctx.cfg["models"]["builder_fallback"])
        return {"tries": s["tries"] + 1, "response": res.response[-2000:], "tokens": s["tokens"] + res.total_tokens}

    def check(s: WorkerState) -> dict[str, Any]:
        item, wt = s["item"], Path(s["worktree"])
        path = wt / item["test_file"]
        other = [p for p, _ in changed_paths(wt) if p != item["test_file"] and not p.startswith(".autose-work/")]
        reasons: list[str] = []
        covered: dict[str, list[str]] = {a: [] for a in item["criterion_ids"]}
        tests: list[str] = []
        summary, passed = "", False
        if not path.exists():
            reasons.append(f"{item['test_file']} was not written")
        else:
            src = path.read_text()
            try:
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                        tests.append(node.name)
                        seg = (ast.get_source_segment(src, node) or "").replace("_", "-").upper()
                        for a in AC_ID_RE.findall(seg):
                            if a in covered:
                                covered[a].append(node.name)
            except SyntaxError as e:
                reasons.append(f"syntax error in {item['test_file']}: {e}")
            missing = [a for a, t in covered.items() if not t]
            if missing:
                reasons.append(f"no test cites {missing}")
            p = sh([str(wt / ".venv" / "bin" / "python"), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--no-header", item["test_file"]], cwd=wt, check=False, timeout=600)
            summary = (p.stdout.strip().splitlines() or [""])[-1]
            passed = p.returncode == 0
        return {"check": {"reasons": reasons, "covered": covered, "tests": tests, "pytest": summary,
                          "passed": passed, "ignored_files": other}}

    def route(s: WorkerState) -> str:
        if s["check"]["reasons"] and s["tries"] < 2:
            return "agent"
        return "return_result"

    def retry_feedback(s: WorkerState) -> dict[str, Any]:
        return {"feedback": "Your previous attempt FAILED the worker check:\n" + "\n".join(
            f"- {r}" for r in s["check"]["reasons"])}

    def return_result(s: WorkerState) -> dict[str, Any]:
        item, wt = s["item"], Path(s["worktree"])
        path = wt / item["test_file"]
        content = path.read_text() if path.exists() else ""
        c = s["check"]
        status = "complete" if not c["reasons"] else ("incomplete" if content else "error")
        try:
            with _git_lock:
                git(repo, "worktree", "remove", "--force", str(wt), check=False)
        finally:
            shutil.rmtree(wt, ignore_errors=True)
        log(f"worker {item['id']}: {status}, tests={len(c['tests'])}, pytest='{c['pytest']}'")
        return {"result": {
            "work_item_id": item["id"], "kind": item["kind"], "criterion_ids": item["criterion_ids"],
            "status": status, "test_file": item["test_file"], "content": content, "tests": c["tests"],
            "covered": c["covered"], "pytest": c["pytest"], "passed_alone": c["passed"],
            "reasons": c["reasons"], "ignored_files": c["ignored_files"], "tries": s["tries"],
            "tokens": s["tokens"], "notes": s.get("response", "")[-600:],
        }}

    g = StateGraph(WorkerState)
    g.add_node("receive_slice", receive_slice)
    g.add_node("agent", agent)
    g.add_node("check", check)
    g.add_node("retry_feedback", retry_feedback)
    g.add_node("return_result", return_result)
    g.add_edge(START, "receive_slice")
    g.add_edge("receive_slice", "agent")
    g.add_edge("agent", "check")
    g.add_conditional_edges("check", route, {"agent": "retry_feedback", "return_result": "return_result"})
    g.add_edge("retry_feedback", "agent")
    g.add_edge("return_result", END)
    return g.compile()
