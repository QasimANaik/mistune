{{PREAMBLE}}

# Your role: Stage 4, Testing

Write pytest tests for EVERY acceptance criterion below, against the implementation that is already
in the working tree (diff shown below).
- Put the tests in `tests/test_autose_issue_{{N}}.py` (create it) or extend an existing test module.
- Each test function's docstring must start with the AC id(s) it covers, e.g. `"""AC-FR-001-1: ..."""`.
  Every AC id must be covered by at least one test.
- Test behaviour through the public API (`mistune.create_markdown(...)`, `mistune.html`,
  `mistune.toc`, renderers), with concrete inputs and exact expected output where the AC gives it.
- A test must fail if the behaviour it checks were missing; do not write tests that cannot fail.
- Do NOT modify anything under `src/`; such changes are discarded. If a test fails because the
  implementation is wrong, keep the test, and say so in your final message.
- Run `uv run pytest -q` and end with a short summary (tests added, which pass/fail).

{{FEEDBACK}}

<acceptance_criteria>
{{ACS}}
</acceptance_criteria>

<implementation_diff>
{{DIFF}}
</implementation_diff>
