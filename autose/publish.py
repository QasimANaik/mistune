"""Publish a review (no LLM, no API key): post review.md on the PR and expose verdict/route as job outputs.

    python3 autose/publish.py --pr N --review out/review-1
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import gh, log, read_json, set_output  # noqa: E402

LABELS = {"approve": ("autose:approved", "0e8a16"), "request_changes": ("autose:changes-requested", "d93f0b"),
          "error": ("autose:failed", "d93f0b")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True)
    ap.add_argument("--review", required=True)
    a = ap.parse_args()
    d = Path(a.review)
    v = read_json(d / "verdict.json", {"verdict": "error", "route": "none"})
    body = str(d / "review.md")
    flag = {"approve": "--approve", "request_changes": "--request-changes"}.get(v["verdict"])
    posted = False
    if flag:
        # GitHub refuses approve/request-changes on a PR opened by the same identity (the bot's own PRs);
        # then the review is posted as a comment review and the verdict is carried by a label.
        posted = gh(["pr", "review", a.pr, flag, "--body-file", body], check=False, retries=1).returncode == 0
    if not posted:
        gh(["pr", "review", a.pr, "--comment", "--body-file", body])
    name, color = LABELS.get(v["verdict"], LABELS["error"])
    gh(["label", "create", name, "--color", color, "--force"], check=False)
    gh(["pr", "edit", a.pr, "--remove-label", "autose:approved,autose:changes-requested"], check=False, retries=1)
    gh(["pr", "edit", a.pr, "--add-label", name], check=False)
    log(f"published review on PR #{a.pr}: {v['verdict']} (formal review state: {posted})")
    set_output("verdict", v["verdict"])
    set_output("route", v.get("route", "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
