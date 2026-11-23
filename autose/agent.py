"""Run one headless Gemini CLI agent call with a fresh context, a role policy and a stripped environment."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import TOOL, log, redact, write, write_json

# Policies are copied once, before any agent runs, so an agent editing autose/policies/ cannot
# widen its own permissions for later calls.
_POLICY_DIR = Path(tempfile.mkdtemp(prefix="autose-policies-"))
for _p in (TOOL / "policies").glob("*.toml"):
    shutil.copy(_p, _POLICY_DIR / _p.name)


@dataclass
class AgentResult:
    name: str
    model: str
    response: str
    exit_code: int
    timed_out: bool
    duration_s: float
    tool_calls: int
    denied: int
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return int(self.stats.get("total_tokens") or 0)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _agent_env(home: Path) -> dict[str, str]:
    """Only what the agent needs. No GH_TOKEN, no GITHUB_*, no ACTIONS_* variables."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "GEMINI_CLI_TRUST_WORKSPACE": "true",
        "UV_NO_SYNC": "1",  # `uv run` must not re-sync (and drop test deps) inside the agent
        "UV_OFFLINE": "1",
        "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(Path.home() / ".cache" / "uv")),
        "UV_PYTHON": os.environ.get("UV_PYTHON", ""),
        "LANG": "C.UTF-8",
        "TERM": "dumb",
        "NO_COLOR": "1",
    }
    return {k: v for k, v in env.items() if v}


def _parse_stream(out: str) -> tuple[str, dict[str, Any], int, int]:
    """Return (final assistant text, stats, tool calls, denied tool results) from stream-json output."""
    buf: list[str] = []
    stats: dict[str, Any] = {}
    tools = denied = 0
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "message" and ev.get("role") == "assistant":
            buf.append(str(ev.get("content", "")))
        elif t == "tool_use":
            tools += 1
            buf = []  # keep only the text after the last tool call
        elif t == "tool_result":
            blob = json.dumps(ev).lower()
            if ev.get("status") == "error" and ("denied" in blob or "policy" in blob):
                denied += 1
        elif t == "result":
            stats = ev.get("stats") or {}
    return "".join(buf).strip(), stats, tools, denied


def run_agent(
    name: str,
    prompt_text: str,
    model: str,
    policy: str,
    repo: Path,
    out: Path,
    cfg: dict[str, Any],
    skills: tuple[str, ...] = (),
    fallback_model: str | None = None,
) -> AgentResult:
    home = Path(tempfile.mkdtemp(prefix=f"agent-{name}-"))
    gem = home / ".gemini"
    write_json(
        gem / "settings.json",
        {
            "model": {"maxSessionTurns": cfg["budgets"]["max_session_turns"]},
            "privacy": {"usageStatisticsEnabled": False},
        },
    )
    for s in skills:
        shutil.copytree(TOOL / "skills" / s, gem / "skills" / s)
    write(out / "prompts" / f"{name}.md", prompt_text)
    cmd = [
        "gemini", "-p", prompt_text, "-m", model,
        "--output-format", "stream-json",
        "--approval-mode", "default",
        "--admin-policy", str(_POLICY_DIR / policy),
    ]
    log(f"agent {name}: model={model} policy={policy} skills={list(skills)}")
    t0 = time.time()
    timed_out = False
    try:
        p = subprocess.run(
            cmd, cwd=repo, env=_agent_env(home), text=True, capture_output=True,
            timeout=cfg["budgets"]["agent_timeout_s"],
        )
        stdout, stderr, code = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        code = -1
    dur = time.time() - t0
    write(out / "transcripts" / f"{name}.jsonl", redact(stdout))
    write(out / "transcripts" / f"{name}.stderr.txt", redact(stderr[-20000:]))
    response, stats, tools, denied = _parse_stream(stdout)
    res = AgentResult(name, model, response, code, timed_out, round(dur, 1), tools, denied, stats)
    write_json(
        out / "usage" / f"{name}.json",
        {
            "name": name, "model": model, "exit_code": code, "timed_out": timed_out,
            "duration_s": res.duration_s, "tool_calls": tools, "denied_tool_calls": denied, "stats": stats,
        },
    )
    log(f"agent {name}: exit={code} timeout={timed_out} {dur:.0f}s tools={tools} tokens={res.total_tokens}")
    if not res.ok and tools == 0 and fallback_model and fallback_model != model:
        log(f"agent {name}: failed before doing any work ({redact(stderr[-300:])!r}); retrying with {fallback_model}")
        return run_agent(f"{name}-fallback", prompt_text, fallback_model, policy, repo, out, cfg, skills, None)
    return res
