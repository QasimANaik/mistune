"""Stage 6: independent reviewer. Runs in its own read-only job, on the PR head checkout.

    python3 autose/reviewer.py --pr N --repo work --out out/review-1 --round 1 [--variant v]

Inputs are ONLY: the linked issue, the PR diff, and the checked-out code. This job never downloads
builder artifacts (spec, design, transcripts, test report) and has no write token.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import run_agent  # noqa: E402
from common import gh, load_config, log, prompt, untrusted, write, write_json  # noqa: E402

SEVERE = {"blocker", "major"}


def linked_issue(pr: dict[str, Any]) -> dict[str, Any]:
    m = re.search(r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)", pr.get("body") or "")
    if m:
        p = gh(["issue", "view", m.group(1), "--json", "number,title,body"], check=False)
        if p.returncode == 0:
            data: dict[str, Any] = json.loads(p.stdout)
            return data
    # no linked issue: the PR title + body is the only statement of intent
    return {"number": pr["number"], "title": pr.get("title", ""), "body": pr.get("body") or ""}


def parse_verdict(text: str) -> dict[str, Any] | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    candidates = blocks or re.findall(r"(\{\s*\"verdict\".*\})", text, re.S)
    for raw in reversed(candidates):
        try:
            v: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if v.get("verdict") in ("approve", "request_changes"):
            return v
    return None


def normalise(v: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Deterministic rules applied to the reviewer's output (recorded in review.md)."""
    notes: list[str] = []
    findings = [f for f in v.get("findings") or [] if isinstance(f, dict)]
    kept = [f for f in findings if str(f.get("evidence", "")).strip()]
    if len(kept) < len(findings):
        notes.append(f"{len(findings) - len(kept)} finding(s) without evidence were discarded (evidence rule).")
    severe = [f for f in kept if str(f.get("severity", "")).lower() in SEVERE]
    verdict = v.get("verdict")
    if verdict == "approve" and severe:
        verdict = "request_changes"
        notes.append("Verdict changed approve -> request_changes: the review lists blocker/major findings.")
    if verdict == "request_changes" and not severe:
        verdict = "approve"
        notes.append("Verdict changed request_changes -> approve: no evidenced blocker/major findings remain.")
    route = v.get("route") if v.get("route") in ("code", "approach") else "code"
    out = {
        "verdict": verdict,
        "route": route if verdict == "request_changes" else "none",
        "summary": v.get("summary", ""),
        "checked": v.get("checked") or [],
        "findings": kept,
        "discarded_findings": [f for f in findings if f not in kept],
    }
    return out, notes


def render(v: dict[str, Any], notes: list[str], model: str, rnd: str, pr: int, variant: str) -> str:
    icon = "✅ APPROVE" if v["verdict"] == "approve" else ("❌ REQUEST CHANGES" if v["verdict"] else "⚠️ ERROR")
    rows = "\n".join(
        f"| {f.get('severity', '')} | `{f.get('file', '')}:{f.get('line', '')}` | {f.get('problem', '')} | "
        f"{str(f.get('evidence', '')).replace(chr(10), ' ')[:400]} | {f.get('suggestion', '')} |"
        for f in v.get("findings", [])
    )
    checked = "\n".join(f"- {c}" for c in v.get("checked", [])) or "- (nothing listed)"
    return (
        f"## AutoSE independent review, round {rnd}: {icon}\n\n"
        f"**Route:** `{v.get('route')}` · **Reviewer model:** `{model}` · **Variant:** `{variant}` · PR #{pr}\n\n"
        f"{v.get('summary', '')}\n\n### What the reviewer checked\n{checked}\n\n"
        + (f"### Findings\n| Severity | Where | Problem | Evidence | Suggestion |\n|---|---|---|---|---|\n{rows}\n\n"
           if rows else "### Findings\nNone.\n\n")
        + ("### Pipeline rules applied\n" + "\n".join(f"- {n}" for n in notes) + "\n\n" if notes else "")
        + "_The reviewer saw only the issue, the diff and the PR-head checkout. It cannot push. "
        "A human decides whether to merge._\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--out", required=True)
    ap.add_argument("--round", default="1")
    ap.add_argument("--variant", default=os.environ.get("AUTOSE_VARIANT") or "baseline")
    a = ap.parse_args()
    cfg = load_config(a.variant)
    repo, out = Path(a.repo).resolve(), Path(a.out).resolve()
    pr = json.loads(gh(["pr", "view", a.pr, "--json", "number,title,body,headRefOid"]).stdout)
    issue = linked_issue(pr)
    diff = gh(["pr", "diff", a.pr]).stdout
    model = cfg["v"]["reviewer_model"]
    feedback = ""
    verdict = None
    res = None
    for attempt in range(2):
        text = prompt(
            cfg["v"]["reviewer_prompt"],
            ISSUE=untrusted("untrusted_issue", issue.get("body", ""), number=str(issue.get("number")),
                            title=issue.get("title", "")),
            DIFF=diff[:60000],
            FEEDBACK=feedback,
        )
        res = run_agent(f"review{a.round}-{attempt + 1}", text, model, cfg["v"]["reviewer_policy"], repo, out, cfg,
                        fallback_model=cfg["models"]["reviewer_fallback"])
        verdict = parse_verdict(res.response)
        if verdict and (verdict["verdict"] != "approve" or verdict.get("checked")):
            break
        feedback = ("Your previous answer did not end with a valid JSON verdict, or approved without listing "
                    "what you checked. Do the review and end with the required JSON block.")
    notes: list[str] = []
    if verdict is None:
        final = {"verdict": "error", "route": "none", "summary": "The reviewer did not produce a valid verdict.",
                 "checked": [], "findings": []}
    else:
        final, notes = normalise(verdict)
    final.update({"round": a.round, "model": res.model if res else model, "variant": a.variant,
                  "head_sha": pr.get("headRefOid"), "issue": issue.get("number"),
                  "tokens": res.total_tokens if res else 0})
    write_json(out / "verdict.json", final)
    write(out / "review.md", render(final, notes, final["model"], a.round, int(pr["number"]), a.variant))
    log(f"review round {a.round}: {final['verdict']} route={final['route']} findings={len(final['findings'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
