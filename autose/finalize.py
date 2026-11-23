"""Finalize (no LLM): summarise the run on the issue/PR and set the final label.

    python3 autose/finalize.py --artifacts all/ --mode build --issue N --pr P
Job results arrive in env NEEDS_JSON (toJSON(needs)).
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import gh, log, read_json, run_url  # noqa: E402


def latest_state(root: Path) -> dict[str, Any]:
    for name in ("rework-1", "build"):
        s = read_json(root / name / "state.json")
        if s:
            return dict(s)
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--mode", required=True)
    ap.add_argument("--issue", default="")
    ap.add_argument("--pr", default="")
    a = ap.parse_args()
    root = Path(a.artifacts)
    needs = json.loads(os.environ.get("NEEDS_JSON", "{}"))
    state = latest_state(root)
    reviews = [read_json(root / f"review-{k}" / "verdict.json") for k in (1, 2)]
    reviews = [r for r in reviews if r]
    pr = a.pr or str(state.get("pr") or "")

    status = str(state.get("status") or "")
    if status == "needs_clarification":
        final = "autose:needs-human"
    elif status.startswith("stopped_after"):
        final = "autose:experiment"
    elif a.mode == "build" and needs.get("build", {}).get("result") != "success":
        final = "autose:failed"
    elif needs.get("rework-1", {}).get("result") == "failure":
        final = "autose:failed"
    elif reviews and reviews[-1].get("verdict") == "approve":
        final = "autose:done"
    elif reviews and reviews[-1].get("verdict") == "request_changes":
        final = "autose:needs-human" if len(reviews) >= 2 or a.mode == "review" else "autose:failed"
    else:
        final = "autose:failed"

    rows = "\n".join(
        f"| {s} | {d.get('status')} | {d.get('attempts')} | {'; '.join(d.get('notes', []))[-300:]} |"
        for s, d in state.get("stages", {}).items()
    )
    rev_rows = "\n".join(
        f"| {r.get('round')} | {r.get('verdict')} | {r.get('route')} | {len(r.get('findings', []))} | {r.get('model')} |"
        for r in reviews
    )
    tokens = state.get("tokens", 0) + sum(int(r.get("tokens") or 0) for r in reviews)
    body = (
        f"## AutoSE run summary: `{final}`\n\nRun: {run_url()}\n"
        + (f"Pull request: #{pr}\n" if pr else "")
        + (f"\n| Stage | Status | Attempts | Notes |\n|---|---|---|---|\n{rows}\n" if rows else "")
        + (f"\n| Review round | Verdict | Route | Findings | Model |\n|---|---|---|---|---|\n{rev_rows}\n" if rev_rows else "")
        + (f"\nStopped at **{state.get('stopped_at')}**: {state.get('stop_reason') or 'see that stage artifact'}\n"
           if state.get("stopped_at") else "")
        + ("\n**Needs clarification:** the acceptance criteria could not be made testable, so no code was written. "
           "See `spec.md` in the run artifacts for the open questions.\n" if status == "needs_clarification" else "")
        + (f"\nInjection-like phrases in the issue (treated as data): {state['injection_flags']}\n"
           if state.get("injection_flags") else "")
        + f"\nTokens (builder + reviewer): {tokens:,}\n\n"
        "**Next step is a human decision: merge or close. AutoSE never merges.**\n\n"
        f"<!-- autose-state {json.dumps({'final': final, 'pr': pr, 'tokens': tokens, 'run': run_url()})} -->\n"
    )
    target = a.issue or pr
    for num in {t for t in (target, pr) if t}:
        gh(["issue", "edit", num, "--remove-label", "autose:running"], check=False, retries=1)
        gh(["label", "create", final, "--color", "c5def5"], check=False, retries=1)
        gh(["issue", "edit", num, "--add-label", final], check=False)
    if target:
        gh(["issue", "comment", target, "--body", body], check=False)
    log(f"final: {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
