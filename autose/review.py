"""Stage 6: nodes of the independent review graph (wired in graph.build_review_graph).

Runs in its own read-only job on the PR-head checkout, with the reviewer model and its own prompt.
Inputs are ONLY the linked issue, the PR diff and the checked-out code. The job never downloads the
build artifacts (spec, design, transcripts, test report) and holds no write token.

    intake_pr (code) -> reviewer (AI) -> judge (code rules) -(no valid verdict, once)-> reviewer
                                                           \\-> render (review.md + verdict.json)
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent import run_agent
from common import gh, log, prompt, untrusted, write, write_json
from state import ReviewState

SEVERE = {"blocker", "major"}


def linked_issue(pr: dict[str, Any]) -> dict[str, Any]:
    m = re.search(r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)", pr.get("body") or "")
    if m:
        p = gh(["issue", "view", m.group(1), "--json", "number,title,body"], check=False)
        if p.returncode == 0:
            data: dict[str, Any] = json.loads(p.stdout)
            return data
    return {"number": pr["number"], "title": pr.get("title", ""), "body": pr.get("body") or ""}


def parse_verdict(text: str) -> dict[str, Any] | None:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    for raw in reversed(blocks or re.findall(r"(\{\s*\"verdict\".*\})", text, re.S)):
        try:
            v: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if v.get("verdict") in ("approve", "request_changes"):
            return v
    return None


def normalise(v: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Deterministic rules applied to the reviewer's output (listed in review.md)."""
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
    return {"verdict": verdict, "route": route if verdict == "request_changes" else "none",
            "summary": v.get("summary", ""), "checked": v.get("checked") or [], "findings": kept,
            "discarded_findings": [f for f in findings if f not in kept]}, notes


def render_md(v: dict[str, Any], notes: list[str]) -> str:
    icon = {"approve": "✅ APPROVE", "request_changes": "❌ REQUEST CHANGES"}.get(v["verdict"], "⚠️ ERROR")
    rows = "\n".join(
        f"| {f.get('severity', '')} | `{f.get('file', '')}:{f.get('line', '')}` | {f.get('problem', '')} | "
        f"{str(f.get('evidence', '')).replace(chr(10), ' ')[:400]} | {f.get('suggestion', '')} |"
        for f in v.get("findings", []))
    checked = "\n".join(f"- {c}" for c in v.get("checked", [])) or "- (nothing listed)"
    return (f"## AutoSE independent review, round {v['round']}: {icon}\n\n**Route:** `{v.get('route')}` · "
            f"**Reviewer model:** `{v['model']}` · **Variant:** `{v['variant']}` · PR #{v['pr']}\n\n"
            f"{v.get('summary', '')}\n\n### What the reviewer checked\n{checked}\n\n"
            + (f"### Findings\n| Severity | Where | Problem | Evidence | Suggestion |\n|---|---|---|---|---|\n{rows}\n\n"
               if rows else "### Findings\nNone.\n\n")
            + ("### Pipeline rules applied\n" + "\n".join(f"- {n}" for n in notes) + "\n\n" if notes else "")
            + "_The reviewer saw only the issue, the diff and the PR-head checkout. It cannot push. "
            "A human decides whether to merge._\n")


@dataclass
class ReviewNodes:
    cfg: dict[str, Any]
    repo: Path
    out: Path

    def intake_pr(self, s: ReviewState) -> dict[str, Any]:
        pr = json.loads(gh(["pr", "view", str(s["pr"]), "--json", "number,title,body,headRefOid"]).stdout)
        return {"issue": linked_issue(pr), "diff": gh(["pr", "diff", str(s["pr"])]).stdout,
                "head_sha": pr.get("headRefOid"), "attempt": 0, "feedback": "", "raw": None,
                "model": self.cfg["v"]["reviewer_model"]}

    def reviewer(self, s: ReviewState) -> dict[str, Any]:
        issue = s["issue"]
        text = prompt(self.cfg["v"]["reviewer_prompt"],
                      ISSUE=untrusted("untrusted_issue", issue.get("body", ""), number=str(issue.get("number")),
                                      title=issue.get("title", "")),
                      DIFF=s["diff"][:60000], FEEDBACK=s.get("feedback", ""))
        attempt = int(s.get("attempt") or 0) + 1
        res = run_agent(f"review{s['round']}-{attempt}", text, s["model"], self.cfg["v"]["reviewer_policy"],
                        self.repo, self.out, self.cfg, fallback_model=self.cfg["models"]["reviewer_fallback"])
        return {"attempt": attempt, "raw": parse_verdict(res.response), "tokens": res.total_tokens, "model": res.model}

    def judge(self, s: ReviewState) -> dict[str, Any]:
        raw = s.get("raw")
        if raw is None or (raw["verdict"] == "approve" and not raw.get("checked")):
            log("judge: no valid verdict (or approve without listing checks)")
            return {"raw": None, "feedback": "Your previous answer did not end with a valid JSON verdict, or approved "
                                             "without listing what you checked. Do the review and end with the "
                                             "required JSON block."}
        final, notes = normalise(raw)
        return {"verdict": final, "notes": notes}

    def render(self, s: ReviewState) -> dict[str, Any]:
        v = dict(s.get("verdict") or {"verdict": "error", "route": "none", "checked": [], "findings": [],
                                      "summary": "The reviewer did not produce a valid verdict."})
        v.update({"round": s["round"], "model": s.get("model"), "variant": s["variant"], "pr": s["pr"],
                  "head_sha": s.get("head_sha"), "issue": s["issue"].get("number"), "tokens": s.get("tokens", 0)})
        write_json(self.out / "verdict.json", v)
        write(self.out / "review.md", render_md(v, s.get("notes") or []))
        log(f"review round {s['round']}: {v['verdict']} route={v['route']} findings={len(v['findings'])}")
        return {"verdict": v}
