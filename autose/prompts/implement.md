{{PREAMBLE}}

# Your role: Stage 3, Implementation

Implement the design below. Constraints:
- Change only files under `src/`. Tests are written in a separate stage; any change you make under
  `tests/` or elsewhere is discarded automatically.
- Keep behaviour not covered by the acceptance criteria unchanged; keep the public API compatible
  (new parameters must be optional with defaults that preserve today's output).
- Code must pass `uv run ruff check .` and `uv run mypy` (strict typing on src/mistune).
- Run `uv run pytest -q --tb=short` before you finish; existing tests must keep passing.
- Finish with a short plain-text summary of what you changed.
- If you are confident that a failing test listed in the feedback contradicts the acceptance
  criteria, do not bend the code to it; instead add a line `DISPUTE: <test id>: <reason>` to your
  final message.

{{FEEDBACK}}

<design>
{{DESIGN}}
</design>

<acceptance_criteria>
{{ACS}}
</acceptance_criteria>
