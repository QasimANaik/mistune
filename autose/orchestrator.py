"""AutoSE orchestrator: a deterministic state machine for stages 1-5 (and the rework round).

    python3 autose/orchestrator.py build  --issue N --repo work --out out [--variant v] [--stop-after stage]
    python3 autose/orchestrator.py rework --issue N --repo work --out out --review out/review-1 --round 1

Every loop-back is decided here from check results; agents never decide pass/fail or what runs next.
Only this process holds GH_TOKEN; agents run with a stripped environment (see agent.py).
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import AgentResult, run_agent  # noqa: E402
from checks import Check, ac_coverage, check_build, check_design, check_spec, restrict_changes, run_pytest  # noqa: E402
from common import gh, git, load_config, log, prompt, read_json, run_url, set_output, untrusted, write, write_json  # noqa: E402

BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
STAGES = ["spec", "design", "implement", "test", "release"]


class Stop(Exception):
    """A stage could not pass its check within its budget: explain in the artifact and stop."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"{stage}: {reason}")
        self.stage, self.reason = stage, reason


class Run:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.cfg = load_config(args.variant)
        self.repo = Path(args.repo).resolve()
        self.out = Path(args.out).resolve()
        self.work = self.repo / ".autose-work"
        self.n = int(args.issue)
        prev = read_json(self.out / "state.json", {}) if args.cmd == "rework" else {}
        self.state: dict[str, Any] = prev or {
            "issue": self.n,
            "variant": self.cfg["variant_name"],
            "models": {"builder": self.cfg["models"]["builder"], "reviewer": self.cfg["v"]["reviewer_model"]},
            "stages": {s: {"status": "pending", "attempts": 0, "notes": []} for s in STAGES},
            "tokens": 0,
            "events": [],
            "runs": [],
        }
        self.state["runs"].append({"cmd": args.cmd, "url": run_url(), "started": _now()})
        self.calls = 0

    # ------------------------------------------------------------ bookkeeping
    def event(self, stage: str, msg: str) -> None:
        log(f"[{stage}] {msg}")
        self.state["events"].append({"t": _now(), "stage": stage, "msg": msg})
        self.save()

    def mark(self, stage: str, status: str, note: str = "") -> None:
        st = self.state["stages"].setdefault(stage, {"status": "pending", "attempts": 0, "notes": []})
        st["status"] = status
        if note:
            st["notes"].append(note)
        self.save()

    def bump(self, stage: str) -> int:
        st = self.state["stages"][stage]
        st["attempts"] += 1
        self.save()
        return int(st["attempts"])

    def save(self) -> None:
        write_json(self.out / "state.json", self.state)

    def agent(self, stage: str, text: str, skills: tuple[str, ...] = ()) -> AgentResult:
        limit = self.cfg["budgets"]["max_run_tokens"]
        if self.state["tokens"] >= limit:
            raise Stop(stage, f"token budget exhausted ({self.state['tokens']} >= {limit})")
        self.calls += 1
        name = f"{self.args.cmd}{getattr(self.args, 'round', '') or ''}-{self.calls:02d}-{stage}"
        res = run_agent(
            name, text, self.cfg["models"]["builder"], "builder.toml", self.repo, self.out, self.cfg,
            skills=skills, fallback_model=self.cfg["models"]["builder_fallback"],
        )
        self.state["tokens"] += res.total_tokens
        self.event(stage, f"agent {name}: exit={res.exit_code} tools={res.tool_calls} tokens={res.total_tokens}")
        if res.timed_out:
            self.mark(stage, "running", f"agent call {name} hit the {self.cfg['budgets']['agent_timeout_s']}s timeout")
        return res

    def commit(self, msg: str) -> bool:
        git(self.repo, "add", "-A", "--", "src", "tests")
        if not git(self.repo, "diff", "--cached", "--name-only"):
            return False
        git(self.repo, "commit", "-q", "-m", f"autose(#{self.n}): {msg}")
        return True

    def artifact(self, name: str, text: str) -> None:
        write(self.out / name, text)

    # ------------------------------------------------------------ setup
    def prepare(self) -> None:
        git(self.repo, "config", "user.name", BOT_NAME)
        git(self.repo, "config", "user.email", BOT_EMAIL)
        excl = self.repo / ".git" / "info" / "exclude"
        excl.parent.mkdir(parents=True, exist_ok=True)
        with open(excl, "a") as f:
            f.write("\n.autose-work/\n.venv/\n")
        self.work.mkdir(exist_ok=True)
        arch = self.repo / "ARCHITECTURE.md"
        if not self.cfg["v"]["use_architecture_doc"] and arch.exists():
            # experiment variant: hide the doc from every agent without recording a deletion in git
            git(self.repo, "update-index", "--skip-worktree", "ARCHITECTURE.md")
            arch.unlink()
            self.event("setup", "variant hides ARCHITECTURE.md from the agents")

    def issue_block(self) -> str:
        data = self.state.get("issue_data")
        if not data:
            p = gh(["issue", "view", str(self.n), "--json", "number,title,body,url"])
            data = json.loads(p.stdout)
            self.state["issue_data"] = data
            self.save()
        return untrusted("untrusted_issue", data.get("body") or "", number=str(self.n), title=data.get("title", ""))

    @property
    def branch(self) -> str:
        v = self.cfg["variant_name"]
        return f"autose/issue-{self.n}" + ("" if v == "baseline" else f"-{v}")

    # ------------------------------------------------------------ stage 1
    def stage_spec(self) -> None:
        self.mark("spec", "running")
        feedback = ""
        spec_dir = self.work / "spec"
        for attempt in range(1 + self.cfg["retries"]["spec"]):
            self.bump("spec")
            self.agent("spec", prompt("spec.md", N=str(self.n), ISSUE=self.issue_block(), FEEDBACK=feedback),
                       skills=("requirements-spec",))
            restrict_changes(self.repo, ())  # spec stage may not touch code
            chk, acs, srs = check_spec(spec_dir)
            self._write_spec_artifact(spec_dir, chk)
            if chk.ok:
                self.state["acs"] = acs
                self.mark("spec", "passed", f"{len(acs)} acceptance criteria, all testable")
                return
            self.event("spec", f"check failed (attempt {attempt + 1}): {chk.reasons}")
            feedback = "Your previous attempt FAILED the pipeline's spec check. Fix these problems:\n" + "\n".join(
                f"- {r}" for r in chk.reasons
            )
        raise Stop("spec", "acceptance criteria are not all testable: " + "; ".join(chk.reasons))

    def _write_spec_artifact(self, spec_dir: Path, chk: Check) -> None:
        parts = [f"# spec.md (issue #{self.n})\n", "## Stage 1 check (orchestrator)\n", chk.text()]
        for f in sorted(spec_dir.glob("*.md")):
            parts.append(f"\n---\n\n<!-- {f.name} -->\n\n{f.read_text()}")
            write(self.out / "spec" / f.name, f.read_text())
        self.artifact("spec.md", "\n".join(parts))

    def acs_text(self) -> str:
        return "\n".join(f"- {k}: {v}" for k, v in self.state.get("acs", {}).items())

    def srs_text(self) -> str:
        files = sorted((self.out / "spec").glob("SRS-*.md"))
        return files[-1].read_text() if files else self.acs_text()

    # ------------------------------------------------------------ stage 2
    def stage_design(self, extra: str = "") -> None:
        self.mark("design", "running")
        feedback = extra
        hint = (
            "Read `ARCHITECTURE.md` first: it describes the components, extension points and rules of this codebase."
            if self.cfg["v"]["use_architecture_doc"]
            else ""
        )
        design = self.work / "design.md"
        for attempt in range(1 + self.cfg["retries"]["design"]):
            self.bump("design")
            design.unlink(missing_ok=True)
            self.agent("design", prompt("design.md", ARCH_HINT=hint, SPEC=self.srs_text(), FEEDBACK=feedback))
            restrict_changes(self.repo, ())  # design stage may not change code
            chk = check_design(design, self.repo)
            body = design.read_text() if design.exists() else "(not written)"
            self.artifact("design.md", f"{body}\n\n---\n## Stage 2 check (orchestrator)\n\n{chk.text()}")
            if chk.ok:
                self.mark("design", "passed")
                return
            self.event("design", f"check failed (attempt {attempt + 1}): {chk.reasons}")
            feedback = (extra + "\n\n" if extra else "") + (
                "Your previous design FAILED the pipeline's design check:\n" + "\n".join(f"- {r}" for r in chk.reasons)
            )
        raise Stop("design", "the plan does not name existing files and functions: " + "; ".join(chk.reasons))

    def design_text(self) -> str:
        p = self.out / "design.md"
        return p.read_text().split("\n---\n## Stage 2 check")[0] if p.exists() else ""

    # ------------------------------------------------------------ stage 3
    def stage_implement(self, feedback: str, allow_no_change: bool = False) -> AgentResult:
        self.mark("implement", "running")
        fb = feedback
        for attempt in range(1 + self.cfg["retries"]["build"]):
            self.bump("implement")
            res = self.agent("implement", prompt("implement.md", DESIGN=self.design_text(), ACS=self.acs_text(),
                                                 FEEDBACK=fb))
            reverted = restrict_changes(self.repo, ("src/",))
            if reverted:
                self.event("implement", f"reverted changes outside src/: {reverted}")
            changed = bool(git(self.repo, "status", "--porcelain", "--", "src"))
            if not changed and not allow_no_change:
                chk = Check(False, ["the implementation made no change under src/"])
            else:
                chk = check_build(self.repo)
            diff = git(self.repo, "diff", self.state["base"], "--", "src")
            work_diff = git(self.repo, "diff", "HEAD", "--", "src")
            self.artifact("diff.patch", (diff + "\n" + work_diff) if work_diff else diff)
            self.artifact("implement_check.md", f"# Stage 3 check (attempt {attempt + 1})\n\n{chk.text()}")
            if chk.ok:
                self.commit(f"implementation (attempt {self.state['stages']['implement']['attempts']})")
                self.artifact("diff.patch", git(self.repo, "diff", self.state["base"], "--", "src") + "\n")
                self.mark("implement", "passed")
                return res
            self.event("implement", f"build check failed: {chk.reasons}")
            fb = feedback + "\n\nYour previous attempt FAILED the build check:\n" + chk.text()
        raise Stop("implement", "the code does not build/lint/type-check: " + "; ".join(chk.reasons))

    # ------------------------------------------------------------ stage 4
    def stage_write_tests(self, feedback: str) -> None:
        self.mark("test", "running")
        diff = git(self.repo, "diff", self.state["base"], "--", "src")
        self.agent("test", prompt("tests.md", N=str(self.n), ACS=self.acs_text(), DIFF=diff[:30000], FEEDBACK=feedback))
        reverted = restrict_changes(self.repo, ("tests/",))
        if reverted:
            self.event("test", f"reverted changes outside tests/: {reverted}")
        self.commit("tests for acceptance criteria")

    def check_tests(self) -> tuple[Check, list[str]]:
        cover, tests = ac_coverage(self.repo, self.state["base"], self.state.get("acs", {}))
        missing = [a for a, t in cover.items() if not t]
        ok, summary, output = run_pytest(self.repo)
        reasons = []
        if not tests:
            reasons.append("no new test functions were added")
        if missing:
            reasons.append(f"acceptance criteria without a test: {missing}")
        if not ok:
            reasons.append(f"test suite failed: {summary}")
        rows = "\n".join(f"| {a} | {'<br>'.join(t) or '**MISSING**'} |" for a, t in cover.items())
        report = (
            f"# test_report.md (issue #{self.n})\n\n**Full suite:** {'PASS' if ok else 'FAIL'}: `{summary}`\n\n"
            f"**New/changed test functions:** {len(tests)}\n\n| AC | Tests |\n|---|---|\n{rows}\n\n"
            f"## Stage 4 check (orchestrator)\n\n{Check(not reasons, reasons).text()}\n"
            + ("" if ok else f"\n## Failing output\n\n```\n{output[-5000:]}\n```\n")
        )
        self.artifact("test_report.md", report)
        return Check(not reasons, reasons, "" if ok else output), missing

    def implement_and_test(self, feedback: str = "", rewrite_tests: bool = True, allow_no_change: bool = False) -> None:
        """Stages 3 and 4 with the loop-backs: 4 -> 3 (tests fail), 4 -> 2 (still failing), 4 -> 4 (AC not covered)."""
        r = self.cfg["retries"]
        impl_fb, test_fb = feedback, feedback
        impl_loops = redesigns = cover_retries = 0
        need_impl, need_tests = True, rewrite_tests
        while True:
            if need_impl:
                res = self.stage_implement(impl_fb, allow_no_change=allow_no_change)
                allow_no_change = True  # later loop-backs may legitimately leave src/ unchanged
                disputes = re.findall(r"^DISPUTE:\s*(.+)$", res.response, re.M)
                if disputes and cover_retries < r["tests_cover"]:
                    cover_retries += 1
                    need_tests = True
                    test_fb = "The implementer disputes these tests; re-check them against the ACs:\n" + "\n".join(
                        f"- {d}" for d in disputes
                    )
            if need_tests:
                self.bump("test")
                self.stage_write_tests(test_fb)
            need_impl, need_tests = False, False
            chk, missing = self.check_tests()
            if chk.ok:
                self.mark("test", "passed")
                return
            suite_failed = any(x.startswith("test suite failed") for x in chk.reasons)
            if not suite_failed and cover_retries < r["tests_cover"]:
                cover_retries += 1
                need_tests = True
                test_fb = "Your previous tests FAILED the coverage check:\n" + "\n".join(f"- {x}" for x in chk.reasons)
                self.event("test", "AC coverage incomplete -> rewrite tests")
                continue
            if not suite_failed:
                raise Stop("test", "; ".join(chk.reasons))
            fail_fb = "Tests are failing. Make them pass by fixing the implementation (tests cannot be edited):\n" + (
                f"```\n{chk.details[-5000:]}\n```"
            )
            if impl_loops < r["implement_after_test_fail"]:
                impl_loops += 1
                self.event("test", f"tests fail -> back to stage 3 (loop {impl_loops})")
                need_impl, impl_fb = True, fail_fb
                continue
            if redesigns < r["redesign"]:
                redesigns += 1
                impl_loops = 0
                self.event("test", "tests still fail -> back to stage 2 (redesign)")
                self.stage_design("The previous design led to an implementation whose tests keep failing:\n" + fail_fb)
                need_impl, impl_fb = True, fail_fb
                continue
            raise Stop("test", "tests still fail after all retries: " + "; ".join(chk.reasons))

    # ------------------------------------------------------------ stage 5
    def stage_release(self, force: bool) -> None:
        self.mark("release", "running")
        for attempt in range(1 + self.cfg["retries"]["ci"]):
            self.bump("release")
            sha = git(self.repo, "rev-parse", "HEAD")
            push = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", "push", "origin",
                    f"HEAD:refs/heads/{self.branch}"]
            git(self.repo, *(push + (["--force"] if force else [])))
            force = False
            pr = self.ensure_pr()
            ok, info = self.wait_ci(sha)
            self.state["ci"] = info
            if ok:
                self.mark("release", "passed", f"PR #{pr} open, CI green ({info.get('url')})")
                return
            self.event("release", f"CI failed: {info.get('url')}")
            if attempt < self.cfg["retries"]["ci"]:
                self.implement_and_test(
                    "The pull request's CI (tests.yml: ruff, mypy, docs, pytest) FAILED:\n```\n"
                    + str(info.get("log", ""))[-5000:] + "\n```",
                    rewrite_tests=False, allow_no_change=False,
                )
        raise Stop("release", f"CI does not pass: {self.state.get('ci', {}).get('url')}")

    def ensure_pr(self) -> int:
        title = f"AutoSE: {self.state['issue_data']['title']} (#{self.n})"
        self.artifact("pr.md", self.pr_body())
        p = gh(["pr", "list", "--head", self.branch, "--state", "open", "--json", "number,url"])
        existing = json.loads(p.stdout)
        if existing:
            num = int(existing[0]["number"])
            gh(["pr", "edit", str(num), "--body-file", str(self.out / "pr.md")])
        else:
            gh(["pr", "create", "--base", "main", "--head", self.branch, "--title", title, "--body-file",
                str(self.out / "pr.md")])
            num = int(json.loads(gh(["pr", "view", self.branch, "--json", "number"]).stdout)["number"])
        gh(["pr", "edit", str(num), "--add-label", "autose"], check=False)
        state = json.loads(gh(["pr", "view", str(num), "--json", "state,url"]).stdout)
        if state["state"] != "OPEN":
            raise Stop("release", f"PR #{num} is not open ({state['state']})")
        self.state["pr"], self.state["pr_url"], self.state["branch"] = num, state["url"], self.branch
        self.artifact("pr.md", self.pr_body() + f"\n\nPR: {state['url']}\n")
        self.save()
        return num

    def pr_body(self) -> str:
        design = self.design_text()
        summary = re.search(r"##\s*Summary\s*(.*?)(?=\n##\s|\Z)", design, re.S)
        rows = "\n".join(
            f"| {s} | {d['status']} | {d['attempts']} |" for s, d in self.state["stages"].items() if s != "review"
        )
        tr = (self.out / "test_report.md").read_text() if (self.out / "test_report.md").exists() else ""
        acs = re.search(r"\| AC \| Tests \|.*?(?=\n\n)", tr, re.S)
        return (
            f"Fixes #{self.n}\n\n## Summary\n{summary.group(1).strip() if summary else '(see design.md)'}\n\n"
            f"## Acceptance criteria → tests\n{acs.group(0) if acs else '(see test_report.md)'}\n\n"
            f"## Stage checks\n| Stage | Status | Attempts |\n|---|---|---|\n{rows}\n\n"
            f"Artifacts (spec.md, design.md, diff.patch, test_report.md, transcripts): {run_url()}\n\n"
            f"Variant: `{self.cfg['variant_name']}` · builder model: `{self.cfg['models']['builder']}`\n\n"
            "_Generated by the AutoSE workflow. It will be reviewed by an independent reviewer agent; "
            "a human decides whether to merge._\n"
        )

    def wait_ci(self, sha: str) -> tuple[bool, dict[str, Any]]:
        gh(["workflow", "run", "tests.yml", "--ref", self.branch])
        deadline = time.time() + self.cfg["budgets"]["ci_timeout_s"]
        run: dict[str, Any] = {}
        while time.time() < deadline:
            time.sleep(20)
            p = gh(["run", "list", "--workflow", "tests.yml", "--branch", self.branch, "--event", "workflow_dispatch",
                    "--json", "databaseId,headSha,status,conclusion,url", "--limit", "10"], check=False)
            runs = [r for r in json.loads(p.stdout or "[]") if r.get("headSha") == sha]
            if runs:
                run = runs[0]
                if run["status"] == "completed":
                    info = {"url": run["url"], "conclusion": run["conclusion"]}
                    if run["conclusion"] != "success":
                        logp = gh(["run", "view", str(run["databaseId"]), "--log-failed"], check=False)
                        info["log"] = logp.stdout[-8000:]
                    return run["conclusion"] == "success", info
        return False, {"url": run.get("url"), "conclusion": "timeout"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stop(run: Run, e: Stop) -> int:
    run.mark(e.stage, "failed", e.reason)
    name = {"spec": "spec.md", "design": "design.md", "implement": "implement_check.md",
            "test": "test_report.md", "release": "pr.md"}[e.stage]
    path = run.out / name
    prev = path.read_text() if path.exists() else ""
    write(path, prev + f"\n\n## Why this stage stopped\n\n{e.reason}\n\nRun: {run_url()}\n")
    run.state["result"] = "failed"
    run.state["stopped_at"] = e.stage
    run.save()
    log(f"STOP at {e.stage}: {e.reason}")
    return 1


def cmd_build(args: argparse.Namespace) -> int:
    run = Run(args)
    try:
        run.prepare()
        run.state["base"] = git(run.repo, "rev-parse", "HEAD")
        git(run.repo, "checkout", "-q", "-B", run.branch)
        run.stage_spec()
        if args.stop_after == "spec":
            return 0
        run.stage_design()
        if args.stop_after == "design":
            return 0
        run.implement_and_test()
        if args.stop_after == "test":
            return 0
        run.stage_release(force=True)
        run.state["result"] = "pr_open"
        set_output("pr", str(run.state["pr"]))
        set_output("branch", run.branch)
        return 0
    except Stop as e:
        return _stop(run, e)
    finally:
        run.save()


def cmd_rework(args: argparse.Namespace) -> int:
    run = Run(args)
    verdict = read_json(Path(args.review) / "verdict.json", {})
    route = verdict.get("route", "code")
    findings = (Path(args.review) / "review.md").read_text() if (Path(args.review) / "review.md").exists() else ""
    fb = (
        f"An independent reviewer requested changes (round {args.round}, route: {route}). Address every finding:\n"
        + untrusted("untrusted_review", findings)
    )
    try:
        run.prepare()
        run.state["base"] = git(run.repo, "merge-base", "origin/main", "HEAD")
        run.event("rework", f"round {args.round}: route={route}")
        for s in ("design", "implement", "test", "release") if route == "approach" else ("implement", "test", "release"):
            run.state["stages"][s]["status"] = "rework"
        if route == "approach":
            run.stage_design(fb)
        run.implement_and_test(fb, rewrite_tests=True, allow_no_change=True)
        run.stage_release(force=False)
        run.state["result"] = "pr_open"
        return 0
    except Stop as e:
        return _stop(run, e)
    finally:
        run.save()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "rework"])
    ap.add_argument("--issue", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", default="out")
    ap.add_argument("--variant", default=os.environ.get("AUTOSE_VARIANT") or "baseline")
    ap.add_argument("--stop-after", default="", choices=["", "spec", "design", "test"])
    ap.add_argument("--review", default="")
    ap.add_argument("--round", default="")
    return {"build": cmd_build, "rework": cmd_rework}[(a := ap.parse_args()).cmd](a)


if __name__ == "__main__":
    sys.exit(main())
