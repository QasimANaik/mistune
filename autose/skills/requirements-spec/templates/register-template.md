<!--
REGISTER TEMPLATE. Copy to specs/<slug>/REG-<slug>-v<N>.md.
Keep headings and field names exact. Order OQs by impact (blocking first).
-->
# Assumptions and Open-Questions Register: <Project name>

- **Document ID:** REG-<slug>
- **Version:** v<N>
- **Date:** <YYYY-MM-DD>

## 1. Open questions

### OQ-001 — <short title>
- **Question:** <one decision, phrased so a stakeholder can answer directly>
- **Why it matters:** <what it unblocks/changes>
- **Options:** (a) … (b) … (c) other
- **Default if unanswered:** ASM-… | None (cannot default safely)
- **Owner:** STK-… | <role>
- **Blocking:** yes | no
- **Affects:** FR-…, NFR-…
- **Status:** OPEN | ANSWERED | DEFERRED
- **Answer:** — | <summary> (SRC-…)

## 2. Assumptions

### ASM-001 — <short title>
- **Statement:** <what is assumed>
- **Basis:** <rationale: domain convention, logical necessity, proposal; cite SRC-… if partly grounded>
- **Origin:** INFERRED | STATED (the stakeholder's own assumption)
- **Status:** OPEN | CONFIRMED | RETRACTED
- **Confirm via:** OQ-…
- **Affects:** FR-…

## 3. Conflicts

### CNF-001 — <short title>
- **Claim A:** "<quote>" (SRC-…, STK-…)
- **Claim B:** "<quote>" (SRC-…, STK-…)
- **Nature:** stakeholder vs stakeholder | requirement vs constraint | source vs source
- **Affects:** FR-…
- **Resolution options:** (1) … trade-off … (2) … trade-off …
- **Decision owner:** STK-… | unknown
- **Status:** OPEN | RESOLVED (SRC-…)

## 4. Out of scope

### OOS-001 — <item>
- **Item:** <what is excluded or deliberately not specified>
- **Basis:** <SRC-… (explicitly excluded) | not requested by any source>
- **Origin:** STATED | INFERRED

## 5. Evidence assessment

<Only if external evidence was retrieved. One row per claim extracted from REF-* records.>

| Claim | Sources (REF) | Assessment | Effect on spec |
|---|---|---|---|
| <claim> | REF-…, REF-… | Corroborated / Single source / Conflicting / Unavailable / Not used | <IDs created or changed, or "none"> |
