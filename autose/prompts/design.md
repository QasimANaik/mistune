{{PREAMBLE}}

# Your role: Stage 2, Design

Plan the code change that satisfies the specification below. {{ARCH_HINT}} Explore the code as much
as you need, but **do not modify any source or test file** in this stage (such changes are discarded).

Write `.autose-work/design.md` with exactly these sections:

## Summary
2–4 sentences: what changes and why this is the right place in the architecture.

## Files and functions to change
One bullet per file, in exactly this format (paths relative to the repo root, names in backticks):
- `src/mistune/path/file.py`: `function_name`, `ClassName.method_name`
Append ` (new)` after a file path or a symbol that does not exist yet. Name at least one existing
function or class you will change. Include the test file(s) you expect to add or extend.

## Existing tests to update
Only if an acceptance criterion explicitly requires changing behaviour that existing tests or fixtures pin
down (fixture-driven tests read `tests/fixtures/*.txt`): one bullet per file,
- `tests/fixtures/file.txt`: AC-FR-001-1 (why the expected output must change)
Otherwise write `None`. These files are the only existing tests the implementer may edit.

## Plan
Numbered steps. Reference the AC ids each step satisfies.

## Risks
Edge cases and existing behaviour that must not change; how the change stays compatible with
`uv run mypy` (strict) and `uv run ruff check .`.

{{FEEDBACK}}

<specification>
{{SPEC}}
</specification>
