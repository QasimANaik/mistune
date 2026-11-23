#!/usr/bin/env python3
"""Structural, traceability, provenance and testability linter for requirements-spec artefacts.

Usage:
    python3 validate_spec.py <spec-dir> [--version vN] [--json]

<spec-dir> holds SRS-<slug>-v<N>.md, REG-<slug>-v<N>.md and VAL-<slug>-v<N>.md.
The highest version present is checked unless --version is given.

Exit codes: 0 = no errors (warnings allowed), 1 = errors found, 2 = usage or input problem.
Only the standard library is used.
"""
import argparse
import json
import re
import sys
from pathlib import Path

PREFIXES = "SRC|REF|STK|ACT|FR|NFR|CON|DEP|RSK|ASM|OQ|CNF|GL|OOS"
ID_RE = re.compile(rf"(?<![A-Za-z0-9-])(?:{PREFIXES})-\d{{3}}\b")
AC_RE = re.compile(r"\bAC-((?:FR|NFR)-\d{3})-(\d+)\b")
HEADING_RE = re.compile(rf"^###\s+((?:{PREFIXES})-\d{{3}})\b")
TABLE_ROW_RE = re.compile(rf"^\|\s*((?:{PREFIXES})-\d{{3}})\s*\|")
FIELD_RE = re.compile(r"^\s*-\s+\*\*([^*]+?):\*\*\s*(.*)$")
FILE_RE = re.compile(r"^(SRS|REG|VAL)-(.+)-v(\d+)\.md$")

ORIGINS = {"STATED", "CONFIRMED", "INFERRED"}
READINESS = {"READY", "NEEDS-CONFIRMATION", "NEEDS-CLARIFICATION", "BLOCKED"}
VERIFICATION = {"TEST", "DEMONSTRATION", "INSPECTION", "ANALYSIS"}
VERDICTS = ("IMPLEMENTATION-READY", "PARTIALLY-READY", "NOT-READY")

REQUIRED_SECTIONS = {
    "SRS": ["introduction", "glossary", "sources", "stakeholders", "functional requirements",
            "non-functional requirements", "constraints", "dependencies", "risks",
            "traceability", "change log"],
    "REG": ["open questions", "assumptions", "conflicts", "out of scope"],
    "VAL": ["readiness", "check results", "gap checklist", "tool log", "human decisions"],
}

LEXICON = [
    "fast", "quick", "responsive", "real-time", "instant", "low-latency", "efficient",
    "scalable", "enterprise-grade", "unlimited", "reliable", "robust", "highly available",
    "resilient", "secure", "privacy-preserving", "safe", "sovereign", "user-friendly",
    "intuitive", "easy", "seamless", "simple", "modern", "autonomous", "smart", "intelligent",
    "model-agnostic", "flexible", "local-first", "etc", "and so on", "as appropriate",
    "various", "minimal", "sufficient", "best-in-class", "state-of-the-art", "world-class",
    # Mirrors references/analysis-guide.md §2. Deliberately omitted because they are ordinary words
    # that would flood the report with false positives: support, handle, manage, open, offline, some, all, every.
    "high-volume", "massive", "large", "private", "compliant", "trusted", "always on",
    "fault-tolerant", "ai-powered", "agentic", "self-healing", "pluggable", "vendor-neutral",
    "extensible", "interoperable", "self-hosted", "cloud-native", "on-prem",
]
VERDICT_RANK = {"NOT-READY": 0, "PARTIALLY-READY": 1, "IMPLEMENTATION-READY": 2}
ABSOLUTES = ["100%", "zero", "never", "always", "guaranteed", "fully", "all times"]


class Report:
    def __init__(self):
        self.errors, self.warnings, self.info = [], [], []

    def error(self, check, msg):
        self.errors.append((check, msg))

    def warn(self, check, msg):
        self.warnings.append((check, msg))


def pick_files(spec_dir: Path, version):
    found = {}
    for p in spec_dir.iterdir():
        m = FILE_RE.match(p.name)
        if m:
            kind, _slug, ver = m.group(1), m.group(2), int(m.group(3))
            found.setdefault(ver, {})[kind] = p
    if not found:
        return None, {}
    ver = int(version.lstrip("v")) if version else max(found)
    return ver, found.get(ver, {})


