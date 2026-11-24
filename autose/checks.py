"""Deterministic stage checks. The orchestrator, not an agent, decides pass/fail from these."""

import ast
import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from common import TOOL, git, sh

AC_LINE_RE = re.compile(r"\b(AC-(?:FR|NFR)-\d{3}-\d+)\b\s*[:\-–]?\s*(.*)")
AC_ID_RE = re.compile(r"\bAC-(?:FR|NFR)-\d{3}-\d+\b")


@dataclass
class Check:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    details: str = ""

    def text(self) -> str:
        head = "PASS" if self.ok else "FAIL"
        body = "\n".join(f"- {r}" for r in self.reasons) or "- (no problems found)"
        return f"**{head}**\n\n{body}\n" + (f"\n```\n{self.details[-4000:]}\n```\n" if self.details else "")


def _lexicon() -> list[str]:
    """Vague-word list from the A1 requirements-spec skill's own validator (reused, not copied)."""
    path = TOOL / "skills" / "requirements-spec" / "scripts" / "validate_spec.py"
    spec = importlib.util.spec_from_file_location("a1_validate_spec", path)
    if not spec or not spec.loader:
        return []
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(getattr(mod, "LEXICON", []))


# ---------------------------------------------------------------- stage 1: spec
def extract_acs(srs_text: str) -> dict[str, str]:
    acs: dict[str, str] = {}
    for line in srs_text.splitlines():
        m = AC_LINE_RE.search(line)
        if m and m.group(1) not in acs and len(m.group(2)) > 10:
            acs[m.group(1)] = m.group(2).strip()
    return acs


