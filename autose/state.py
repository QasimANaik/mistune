"""Graph state for AutoSE (LangGraph). Plain JSON-like dicts so checkpoints and state.json stay readable.

Fields with a reducer are combined across nodes (parallel workers append), the rest are replaced.
"""

import operator
from typing import Annotated, Any, TypedDict

RESET = "__reset__"


def add_results(a: list[Any] | None, b: list[Any] | None) -> list[Any]:
    """Workers append their WorkerResult; the orchestrator sends [RESET, ...] to start a new round."""
    b = b or []
    if b and b[0] == RESET:
        return list(b[1:])
    return (a or []) + b


class AutoSEState(TypedDict, total=False):
    # request
    issue: int
    variant: str
    mode: str                     # build | rework
    round: str                    # review round that triggered a rework ("" for build)
    issue_data: dict[str, Any]    # number, title, body, url
    injection_flags: list[str]    # phrases in the issue that look like instructions (recorded, not obeyed)
    # repository
    base: str                     # commit the branch starts from
    branch: str
    patch: str                    # git diff base..HEAD after the last commit (restores code on resume)
    # stage 1-2 outputs
    acs: dict[str, str]           # AC id -> text
    # control
    stages: dict[str, dict[str, Any]]   # stage -> {status, attempts, notes}
    attempts: dict[str, int]      # tries of the current entry into a stage
    loops: dict[str, int]         # impl_after_test, redesign, cover, ci
    feedback: dict[str, str]      # stage -> text given to the next call of that stage
    need_tests: bool              # True -> implement goes to the test orchestrator, else straight to merge
    allow_no_change: bool
    last_ok: bool                 # result of the last stage check
    weak: list[str]               # AC ids without a test -> re-sent to workers only
    work_items: list[dict[str, Any]]
    results: Annotated[list[Any], add_results]
    review: dict[str, Any]        # rework input: route, round, text
    # release
    pr: int
    pr_url: str
    ci: dict[str, Any]
    # outcome
    status: str                   # running | needs_clarification | failed | pr_open | stopped_after
    stopped_at: str
    stop_reason: str
    tokens: Annotated[int, operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]


class WorkerState(TypedDict, total=False):
    """Private to one test worker (subgraph). Only the WorkerResult leaves it."""
    item: dict[str, Any]          # id, kind (criterion | e2e), criterion_ids, acs, test_file, budget
    issue: int
    diff: str
    feedback: str
    worktree: str
    tries: int
    response: str
    check: dict[str, Any]
    tokens: int
    result: dict[str, Any]


class ReviewState(TypedDict, total=False):
    pr: int
    round: str
    variant: str
    issue: dict[str, Any]
    diff: str
    head_sha: str
    attempt: int
    feedback: str
    raw: dict[str, Any] | None
    verdict: dict[str, Any]
    notes: list[str]
    model: str
    infra_error: str
    tokens: Annotated[int, operator.add]
