{{PREAMBLE}}

# Your role: Stage 4, test worker (one slice of the acceptance criteria)

You are one of several test workers running in parallel, each in its own copy of the repository.
The implementation is already in the working tree (diff below). Write pytest tests for ONLY the
acceptance criteria listed below.

- Write all your tests in ONE new file: `{{FILE}}`. Do not edit any other file (other changes are discarded).
- Each test function's docstring must start with the AC id(s) it covers, e.g. `"""AC-FR-001-1: ..."""`.
  Every AC id below must be covered by at least one test.
- Test behaviour through the public API (`mistune.create_markdown(...)`, `mistune.html`, `mistune.toc`,
  renderers) with concrete inputs and exact expected output where the AC gives it.
- A test must fail if the behaviour it checks were missing; do not write tests that cannot fail.
- Do NOT modify anything under `src/`. If a test fails because the implementation is wrong, keep the
  test and say so in your final message.
- Run `uv run pytest -q {{FILE}}` and end with a short summary.

{{FEEDBACK}}

<acceptance_criteria>
{{ACS}}
</acceptance_criteria>

<implementation_diff>
{{DIFF}}
</implementation_diff>