def check_spec(spec_dir: Path) -> tuple[Check, dict[str, str], str]:
    srs_files = sorted(spec_dir.glob("SRS-*.md"))
    if not srs_files:
        return Check(False, [f"no SRS-*.md file written in {spec_dir.name}/"]), {}, ""
    srs = srs_files[-1].read_text()
    acs = extract_acs(srs)
    reasons: list[str] = []
    if not acs:
        reasons.append("no acceptance criteria with ids like AC-FR-001-1 found in the SRS")
    vague = _lexicon()
    for ac_id, text in acs.items():
        low = text.lower()
        if ac_id.startswith("AC-FR"):
            if not all(re.search(rf"\b{w}\b", low) for w in ("given", "when", "then")):
                reasons.append(f"{ac_id} is not in Given/When/Then form: {text[:120]!r}")
        elif "metric" not in low and not all(w in low for w in ("given", "when", "then")):
            reasons.append(f"{ac_id} (NFR) has neither Metric/Threshold nor Given/When/Then form")
        hits = [w for w in vague if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", low)]
        if hits:
            reasons.append(f"{ac_id} uses vague wording {hits} (not testable as written)")
    # A1 validator: structural/traceability lint. Recorded, but only AC testability blocks the stage
    # (batch mode leaves INFERRED items NEEDS-CONFIRMATION by design, which the validator flags).
    validator = TOOL / "skills" / "requirements-spec" / "scripts" / "validate_spec.py"
    p = sh(["python3", str(validator), str(spec_dir), "--json"], check=False)
    details = ""
    try:
        res = json.loads(p.stdout)
        errs = res.get("errors", [])
        details = f"A1 validate_spec.py: {len(errs)} errors, {len(res.get('warnings', []))} warnings\n" + "\n".join(
            str(e) for e in errs[:15]
        )
    except json.JSONDecodeError:
        details = f"A1 validate_spec.py exit {p.returncode}: {p.stdout[-800:]} {p.stderr[-800:]}"
    return Check(not reasons, reasons, details), acs, srs


# ---------------------------------------------------------------- stage 2: design
_NEW = r"[(\[]\s*new\s*[)\]]"  # "(new)" / "[new]", any case
_FILE_LINE_RE = re.compile(rf"^\s*[-*]\s*`([^`]+)`\s*({_NEW})?\s*:?\s*(.*)$", re.I)
_SYM_RE = re.compile(rf"`([^`]+)`\s*({_NEW})?", re.I)
_NEW_INSIDE = re.compile(rf"\s*{_NEW}\s*", re.I)


def _name(raw: str, marked_new: bool) -> tuple[str, bool]:
    """Accept `(new)` inside or after the backticks; drop a trailing call `()`."""
    new = marked_new or bool(_NEW_INSIDE.search(raw))
    name = _NEW_INSIDE.sub("", raw).strip()
    return (name[:-2] if name.endswith("()") else name), new


def _defined_names(path: Path) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names.add(f"{node.name}.{sub.name}")
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def check_design(design: Path, repo: Path) -> Check:
    if not design.exists():
        return Check(False, ["design.md was not written"])
    text = design.read_text()
    m = re.search(r"^##\s*Files and functions to change\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    if not m:
        return Check(False, ["missing section '## Files and functions to change'"])
    reasons: list[str] = []
    existing_hits = 0
    entries = 0
    for line in m.group(1).splitlines():
        fm = _FILE_LINE_RE.match(line)
        if not fm:
            continue
        entries += 1
        rel, file_new = _name(fm.group(1), bool(fm.group(2)))
        rest = fm.group(3)
        path = repo / rel
        if file_new:
            if not (rel.startswith("src/") or rel.startswith("tests/")):
                reasons.append(f"new file {rel} is outside src/ or tests/")
            continue
        if not path.is_file():
            reasons.append(f"file {rel} does not exist (mark it `(new)` if it should be created)")
            continue
        if not rel.endswith(".py") or rel.startswith("tests/"):
            continue  # test functions are written later by the test workers; only the file is checked here
        names = _defined_names(path)
        for sm in _SYM_RE.finditer(rest):
            sym, sym_new = _name(sm.group(1), bool(sm.group(2)))
            if sym_new:
                continue
            last = sym.split(".")[-1]
            if sym in names or last in names:
                existing_hits += 1
            else:
                reasons.append(f"`{sym}` not found in {rel} (mark it `(new)` if it should be created)")
    if entries == 0:
        reasons.append("no file bullets in the format - `path`: `symbol`, `symbol`")
    elif existing_hits == 0:
        reasons.append("the plan names no existing function/class to change")
    return Check(not reasons, reasons)


# ---------------------------------------------------------------- stage 3: build + diff guard
def changed_paths(repo: Path) -> list[tuple[str, bool]]:
    """(path, tracked) for every modified/added/deleted/untracked path vs HEAD."""
    out = sh(["git", "status", "--porcelain=v1", "-z", "-uall"], cwd=repo).stdout
    res: list[tuple[str, bool]] = []
    entries = out.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        res.append((path, code != "??"))
        if code[0] in "RC" and i < len(entries):  # rename/copy: next entry is the original path
            res.append((entries[i], True))
            i += 1
    return res


def restrict_changes(repo: Path, allowed: tuple[str, ...]) -> list[str]:
    """Revert every change outside the allowed prefixes (role separation enforced in code)."""
    reverted: list[str] = []
    for path, tracked in changed_paths(repo):
        if path.startswith((".autose-work/", ".venv")) or path.startswith(allowed):
            continue
        if tracked:
            git(repo, "checkout", "HEAD", "--", path, check=False)
        else:
            (repo / path).unlink(missing_ok=True)
        reverted.append(path)
    return reverted


def ruff_fix(repo: Path, paths: list[str]) -> tuple[bool, str]:
    """Auto-fix what ruff can fix (import order) in the given files, then report what is left."""
    if not paths:
        return True, ""
    py = str(repo / ".venv" / "bin" / "python")
    sh([py, "-m", "ruff", "check", "--fix", "-q", *paths], cwd=repo, check=False, timeout=300)
    p = sh([py, "-m", "ruff", "check", *paths], cwd=repo, check=False, timeout=300)
    return p.returncode == 0, p.stdout[-3000:]


def check_build(repo: Path, ruff_paths: tuple[str, ...] = ("src",)) -> Check:
    """Stage 3 check. ruff covers only what the implementer may edit (src/); test files are checked in stage 4."""
    py = str(repo / ".venv" / "bin" / "python")
    steps = [
        ("import", [py, "-c", "import mistune; print(mistune.__version__)"]),
        ("ruff", [py, "-m", "ruff", "check", *ruff_paths]),
        ("mypy (strict, src/mistune)", [py, "-m", "mypy"]),
    ]
    reasons, details = [], ""
    for label, cmd in steps:
        p = sh(cmd, cwd=repo, check=False, timeout=600)
        if p.returncode != 0:
            reasons.append(f"{label} failed")
            details += f"$ {' '.join(cmd[1:])}\n{p.stdout[-3000:]}{p.stderr[-1500:]}\n"
    return Check(not reasons, reasons, details)


# ---------------------------------------------------------------- stage 4: tests
def ac_coverage(repo: Path, base: str, acs: dict[str, str]) -> tuple[dict[str, list[str]], list[str]]:
    """Map AC id -> test functions (in files changed since base) whose name/docstring/body cites it."""
    files = [f for f in git(repo, "diff", "--name-only", base, "--", "tests/").splitlines() if f.endswith(".py")]
    files += [p for p, tracked in changed_paths(repo) if not tracked and p.startswith("tests/") and p.endswith(".py")]
    cover: dict[str, list[str]] = {a: [] for a in acs}
    tests: list[str] = []
    for rel in sorted(set(files)):
        path = repo / rel
        if not path.exists():
            continue
        src = path.read_text()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                seg = ast.get_source_segment(src, node) or ""
                tid = f"{rel}::{node.name}"
                tests.append(tid)
                for a in AC_ID_RE.findall(seg.replace("_", "-").upper()):
                    if a in cover:
                        cover[a].append(tid)
    return cover, tests


def run_pytest(repo: Path) -> tuple[bool, str, str]:
    py = str(repo / ".venv" / "bin" / "python")
    p = sh([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "-rf"], cwd=repo, check=False,
           timeout=900)
    summary = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
    return p.returncode == 0, summary, p.stdout[-6000:] + p.stderr[-1500:]
