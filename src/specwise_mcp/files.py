"""Reading local files and git revisions for tools that accept a path instead of the content."""
from __future__ import annotations

import subprocess
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError


def resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_file():
        raise ToolError(f"No such file: {p} (relative paths start from {Path.cwd()}).")
    return p


def read_text(path: str, max_bytes: int) -> str:
    p = resolve(path)
    size = p.stat().st_size
    if size > max_bytes:
        raise ToolError(f"{p} is {size:,} bytes; the limit is {max_bytes:,}.")
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"{p} is not UTF-8 text.")

def git_show(path: str, ref: str) -> str:
    """The file as it is at `ref` (a branch, tag or commit) in the git repository that contains it."""
    p = resolve(path).resolve()

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(p.parent), *args], check=False, capture_output=True, text=True)

    top = run("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise ToolError(f"{p} is not in a git repository.")
    rel = p.relative_to(Path(top.stdout.strip()).resolve()).as_posix()
    shown = run("show", f"{ref}:{rel}")
    if shown.returncode != 0:
        raise ToolError(f"Could not read {rel} at {ref!r}: {shown.stderr.strip()[:200]}")
    return shown.stdout
