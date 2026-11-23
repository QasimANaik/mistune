"""Trigger gate (no LLM, no API key). Decides whether and how this workflow run proceeds.

Reads the event payload from GITHUB_EVENT_PATH (never interpolated into shell), checks who
triggered it, and writes outputs: mode (build | review | skip), issue, pr, variant, stop_after.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import gh, load_config, log, run_url, set_output  # noqa: E402

TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
CMD_RE = re.compile(r"^/autose(?:\s+(review))?(?:\s+variant=([a-z_]+))?\s*$")


def decide(event_name: str, ev: dict) -> dict[str, str]:
    skip = {"mode": "skip", "issue": "", "pr": "", "variant": "baseline", "stop_after": "", "why": ""}
    if event_name == "workflow_dispatch":
        inp = ev.get("inputs") or {}
        mode = inp.get("mode") or "build"
        return {"mode": mode, "issue": str(inp.get("issue") or ""), "pr": str(inp.get("pr") or ""),
                "variant": inp.get("variant") or "baseline", "stop_after": inp.get("stop_after") or "",
                "why": f"workflow_dispatch by {ev.get('sender', {}).get('login')}"}
    issue = ev.get("issue") or {}
    is_pr = "pull_request" in issue
    if event_name == "issues":
        if (ev.get("label") or {}).get("name") != "autose" or is_pr:
            return {**skip, "why": "label is not 'autose'"}
        # adding a label already requires triage/write permission on the repository
        return {**skip, "mode": "build", "issue": str(issue["number"]), "why": f"label by {ev['sender']['login']}"}
    if event_name == "issue_comment":
        c = ev.get("comment") or {}
        body = (c.get("body") or "").strip()
        m = CMD_RE.match(body.splitlines()[0].strip()) if body else None
        if not m:
            return {**skip, "why": "comment is not an /autose command"}
        if (c.get("user") or {}).get("type") == "Bot":
            return {**skip, "why": "ignoring bot comment"}
        if c.get("author_association") not in TRUSTED:
            return {**skip, "why": f"untrusted author_association {c.get('author_association')}"}
        variant = m.group(2) or "baseline"
        if is_pr:
            if issue.get("state") != "open":
                return {**skip, "why": "PR is not open"}
            return {**skip, "mode": "review", "pr": str(issue["number"]), "variant": variant,
                    "why": f"/autose on PR by {c['user']['login']}"}
        return {**skip, "mode": "build", "issue": str(issue["number"]), "variant": variant,
                "why": f"/autose on issue by {c['user']['login']}"}
    return {**skip, "why": f"unsupported event {event_name}"}


def main() -> int:
    event_name = os.environ["GITHUB_EVENT_NAME"]
    ev = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    d = decide(event_name, ev)
    if d["mode"] != "skip":
        try:
            load_config(d["variant"])
        except SystemExit as e:
            d = {**d, "mode": "skip", "why": str(e)}
    log(f"gate: {d}")
    for k in ("mode", "issue", "pr", "variant", "stop_after"):
        set_output(k, d[k])
    target = d["issue"] or d["pr"]
    if d["mode"] != "skip" and target:
        gh(["label", "create", "autose:running", "--color", "fbca04", "--force"], check=False)
        gh(["issue", "edit", target, "--add-label", "autose:running"], check=False)
        gh(["issue", "comment", target, "--body",
            f"🤖 AutoSE run started (`{d['mode']}`, variant `{d['variant']}`): {run_url()}"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
