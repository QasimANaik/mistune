{{PREAMBLE}}

# Your role: Stage 1, Requirements

Activate the `requirements-spec` skill and follow it in **batch mode** (no stakeholder can answer
questions now) to turn the GitHub issue below into a specification. Use project slug `issue-{{N}}`
and write exactly these three files (and nothing else):

- `.autose-work/spec/SRS-issue-{{N}}-v1.md`
- `.autose-work/spec/REG-issue-{{N}}-v1.md`
- `.autose-work/spec/VAL-issue-{{N}}-v1.md`

External-evidence (MCP/Fetch) checks are not available here: report them as NOT-RUN.

Additional rules for this pipeline (they take precedence over the skill where they differ):
1. Requirements describe observable behaviour of the library, not code design. You may read the
   code (e.g. to learn the current output format) but do not plan the change.
2. Every functional requirement has acceptance criteria written on ONE line each, exactly as
   `- AC-FR-001-1: Given <concrete Markdown input / options>, when <API call>, then <exact observable output>.`
   Use concrete example inputs and expected HTML fragments so each AC becomes one pytest test.
   Avoid vague words (fast, simple, robust, large, secure, …).
3. Add acceptance criteria that existing behaviour the issue does not ask to change stays the same
   (regression), where the change could plausibly break it.
4. At most 6 functional requirements. Keep the documents short.
5. If the issue is vague, choose the most reasonable interpretation, record it as an assumption
   (ASM-*) and an open question (OQ-*), and still write testable ACs for that interpretation.

{{FEEDBACK}}

{{ISSUE}}
