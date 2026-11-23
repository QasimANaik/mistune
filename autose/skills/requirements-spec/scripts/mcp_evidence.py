#!/usr/bin/env python3
"""Call a tool on an MCP server over stdio and save the exchange as an evidence record.

Used by the requirements-spec skill (workflow step 8) when the agent's own session does not expose
the MCP server's tools natively. It speaks the real Model Context Protocol (initialize -> tools/list
-> tools/call) through the official `mcp` Python SDK.

Usage:
    python3 mcp_evidence.py --ref REF-001 --out <spec-dir>/evidence \
        --tool fetch --arg url=https://example.org/page --arg max_length=8000

    python3 mcp_evidence.py --list-tools        # discovery only

The server is read from .mcp.json (key --server, default "fetch"): the nearest one in the current
directory or its parents, or the file given with --mcp-config.

Exit codes: 0 = result obtained; 2 = usage/config error; 3 = tool returned isError (do not retry the
same arguments; replace the source); 4 = server unavailable or timed out after retries.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("error: the 'mcp' Python package is required (pip install mcp)", file=sys.stderr)
    sys.exit(2)


def find_config(explicit):
    """Return the .mcp.json to use: --mcp-config, else the nearest one in the cwd or its parents."""
    if explicit:
        return Path(explicit).resolve()
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        if (d / ".mcp.json").is_file():
            return d / ".mcp.json"
    return None


def config_error(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def load_server(name, explicit_config=None):
    cfg = find_config(explicit_config)
    if cfg is None and not explicit_config and name == "fetch" and importlib.util.find_spec("mcp_server_fetch"):
        # No project config (e.g. a user-level skill used in a fresh project): run the installed package.
        return StdioServerParameters(command=sys.executable, args=["-m", "mcp_server_fetch"])
    if cfg is None or not cfg.is_file():
        config_error(f".mcp.json not found from {Path.cwd()} upwards (use --mcp-config <path>)")
    try:
        servers = json.loads(cfg.read_text())["mcpServers"]
    except (ValueError, KeyError) as e:
        config_error(f"{cfg} is not a valid MCP config ({type(e).__name__}: {e})")
    if name not in servers:
        config_error(f"server '{name}' not in {cfg} (have {sorted(servers)})")
    s = servers[name]
    command = s["command"]
    # A relative command such as ".venv/bin/mcp-server-fetch" is relative to the config file, not the cwd.
    if "/" in command and not Path(command).is_absolute():
        command = str((cfg.parent / command).resolve())
    return StdioServerParameters(command=command, args=s.get("args", []), env=s.get("env"))


def parse_args_kv(pairs):
    out = {}
    for p in pairs:
        k, _, v = p.partition("=")
        out[k] = int(v) if v.isdigit() else (v.lower() == "true" if v.lower() in ("true", "false") else v)
    return out


async def session_call(params, tool, arguments, list_only):
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = (await session.list_tools()).tools
            catalog = [{"name": t.name, "description": (t.description or "")[:300],
                        "input_schema": t.inputSchema} for t in tools]
            server = {"name": init.serverInfo.name, "version": init.serverInfo.version,
                      "protocol": init.protocolVersion}
            if list_only:
                return server, catalog, None
            if tool not in {t.name for t in tools}:
                raise LookupError(f"tool '{tool}' not offered by server; available: {[t.name for t in tools]}")
            result = await session.call_tool(tool, arguments)
            text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
            return server, catalog, {"is_error": bool(result.isError), "text": text}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="fetch")
    ap.add_argument("--mcp-config", help="path to .mcp.json (default: nearest one in the cwd or its parents)")
    ap.add_argument("--tool", default="fetch")
    ap.add_argument("--arg", action="append", default=[], help="tool argument as key=value (repeatable)")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--ref", help="evidence ID to assign, e.g. REF-001")
    ap.add_argument("--purpose", default="", help="which OQ/RSK/DEP this call is meant to inform")
    ap.add_argument("--out", help="directory for evidence records")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--retries", type=int, default=1, help="retries on timeout/transport failure")
    a = ap.parse_args()

    params = load_server(a.server, a.mcp_config)
    arguments = parse_args_kv(a.arg)
    if not a.list_tools and not (a.ref and a.out):
        print("error: --ref and --out are required for a tool call", file=sys.stderr)
        return 2

    attempts, last_err, started = 0, None, time.monotonic()
    outcome = None
    while attempts <= a.retries:
        attempts += 1
        try:
            outcome = asyncio.run(asyncio.wait_for(
                session_call(params, a.tool, arguments, a.list_tools), a.timeout))
            break
        except LookupError as e:          # wrong tool name: retrying will not help
            print(f"error: {e}", file=sys.stderr)
            return 2
        except (asyncio.TimeoutError, OSError, Exception) as e:  # transport, spawn, timeout
            last_err = f"{type(e).__name__}: {e}"
            print(f"attempt {attempts} failed: {last_err}", file=sys.stderr)
            if attempts <= a.retries:
                time.sleep(2 * attempts)

    if outcome is None:
        status = "UNAVAILABLE"
        server, catalog, result = None, None, None
    else:
        server, catalog, result = outcome
        status = "LISTED" if a.list_tools else ("TOOL-ERROR" if result["is_error"] else "OK")

    if a.list_tools:
        print(json.dumps({"server": server, "tools": catalog, "status": status,
                          "error": last_err}, indent=2))
        return 0 if status == "LISTED" else 4

    record = {
        "ref": a.ref,
        "purpose": a.purpose,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mcp_server": server,
        "server_config": {"command": params.command, "args": params.args},
        "tool": a.tool,
        "arguments": arguments,
        "status": status,
        "attempts": attempts,
        "duration_s": round(time.monotonic() - started, 2),
        "error": last_err if result is None else (result["text"][:500] if result["is_error"] else None),
        "content_sha256": hashlib.sha256(result["text"].encode()).hexdigest() if result else None,
        "content_chars": len(result["text"]) if result else 0,
        "content": result["text"] if result else None,
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{a.ref}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{a.ref}: status={status} attempts={attempts} chars={record['content_chars']} -> {path}")
    return {"OK": 0, "TOOL-ERROR": 3, "UNAVAILABLE": 4}[status]


if __name__ == "__main__":
    sys.exit(main())
