"""AutoSE entry point: runs a LangGraph graph with a SQLite checkpointer.

    python autose/run.py build  --issue N --repo work --out out [--variant v] [--stop-after spec|design|test]
    python autose/run.py rework --issue N --repo work --out out --review out/review-1 --round 1
    python autose/run.py review --pr P   --repo work --out review --round 1

Checkpoints are saved in <out>/checkpoints.sqlite after every node. If a build job is re-run and the
previous attempt's artifact (with that file) is present, the run resumes from the last checkpoint:
the code written so far is restored from the `patch` in the state, then the graph continues.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import git, load_config, log, read_json, set_output, untrusted, write_json  # noqa: E402
from graph import build_graph, build_review_graph  # noqa: E402
from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: E402
from nodes import Ctx, prepare_repo  # noqa: E402
from review import ReviewNodes  # noqa: E402


def saver(out: Path, name: str = "checkpoints.sqlite") -> SqliteSaver:
    out.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(out / name, check_same_thread=False))


def config(thread: str, cfg: dict[str, Any]) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread}, "recursion_limit": 150,
            "max_concurrency": int(cfg["budgets"].get("max_parallel_workers", 3))}


def finish(app: Any, conf: dict[str, Any], out: Path, stop_after: str = "") -> int:
    values = dict(app.get_state(conf).values)
    if stop_after and values.get("status") == "running":
        values["status"] = f"stopped_after_{stop_after}"  # experiment run that ends early on purpose
    write_json(out / "state.json", values)
    status = values.get("status")
    log(f"run finished: status={status} stopped_at={values.get('stopped_at')} tokens={values.get('tokens')}")
    if values.get("pr"):
        set_output("pr", str(values["pr"]))
    if values.get("branch"):
        set_output("branch", values["branch"])
    set_output("status", str(status))
    return 1 if status == "failed" else 0


def cmd_build(a: argparse.Namespace) -> int:
    cfg = load_config(a.variant)
    repo, out = Path(a.repo).resolve(), Path(a.out).resolve()
    ctx = Ctx(cfg, repo, out, "build", stop_after=a.stop_after)
    prepare_repo(ctx)
    app = build_graph(ctx, saver(out))
    conf = config(f"build-issue{a.issue}-{a.variant}", cfg)
    snap = app.get_state(conf)
    if snap.values and snap.next:
        # resume after a crash / re-run: restore the code written so far, then continue at the pending node
        v = snap.values
        log(f"resuming from checkpoint; next={snap.next}")
        git(repo, "checkout", "-q", "-B", v["branch"], v["base"])
        if v.get("patch"):
            patch = out / "resume.patch"
            patch.write_text(v["patch"] + "\n")
            git(repo, "apply", "--index", str(patch))
            git(repo, "commit", "-q", "-m", f"autose(#{a.issue}): restore work from checkpoint")
        app.invoke(None, conf)
        return finish(app, conf, out, a.stop_after)
    else:
        if snap.values:
            conf = config(f"build-issue{a.issue}-{a.variant}-{os.environ.get('GITHUB_RUN_ATTEMPT', 'x')}", cfg)
        app.invoke({"issue": int(a.issue), "variant": a.variant, "mode": "build", "round": "", "tokens": 0,
                    "events": [], "results": []}, conf)
    return finish(app, conf, out, a.stop_after)


def cmd_rework(a: argparse.Namespace) -> int:
    cfg = load_config(a.variant)
    repo, out = Path(a.repo).resolve(), Path(a.out).resolve()
    ctx = Ctx(cfg, repo, out, "rework", rnd=a.round)
    prepare_repo(ctx)
    cp = saver(out)
    app = build_graph(ctx, cp)
    prev = dict(app.get_state(config(f"build-issue{a.issue}-{a.variant}", cfg)).values) or read_json(
        out / "state.json", {})
    verdict = read_json(Path(a.review) / "verdict.json", {})
    review_md = (Path(a.review) / "review.md").read_text() if (Path(a.review) / "review.md").exists() else ""
    route = verdict.get("route", "code")
    text = (f"An independent reviewer requested changes (round {a.round}, route: {route}). "
            "Address every finding:\n" + untrusted("untrusted_review", review_md))
    stages = {k: dict(v) for k, v in (prev.get("stages") or {}).items()}
    for s in (["design"] if route == "approach" else []) + ["implement", "test", "release"]:
        stages.setdefault(s, {"status": "pending", "attempts": 0, "notes": []})["status"] = "rework"
    init = {k: v for k, v in prev.items() if k not in ("events", "results", "tokens")}
    init.update({"mode": "rework", "round": a.round, "review": {"route": route, "round": a.round},
                 "stages": stages, "attempts": {}, "loops": {}, "need_tests": True, "allow_no_change": True,
                 "status": "running", "stopped_at": "", "stop_reason": "", "weak": [], "tokens": 0,
                 "events": [], "results": [],
                 "feedback": {"design": text, "implement": text, "tests": text}})
    conf = config(f"rework{a.round}-issue{a.issue}-{a.variant}", cfg)
    app.invoke(init, conf)
    return finish(app, conf, out)


def cmd_review(a: argparse.Namespace) -> int:
    cfg = load_config(a.variant)
    repo, out = Path(a.repo).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    app = build_review_graph(ReviewNodes(cfg, repo, out), saver(out))
    conf = config(f"review{a.round}-pr{a.pr}-{a.variant}", cfg)
    app.invoke({"pr": int(a.pr), "round": a.round, "variant": a.variant, "tokens": 0}, conf)
    v = app.get_state(conf).values.get("verdict") or {}
    log(f"verdict: {json.dumps({k: v.get(k) for k in ('verdict', 'route')})}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "rework", "review"])
    ap.add_argument("--issue", default="")
    ap.add_argument("--pr", default="")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="out")
    ap.add_argument("--variant", default=os.environ.get("AUTOSE_VARIANT") or "baseline")
    ap.add_argument("--stop-after", default="", choices=["", "spec", "design", "test"])
    ap.add_argument("--review", default="")
    ap.add_argument("--round", default="1")
    a = ap.parse_args()
    return {"build": cmd_build, "rework": cmd_rework, "review": cmd_review}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
