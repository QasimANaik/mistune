"""Shared helpers for AutoSE. Deterministic code only; no LLM calls here."""

import json
import os
import re
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any

TOOL = Path(__file__).resolve().parent  # the autose/ directory (always from the default branch)

_SECRET_RE = re.compile(r"(gh[opsu]_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{20,}|x-access-token:[^@\s]+)")


def redact(text: str) -> str:
    return _SECRET_RE.sub("***", text)


def log(msg: str) -> None:
    print(f"[autose] {redact(msg)}", flush=True)


def sh(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    log("$ " + " ".join(cmd)[:300])
    p = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"command failed ({p.returncode}): {' '.join(cmd)}\n{redact(p.stdout[-3000:])}\n{redact(p.stderr[-3000:])}"
        )
    return p


def gh(args: list[str], cwd: Path | None = None, check: bool = True, retries: int = 3) -> subprocess.CompletedProcess[str]:
    """Run the gh CLI (uses GH_TOKEN from the job env). Retries transient failures."""
    last: subprocess.CompletedProcess[str] | None = None
    for i in range(retries):
        last = sh(["gh", *args], cwd=cwd, check=False)
        if last.returncode == 0:
            return last
        time.sleep(4 * (i + 1))
    assert last is not None
    if check:
        raise RuntimeError(f"gh {' '.join(args)} failed: {redact(last.stderr[-2000:])}")
    return last


def git(repo: Path, *args: str, check: bool = True) -> str:
    return sh(["git", *args], cwd=repo, check=check).stdout.strip()


def git_raw(repo: Path, *args: str) -> str:
    """Unstripped output, for patches (stripping breaks a trailing context line)."""
    return sh(["git", *args], cwd=repo).stdout


def load_config(variant: str = "baseline") -> dict[str, Any]:
    cfg = tomllib.loads((TOOL / "config.toml").read_text())
    variants = cfg.get("variants", {})
    if variant not in variants:
        raise SystemExit(f"unknown variant {variant!r}; known: {sorted(variants)}")
    v = dict(variants[variant])
    cfg["variant_name"] = variant
    cfg["v"] = {
        "use_architecture_doc": v.get("use_architecture_doc", True),
        "reviewer_model": v.get("reviewer_model", cfg["models"]["reviewer"]),
        "reviewer_policy": v.get("reviewer_policy", "reviewer.toml"),
        "reviewer_prompt": v.get("reviewer_prompt", "reviewer.md"),
    }
    return cfg


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def write_json(path: Path, data: Any) -> Path:
    return write(path, json.dumps(data, indent=2, default=str) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def set_output(name: str, value: str) -> None:
    """Write a GitHub Actions step output (no-op when run locally)."""
    out = os.environ.get("GITHUB_OUTPUT")
    log(f"output {name}={value}")
    if out:
        with open(out, "a") as f:
            f.write(f"{name}={value}\n")


def prompt(name: str, **values: str) -> str:
    """Load autose/prompts/<name> and fill {{placeholders}} (missing ones become empty)."""
    text = (TOOL / "prompts" / name).read_text()
    preamble = (TOOL / "prompts" / "_preamble.md").read_text()
    text = text.replace("{{PREAMBLE}}", preamble)
    for k, val in values.items():
        text = text.replace("{{" + k + "}}", val)
    return re.sub(r"\{\{[A-Z_]+\}\}", "", text)


def run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"{server}/{repo}/actions/runs/{run_id}" if run_id else "(local run)"


def untrusted(tag: str, text: str, **attrs: str) -> str:
    """Wrap untrusted text in tags; neutralise any closing tag inside it."""
    safe = text.replace(f"</{tag}", f"<\\/{tag}")
    attr = "".join(f' {k}="{v.replace(chr(34), "")}"' for k, v in attrs.items())
    return f"<{tag}{attr}>\n{safe}\n</{tag}>"
