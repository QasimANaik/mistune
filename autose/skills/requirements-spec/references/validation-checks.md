# Validation Checks

Each check has an ID, a pass criterion, and a method: **A** = automated by `scripts/validate_spec.py`,
**M** = manual (agent judgement, with the evidence written in the VAL summary), **A+M** = the validator
flags candidates and the agent decides.

Result values in the VAL summary: `PASS`, `FAIL` (with the IDs at fault), `WARN` (acceptable with a
stated reason), `MANUAL` (the automated check could not run, so it was done by hand), `NOT-RUN` (with a reason).

## Completeness (COMP)

| ID | Pass criterion | Method |
|---|---|---|
| COMP-1 | Every `SRC-*` is classified and traced to ≥1 item, or explicitly marked `CONTEXT`/`OOS`. | A (untraced SRC warning) + M |
| COMP-2 | Every gap-checklist dimension G1–G15 is marked SRC/ASM/OQ/N/A. N/A has a reason. | M |
| COMP-3 | Every actor participates in ≥1 FR. Every FR names an actor or trigger. | A+M |
| COMP-4 | Every FR and NFR has ≥1 acceptance criterion. | A |
| COMP-5 | All mandatory template sections are present (even if they only say "None identified" with a reason). | A |
| COMP-6 | Every Must FR with an error path has ≥1 negative or error acceptance criterion. | M |

## Consistency (CONS)

| ID | Pass criterion | Method |
|---|---|---|
| CONS-1 | IDs are unique and well-formed. No ID is reused. | A |
| CONS-2 | No two requirements contradict each other. Any contradiction found is recorded as a `CNF-*` and the affected items are `BLOCKED`. | M |
| CONS-3 | Terms are used as the glossary defines them. No synonyms for the same concept. | M |
| CONS-4 | No requirement contradicts a constraint (`CON-*`). | M |
| CONS-5 | No assumption contradicts a stated source. | M |
| CONS-6 | Readiness is consistent with the links: no `READY` item links an open blocking `OQ-*` or an open `CNF-*`. | A |

## Traceability (TRACE)

| ID | Pass criterion | Method |
|---|---|---|
| TRACE-1 | Every FR/NFR/CON cites ≥1 `SRC-*` or `ASM-*`. | A |
| TRACE-2 | Every acceptance criterion belongs to an existing requirement (ID prefix matches its parent). | A |
| TRACE-3 | Every `OQ-*` lists the items it affects. Every `CNF-*` cites the sources of both sides. | A |
| TRACE-4 | Every referenced ID is defined somewhere in the artefact set. | A |
| TRACE-5 | The traceability matrix lists every FR and NFR. | A |
| TRACE-6 | Every `REF-*` row in SRS §3a cites an existing evidence record whose status matches the row. | A |

## Feasibility (FEAS)

| ID | Pass criterion | Method |
|---|---|---|
| FEAS-1 | No absolute that cannot be achieved or verified (100% uptime, zero defects, "never fails", "fully autonomous with no errors"). If a source states one, keep it as `STATED`, set it to `NEEDS-CLARIFICATION`, and add an `RSK-*`. | A+M (absolutes flagged) |
| FEAS-2 | The requirement set is compatible with stated budget, deadline, team, and platform constraints, or the tension is recorded as an `RSK-*`/`CNF-*`. | M |
| FEAS-3 | Every external dependency is identified as a `DEP-*` with its availability or ownership status. | M |
| FEAS-4 | Requirements touching safety, security, payments, personal data, or irreversible actions have an associated `RSK-*` or explicit NFR. | M |

## Testability (TEST)

| ID | Pass criterion | Method |
|---|---|---|
| TEST-1 | Each FR/NFR statement contains exactly one "shall" and no "and/or". | A |
| TEST-2 | No ambiguity-lexicon word appears in a statement or criterion unless it is quantified in the same item or defined in the glossary as `DEFINED`. | A+M |
| TEST-3 | Every acceptance criterion has an observable outcome with a pass/fail decision (FR: Given/When/Then; NFR: metric + threshold + condition + method). | A (shape) + M |
| TEST-4 | Every FR/NFR has a verification method: Test, Demonstration, Inspection, or Analysis. | A |

## Provenance (PROV)

| ID | Pass criterion | Method |
|---|---|---|
| PROV-1 | Every item with `Origin: INFERRED` links ≥1 `ASM-*`. | A |
| PROV-2 | No item with `Origin: INFERRED` is `READY`. | A |
| PROV-3 | Every `STATED` item cites ≥1 `SRC-*`, and the cited quote actually supports it without added scope or numbers. | A (citation present) + M (support) |
| PROV-4 | Every `CONFIRMED` item cites a confirmation `SRC-*` whose location records a stakeholder answer. | A+M |
| PROV-5 | Agent-proposed values are labelled `Proposed (ASM-xxx)`. | A+M |
| PROV-6 | Requirements cite only successful retrievals (`OK`) as `Evidence:`. Evidence-backed items are INFERRED with an ASM. Conflicting or single-source claims are classified in REG §5 and not used as requirement values. | A+M |

## Readiness decision procedure

Evaluate each FR/NFR in this order. The first rule that matches decides.

1. Links an open `CNF-*`, or depends on a `BLOCKED` requirement, or needs a decision only a human
   with authority can make → **BLOCKED**.
2. Links an open **blocking** `OQ-*`, or fails TEST-1/2/3, or fails FEAS-1 → **NEEDS-CLARIFICATION**.
3. `Origin: INFERRED`, or depends on an unconfirmed `ASM-*`, or contains a `Proposed` value →
   **NEEDS-CONFIRMATION**.
4. Otherwise (STATED/CONFIRMED, testable, feasible, unblocked) → **READY**.

Non-blocking open questions (e.g., cosmetic detail) do not prevent `READY`, but they are listed in the
requirement's `Open questions` field.

## Overall verdict

- **IMPLEMENTATION-READY**: every `Must` FR/NFR is READY; no open blocking OQ; no open CNF; validator has no errors.
- **PARTIALLY-READY**: ≥1 `Must` requirement is READY, and the not-ready ones are listed with what unblocks them.
- **NOT-READY**: no `Must` requirement is READY, or the core actor or capability is still unresolved.

The validator computes only the mechanical rules (it cannot judge "core capability unresolved").
Downgrading a computed PARTIALLY-READY to NOT-READY under that clause is allowed with a justification in
the VAL summary; the validator shows it as a `VERDICT` warning. Declaring a verdict higher than the
computed one is a `VERDICT` error.

## Manual fallback (validator unavailable)

If the script cannot run after one retry, do the automated checks by hand:
1. List every `### <ID>` heading. Check for duplicates (CONS-1).
2. For each requirement, check that `Sources`/`Assumptions` are present, `Acceptance criteria` is present, and `Verification` is set.
3. Search for every lexicon word (analysis guide §2) in statements and criteria.
4. For each `READY` item, check that its `Origin` is not INFERRED and that its `Blocked by` field contains no open OQ or CNF.
5. Mark the affected checks `MANUAL` in the VAL summary and record the error message of the failed run.
