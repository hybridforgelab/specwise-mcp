"""End-to-end check of the Specwise server over stdio, as an MCP client would run it, against the real API.

    HFL_API_URL=https://specwise-api.hybridforgelab.com HFL_API_BEARER=... python scripts/e2e_stdio.py specwise

Needs either HFL_API_URL + HFL_API_BEARER (maintainers, no marketplace quota spent) or RAPIDAPI_KEY / API_MARKET_KEY.
Prints one line per check and exits non-zero on any failure. Never prints a key.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parent.parent
FIX = Path.home() / "code/ffrazao/specwise-action/tests/fixtures"
ENV_KEYS = ("HFL_API_URL", "HFL_API_BEARER", "RAPIDAPI_KEY", "API_MARKET_KEY", "HFL_MARKETPLACE", "PATH", "HOME")


def data(result):
    assert not result.is_error, result.content[0].text if result.content else "error"
    return json.loads(result.content[0].text)


def checks(name, tmp: Path):
    if name == "specwise":
        return [
            ("validate_openapi file", "validate_openapi", {"spec_path": str(FIX / "base.yaml")},
             lambda d: d["valid"] is True),
            ("diff_openapi files", "diff_openapi",
             {"base_path": str(FIX / "base.yaml"), "revision_path": str(FIX / "revision.yaml")},
             lambda d: d["breaking"] is True and d["summary"]["breaking"] == 3),
            ("validate_json_schema", "validate_json_schema",
             {"schema": '{"type": "object", "required": ["a"]}', "instance": "{}"},
             lambda d: d["valid"] is False and d["error_count"] == 1),
        ]
    raise SystemExit(f"unknown server {name}")


async def main(name):
    env = {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
    params = StdioServerParameters(command=str(ROOT / ".venv/bin/python"), args=["-m", "specwise_mcp.server"], env=env)
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            print(f"{name}: tools {tools}")
            for label, tool, args, ok in checks(name, Path(tmp)):
                try:
                    d = data(await session.call_tool(tool, args))
                    good = ok(d)
                    extra = f" quota_remaining={d['quota_remaining']}" if "quota_remaining" in d else ""
                    print(f"  {'PASS' if good else 'FAIL'} {label}{extra}")
                except Exception as exc:  # noqa: BLE001 - report and continue
                    good = False
                    print(f"  FAIL {label}: {str(exc)[:200]}")
                failures += not good
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main(sys.argv[1])) else 0)