def parse_items(text):
    """Return {id: {"fields": {name: value}, "body": str, "acs": [(parent, n, text)]}} for ### blocks."""
    items, current, field = {}, None, None
    for line in text.splitlines():
        h = HEADING_RE.match(line)
        if h:
            current = h.group(1)
            items.setdefault(current, []).append({"fields": {}, "body": "", "acs": []})
            field = None
            continue
        if line.startswith("## ") or (line.startswith("### ") and not h):
            current, field = None, None
            continue
        if current is None:
            continue
        block = items[current][-1]
        block["body"] += line + "\n"
        f = FIELD_RE.match(line)
        if f and not AC_RE.search(f.group(1)):
            field = f.group(1).strip()
            block["fields"][field] = f.group(2).strip()
            continue
        for m in AC_RE.finditer(line):
            if re.match(r"^\s*-\s+\*{0,2}AC-", line):
                block["acs"].append((m.group(1), m.group(2), line.strip()))
                break
        if field and line.startswith("  ") and not line.strip().startswith("- AC-"):
            block["fields"][field] += " " + line.strip()
    return items


def sections(text):
    return [l[3:].strip().lower() for l in text.splitlines() if l.startswith("## ")]


def ids_in(s):
    return set(ID_RE.findall(s or ""))


def has_word(text, word):
    return re.search(rf"(?<![A-Za-z-]){re.escape(word)}(?![A-Za-z-])", text, re.IGNORECASE) is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec_dir")
    ap.add_argument("--version")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        print(f"error: {spec_dir} is not a directory", file=sys.stderr)
        return 2
    ver, files = pick_files(spec_dir, args.version)
    r = Report()
    if ver is None:
        print("error: no SRS-/REG-/VAL-<slug>-v<N>.md files found", file=sys.stderr)
        return 2
    for kind in ("SRS", "REG", "VAL"):
        if kind not in files:
            r.error("COMP-5", f"missing {kind} file for v{ver}")

    texts = {k: p.read_text(encoding="utf-8") for k, p in files.items()}
    all_text = "\n".join(texts.values())

    # COMP-5: mandatory sections
    for kind, needed in REQUIRED_SECTIONS.items():
        if kind not in texts:
            continue
        have = sections(texts[kind])
        for s in needed:
            if not any(s in h for h in have):
                r.error("COMP-5", f"{kind}: missing section containing '{s}'")

    # Definitions: ### headings and first-column table rows
    items, defined, table_rows = {}, {}, {}
    for kind, text in texts.items():
        for iid, blocks in parse_items(text).items():
            items.setdefault(iid, []).extend(blocks)
            defined[iid] = defined.get(iid, 0) + len(blocks)
        for line in text.splitlines():
            m = TABLE_ROW_RE.match(line)
            if m and kind == "SRS" and not m.group(1).startswith(("FR-", "NFR-")):
                table_rows.setdefault(m.group(1), []).append(line)
    for iid, rows in table_rows.items():
        defined[iid] = defined.get(iid, 0) + len(rows)

    # CONS-1: uniqueness
    for iid, n in defined.items():
        if n > 1:
            r.error("CONS-1", f"{iid} defined {n} times")

    # TRACE-4: every referenced ID is defined
    referenced = ids_in(all_text)
    for iid in sorted(referenced - set(defined)):
        if "…" in iid:
            continue
        r.error("TRACE-4", f"{iid} is referenced but never defined")

    # Lookup helpers for register state
    def field(iid, name, default=""):
        blocks = items.get(iid)
        return blocks[0]["fields"].get(name, default) if blocks else default

    open_blocking_oq = {i for i in items if i.startswith("OQ-")
                        and field(i, "Status").upper().startswith("OPEN")
                        and field(i, "Blocking").lower().startswith("yes")}
    open_cnf = {i for i in items if i.startswith("CNF-") and field(i, "Status").upper().startswith("OPEN")}
    open_asm = {i for i in items if i.startswith("ASM-") and field(i, "Status").upper().startswith("OPEN")}

    # External evidence (REF-*): status per SRS table row, cross-checked with evidence records
    ref_status = {}
    evidence_records = {}
    for iid, rows in table_rows.items():
        if not iid.startswith("REF-"):
            continue
        cells = [c.strip() for c in rows[0].strip("|").split("|")]
        st = next((c.split()[0] for c in cells if c.split() and c.split()[0] in ("OK", "TOOL-ERROR", "UNAVAILABLE")), None)
        if st is None:
            r.error("TRACE-6", f"{iid}: evidence row has no status (OK / TOOL-ERROR / UNAVAILABLE)")
        ref_status[iid] = st
        rec = next((c for c in cells if c.endswith(".json")), None)
        if rec is None:
            r.error("TRACE-6", f"{iid}: evidence row cites no evidence record (.json)")
            continue
        rec_path = spec_dir / rec
        if not rec_path.exists():
            r.error("TRACE-6", f"{iid}: evidence record {rec} not found")
            continue
        try:
            data = json.loads(rec_path.read_text(encoding="utf-8"))
        except ValueError:
            r.error("TRACE-6", f"{iid}: evidence record {rec} is not valid JSON")
            continue
        evidence_records[iid] = data
        if st and data.get("status") != st:
            r.error("TRACE-6", f"{iid}: row says {st} but record says {data.get('status')}")

    defined_terms = set()
    for iid, rows in table_rows.items():
        if iid.startswith("GL-"):
            cells = [c.strip() for c in rows[0].strip("|").split("|")]
            if len(cells) > 3 and re.search(r"\bDEFINED\b", cells[3]) and "UNDEFINED" not in cells[3]:
                defined_terms.add(cells[1].lower())

    # Requirement checks
    reqs = sorted(i for i in items if i.startswith(("FR-", "NFR-")))
    stats = {"FR": {}, "NFR": {}, "MUST": {}}
    origins = {}
    for rid in reqs:
        f = items[rid][0]["fields"]
        acs = items[rid][0]["acs"]
        stmt = f.get("Statement", "")
        origin = f.get("Origin", "").split()[0].upper() if f.get("Origin") else ""
        readiness = f.get("Readiness", "").split()[0].upper() if f.get("Readiness") else ""
        sources = f.get("Sources", "")
        assumptions = f.get("Assumptions", "")
        blocked_by = f.get("Blocked by", "")
        priority = f.get("Priority", "")
        verification = f.get("Verification", "").split()[0].upper().strip(",") if f.get("Verification") else ""
        kind = rid.split("-")[0]
        stats[kind][readiness] = stats[kind].get(readiness, 0) + 1
        if priority.lower().startswith("must"):
            stats["MUST"][readiness] = stats["MUST"].get(readiness, 0) + 1
        origins[origin] = origins.get(origin, 0) + 1

        if not stmt:
            r.error("TEST-1", f"{rid}: no Statement")
        else:
            n_shall = len(re.findall(r"\bshall\b", stmt, re.IGNORECASE))
            if n_shall != 1:
                r.error("TEST-1", f"{rid}: statement has {n_shall} 'shall' (expected 1)")
            if "and/or" in stmt.lower():
                r.error("TEST-1", f"{rid}: statement uses 'and/or'")
        if origin not in ORIGINS:
            r.error("PROV-1", f"{rid}: Origin '{f.get('Origin', '')}' not one of {sorted(ORIGINS)}")
        if readiness not in READINESS:
            r.error("CONS-6", f"{rid}: Readiness '{f.get('Readiness', '')}' not one of {sorted(READINESS)}")
        src_ids = {i for i in ids_in(sources) if i.startswith("SRC-")}
        asm_ids = {i for i in ids_in(sources + " " + assumptions) if i.startswith("ASM-")}
        ev_ids = {i for i in ids_in(f.get("Evidence", "")) if i.startswith("REF-")}
        for ref in sorted(ev_ids):
            if ref_status.get(ref) not in (None, "OK"):
                r.error("PROV-6", f"{rid}: cites {ref} as evidence but that retrieval failed ({ref_status[ref]})")
        if ev_ids and origin == "INFERRED" and not asm_ids:
            r.error("PROV-6", f"{rid}: evidence-backed inference must still link an ASM-*")
        if not src_ids and not asm_ids:
            r.error("TRACE-1", f"{rid}: cites no SRC-* or ASM-*")
        if origin == "STATED" and not src_ids:
            r.error("PROV-3", f"{rid}: STATED but cites no SRC-*")
        if origin == "CONFIRMED" and not src_ids:
            r.error("PROV-4", f"{rid}: CONFIRMED but cites no confirmation SRC-*")
        if origin == "INFERRED" and not asm_ids:
            r.error("PROV-1", f"{rid}: INFERRED but links no ASM-*")
        if origin == "INFERRED" and readiness == "READY":
            r.error("PROV-2", f"{rid}: INFERRED item marked READY")
        if readiness == "READY":
            bad = (ids_in(blocked_by) | ids_in(stmt)) & (open_blocking_oq | open_cnf)
            if bad:
                r.error("CONS-6", f"{rid}: READY but blocked by open {sorted(bad)}")
            bad_asm = asm_ids & open_asm
            if bad_asm:
                r.error("CONS-6", f"{rid}: READY but depends on unconfirmed {sorted(bad_asm)}")
            if any("proposed" in a[2].lower() for a in acs):
                r.error("PROV-5", f"{rid}: READY but an acceptance criterion contains a Proposed value")
        if readiness == "BLOCKED" and not ids_in(blocked_by):
            r.warn("CONS-6", f"{rid}: BLOCKED but 'Blocked by' names no ID")
        if readiness == "NEEDS-CLARIFICATION" and not (ids_in(blocked_by) | ids_in(f.get("Open questions", ""))):
            r.warn("CONS-6", f"{rid}: NEEDS-CLARIFICATION but no OQ-* linked")
        if verification not in VERIFICATION:
            r.error("TEST-4", f"{rid}: Verification '{f.get('Verification', '')}' not one of {sorted(VERIFICATION)}")
        if kind == "FR" and not ids_in(f.get("Actor/Trigger", "")) and not f.get("Actor/Trigger"):
            r.warn("COMP-3", f"{rid}: no Actor/Trigger")

        # COMP-4 / TRACE-2 / TEST-3
        if not acs:
            r.error("COMP-4", f"{rid}: no acceptance criteria")
        for parent, n, line in acs:
            if parent != rid:
                r.error("TRACE-2", f"AC-{parent}-{n} listed under {rid}")
            low = line.lower()
            if kind == "FR" and not ("given" in low and "when" in low and "then" in low):
                r.warn("TEST-3", f"AC-{parent}-{n}: not in Given/When/Then form")
            if kind == "NFR" and not all(k in low for k in ("metric", "threshold", "conditions", "method")):
                r.warn("TEST-3", f"AC-{parent}-{n}: missing Metric/Threshold/Conditions/Method")
            if kind == "NFR":
                tm = re.search(r"threshold:\s*([^|]*)", line, re.IGNORECASE)
                if tm and not re.search(r"\d", tm.group(1)) and "proposed" not in tm.group(1).lower():
                    r.warn("TEST-3", f"AC-{parent}-{n}: Threshold '{tm.group(1).strip()}' has no number "
                                     "(quantify it, or label it Proposed (ASM-xxx))")

        # TEST-2 / FEAS-1 lexicon scan (statement + criteria)
        scan = stmt + " " + " ".join(a[2] for a in acs)
        vague = [w for w in LEXICON if has_word(scan, w) and w not in defined_terms]
        if vague and readiness == "READY":
            r.error("TEST-2", f"{rid}: READY but uses undefined vague term(s) {vague}")
        elif vague:
            r.warn("TEST-2", f"{rid}: uses vague term(s) {vague} (acceptable only while not READY)")
        absolutes = [w for w in ABSOLUTES if has_word(stmt, w)]
        if absolutes:
            r.warn("FEAS-1", f"{rid}: absolute wording {absolutes}; confirm it is achievable and verifiable")

    # Constraints trace
    for cid in sorted(i for i in items if i.startswith("CON-")):
        f = items[cid][0]["fields"]
        if not ids_in(f.get("Sources", "") + " " + f.get("Assumptions", "")):
            r.error("TRACE-1", f"{cid}: cites no SRC-* or ASM-*")
        if f.get("Origin", "").upper().startswith("INFERRED") and not ids_in(f.get("Assumptions", "")):
            r.error("PROV-1", f"{cid}: INFERRED but links no ASM-*")

    # TRACE-3: OQ affects; CNF has both sides sourced
    for qid in sorted(i for i in items if i.startswith("OQ-")):
        if not ids_in(field(qid, "Affects")):
            r.error("TRACE-3", f"{qid}: Affects lists no IDs")
        if not field(qid, "Status"):
            r.error("TRACE-3", f"{qid}: no Status")
    for cid in sorted(i for i in items if i.startswith("CNF-")):
        a = {i for i in ids_in(field(cid, "Claim A")) if i.startswith("SRC-")}
        b = {i for i in ids_in(field(cid, "Claim B")) if i.startswith("SRC-")}
        if not a or not b:
            r.error("TRACE-3", f"{cid}: each claim must cite a SRC-*")
        if not ids_in(field(cid, "Affects")):
            r.error("TRACE-3", f"{cid}: Affects lists no IDs")
    for aid in sorted(i for i in items if i.startswith("ASM-")):
        if not field(aid, "Status"):
            r.error("TRACE-3", f"{aid}: no Status")

    # TRACE-5: traceability matrix covers every requirement
    srs = texts.get("SRS", "")
    m = re.search(r"^## [^\n]*traceability[^\n]*\n(.*?)(?=^## |\Z)", srs, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    matrix = m.group(1) if m else ""
    for rid in reqs:
        if not re.search(rf"^\|\s*{rid}\s*\|", matrix, re.MULTILINE):
            r.error("TRACE-5", f"{rid}: missing from traceability matrix")

    # COMP-1: every SRC referenced or explicitly CONTEXT/OOS
    for sid, rows in table_rows.items():
        if not sid.startswith("SRC-"):
            continue
        uses = len(re.findall(rf"(?<![A-Za-z0-9-]){sid}\b", all_text)) - len(rows)
        if uses <= 0 and not re.search(r"\b(CONTEXT|OOS)\b", rows[0]):
            r.warn("COMP-1", f"{sid}: not traced to any item and not marked CONTEXT/OOS")

    # COMP-3: every actor used by some FR
    fr_text = " ".join(items[i][0]["body"] for i in reqs if i.startswith("FR-"))
    for aid in sorted(i for i in table_rows if i.startswith("ACT-")):
        if aid not in fr_text:
            r.warn("COMP-3", f"{aid}: not referenced by any FR")

    # Verdict
    must = stats["MUST"]
    must_total = sum(must.values())
    must_ready = must.get("READY", 0)
    if must_total and must_ready == must_total and not open_blocking_oq and not open_cnf and not r.errors:
        computed = "IMPLEMENTATION-READY"
    elif must_ready > 0:
        computed = "PARTIALLY-READY"
    else:
        computed = "NOT-READY"
    for kind in ("SRS", "VAL"):
        dm = re.search(r"\*\*Verdict:\*\*\s*([A-Z-]+)", texts.get(kind, ""))
        declared = dm.group(1) if dm else None
        if declared is None:
            r.error("COMP-5", f"{kind}: no '**Verdict:**' line")
        elif declared not in VERDICT_RANK:
            r.error("COMP-5", f"{kind}: verdict '{declared}' is not one of {list(VERDICTS)}")
        elif VERDICT_RANK[declared] > VERDICT_RANK[computed]:
            r.error("VERDICT", f"{kind} declares {declared} but the computed verdict is {computed} "
                               "(a verdict may be downgraded by the analyst, never upgraded)")
        elif declared != computed:
            r.warn("VERDICT", f"{kind} declares {declared}; computed {computed} (justify the downgrade in VAL)")

    result = {
        "version": f"v{ver}",
        "files": {k: str(p) for k, p in files.items()},
        "requirements": len(reqs),
        "readiness": stats,
        "origins": origins,
        "open_blocking_questions": sorted(open_blocking_oq),
        "open_conflicts": sorted(open_cnf),
        "computed_verdict": computed,
        "errors": [{"check": c, "message": m} for c, m in r.errors],
        "warnings": [{"check": c, "message": m} for c, m in r.warnings],
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"validate_spec: {spec_dir} (v{ver})")
        print(f"  requirements: {len(reqs)}  origins: {origins}")
        print(f"  readiness FR: {stats['FR']}  NFR: {stats['NFR']}  Must: {stats['MUST']}")
        print(f"  open blocking OQs: {len(open_blocking_oq)}  open conflicts: {len(open_cnf)}")
        print(f"  computed verdict: {computed}")
        print(f"  {len(r.errors)} error(s), {len(r.warnings)} warning(s)")
        for c, msg in r.errors:
            print(f"  ERROR [{c}] {msg}")
        for c, msg in r.warnings:
            print(f"  WARN  [{c}] {msg}")
    return 1 if r.errors else 0


if __name__ == "__main__":
    sys.exit(main())
