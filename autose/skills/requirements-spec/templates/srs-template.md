<!--
SRS TEMPLATE. Copy to specs/<slug>/SRS-<slug>-v<N>.md and fill in.
Keep the "## n. Title" headings and the "- **Field:**" names exactly as written: the validator parses them.
Use "None identified: <reason>" rather than deleting a section.
-->
# Software Requirements Specification: <Project name>

- **Document ID:** SRS-<slug>
- **Version:** v<N>
- **Date:** <YYYY-MM-DD>
- **Status:** DRAFT | IN-REVIEW | BASELINED
- **Verdict:** NOT-READY | PARTIALLY-READY | IMPLEMENTATION-READY
- **Companion files:** REG-<slug>-v<N>.md, VAL-<slug>-v<N>.md
- **Interaction mode:** interactive | batch (<why>)

> **Legend.** *Origin:* STATED = said in a source · CONFIRMED = inference confirmed by a stakeholder ·
> INFERRED = the analyst's inference (see linked ASM). *Readiness:* READY · NEEDS-CONFIRMATION ·
> NEEDS-CLARIFICATION · BLOCKED. INFERRED items are never READY.

## 1. Introduction

### 1.1 Purpose
<What this document is for and who should review it.>

### 1.2 Problem statement (as given)
<One-paragraph neutral summary of the input. No new content.>

### 1.3 Scope
- **In scope (stated):** <…> (SRC-…)
- **In scope (inferred, pending confirmation):** <…> (ASM-…)
- **Out of scope:** see OOS-* in the register.

### 1.4 Success measures
<Stated goals/metrics, or "None stated" + OQ reference.>

## 2. Glossary

| ID | Term | Definition / candidate readings | Status | Ref |
|---|---|---|---|---|
| GL-001 | <term> | <definition, or "(a) … (b) …"> | DEFINED / AMBIGUOUS / UNDEFINED | SRC-…, OQ-… |

## 3. Sources

| ID | Verbatim statement | Location | Classification |
|---|---|---|---|
| SRC-001 | "<exact quote>" | <file/para/speaker/date> | FUNC, TERM |

## 3a. External evidence

<One row per MCP tool call, including failures. Records live in evidence/REF-NNN.json. Evidence is context, never a stakeholder statement.>

| ID | Title | URL | Record | Status | Source type | Used for |
|---|---|---|---|---|---|---|
| REF-001 | <title> | <url> | evidence/REF-001.json | OK / TOOL-ERROR (<reason>) / UNAVAILABLE | primary / secondary / tertiary | <IDs, or "not used"> |

## 4. Stakeholders and actors

| ID | Name / role | Kind | Interest or interaction | Decision authority | Origin | Ref |
|---|---|---|---|---|---|---|
| STK-001 | <role> | Stakeholder | <…> | <yes/no/unknown> | STATED | SRC-… |
| ACT-001 | <role/system> | Human actor / System actor | <…> | — | INFERRED | ASM-… |

## 5. Functional requirements

### FR-001 — <short title>
- **Statement:** <EARS sentence with exactly one "shall">
- **Actor/Trigger:** ACT-…
- **Origin:** STATED | CONFIRMED | INFERRED
- **Sources:** SRC-…
- **Assumptions:** ASM-… | None
- **Priority:** Must | Should | Could | Won't (stated | inferred)
- **Readiness:** READY | NEEDS-CONFIRMATION | NEEDS-CLARIFICATION | BLOCKED
- **Blocked by:** OQ-… / CNF-… | None
- **Open questions:** <non-blocking OQ-…> | None
- **Evidence:** <REF-… with what it supports> (optional; never replaces Sources/Assumptions)
- **Verification:** Test | Demonstration | Inspection | Analysis
- **Acceptance criteria:**
  - AC-FR-001-1: Given <…>, when <…>, then <…>.
  - AC-FR-001-2: Given <error condition>, when <…>, then <…>.

## 6. Non-functional requirements

<Order NFRs by category; record the category in the Category field rather than in extra headings.>

### NFR-001 — <short title>
- **Statement:** <…shall…>
- **Category:** Performance | Compatibility | Usability | Reliability | Security | Maintainability | Portability | Safety | Privacy & compliance
- **Origin:** STATED | CONFIRMED | INFERRED
- **Sources:** SRC-…
- **Assumptions:** ASM-… | None
- **Priority:** Must | Should | Could | Won't (stated | inferred)
- **Readiness:** READY | NEEDS-CONFIRMATION | NEEDS-CLARIFICATION | BLOCKED
- **Blocked by:** None
- **Open questions:** None
- **Verification:** Test | Demonstration | Inspection | Analysis
- **Acceptance criteria:**
  - AC-NFR-001-1: Metric: <…> | Threshold: <… or "Proposed (ASM-…): …"> | Conditions: <…> | Method: <…>

## 7. Constraints

### CON-001 — <title>
- **Statement:** <…>
- **Origin:** STATED | CONFIRMED | INFERRED
- **Sources:** SRC-…
- **Assumptions:** None

## 8. Dependencies

### DEP-001 — <external system / party / data>
- **Description:** <…>
- **Availability / owner:** <known | unknown → OQ-…>
- **Affects:** FR-…

## 9. Risks

### RSK-001 — <title>
- **Description:** <…>
- **Cause:** <IDs>
- **Impact:** <…>
- **Likelihood:** L | M | H (inferred)
- **Mitigation idea:** <a question or candidate requirement, not a decision>

## 10. Traceability matrix

| Requirement | Sources | Assumptions | Open items | Acceptance criteria | Priority | Readiness |
|---|---|---|---|---|---|---|
| FR-001 | SRC-… | — | — | AC-FR-001-1..2 | Must | READY |

## 11. Change log

| Version | Date | Change | IDs affected |
|---|---|---|---|
| v1 | <date> | Initial draft from <inputs> | all |
