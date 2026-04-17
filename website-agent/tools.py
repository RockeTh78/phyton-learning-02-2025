"""
Tool implementations for the website generator agent.

- create_file: Write a file to the project output directory
- read_file:   Read from the reference travel blog
- run_command: Execute a shell command with timeout
- test_endpoint: HTTP GET with timeout, returns status + body excerpt
- list_files:  Recursive file listing (tree-style)
- append_to_file: Append content to an existing file
"""

import os
import subprocess
import traceback
from pathlib import Path

import requests

REFERENCE_BLOG = Path("/Users/thomashoche/DEV/phyton-learning-02-2025/travel-blog")


# ─── create_file ──────────────────────────────────────────────────────────────

def create_file(path: str, content: str, project_dir: Path) -> str:
    """Write `content` to `path` (relative to project_dir). Creates parents."""
    try:
        target = project_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: created {path} ({len(content)} chars)"
    except Exception as exc:
        return f"ERROR creating {path}: {exc}\n{traceback.format_exc()}"


# ─── append_to_file ───────────────────────────────────────────────────────────

def append_to_file(path: str, content: str, project_dir: Path) -> str:
    """Append `content` to an existing file at `path` (relative to project_dir)."""
    try:
        target = project_dir / path
        if not target.exists():
            return f"ERROR: {path} does not exist. Use create_file first."
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)
        return f"OK: appended {len(content)} chars to {path}"
    except Exception as exc:
        return f"ERROR appending to {path}: {exc}"


# ─── read_file ────────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """
    Read a file from the REFERENCE travel blog.

    `path` is relative to the travel-blog root, e.g. "app.py" or "templates/base.html".
    Pass an absolute path to read from anywhere else.
    """
    try:
        target = Path(path) if Path(path).is_absolute() else REFERENCE_BLOG / path
        if not target.exists():
            return f"ERROR: {target} not found"
        text = target.read_text(encoding="utf-8")
        # Cap at 50 000 chars to keep context manageable
        if len(text) > 50_000:
            text = text[:50_000] + "\n... [truncated]"
        return text
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"


# ─── run_command ──────────────────────────────────────────────────────────────

def run_command(command: str, cwd: str | None = None) -> str:
    """
    Run `command` in a shell.
    `cwd` defaults to the current working directory.
    Returns combined stdout + stderr (truncated at 8 000 chars).
    Timeout: 120 s.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        if len(output) > 8_000:
            output = output[:8_000] + "\n... [truncated]"
        exit_label = "OK" if result.returncode == 0 else f"EXIT {result.returncode}"
        return f"[{exit_label}]\n{output}".strip()
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120 s"
    except Exception as exc:
        return f"ERROR running command: {exc}\n{traceback.format_exc()}"


# ─── test_endpoint ────────────────────────────────────────────────────────────

def test_endpoint(url: str) -> str:
    """
    HTTP GET `url` with a 10 s timeout.
    Returns status code and first 500 chars of the response body.
    """
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True)
        body = resp.text[:500]
        return f"STATUS {resp.status_code}\n{body}"
    except requests.exceptions.ConnectionError:
        return "ERROR: connection refused (server not running?)"
    except requests.exceptions.Timeout:
        return "ERROR: request timed out (10 s)"
    except Exception as exc:
        return f"ERROR: {exc}"


# ─── list_files ───────────────────────────────────────────────────────────────

def list_files(directory: str, project_dir: Path | None = None) -> str:
    """
    Recursively list files under `directory`.

    If `project_dir` is given:
      - paths starting with "/" are treated as absolute
      - otherwise relative to project_dir
    Falls back to the reference blog if the resolved path doesn't exist.
    """
    try:
        if Path(directory).is_absolute():
            base = Path(directory)
        elif project_dir and (project_dir / directory).exists():
            base = project_dir / directory
        else:
            base = REFERENCE_BLOG / directory

        if not base.exists():
            return f"ERROR: directory not found: {base}"

        lines: list[str] = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(base)
                lines.append(str(rel))
        return "\n".join(lines) if lines else "(empty)"
    except Exception as exc:
        return f"ERROR listing {directory}: {exc}"


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict, project_dir: Path) -> str:
    """Dispatch a tool call by name."""
    try:
        if name == "create_file":
            return create_file(inputs["path"], inputs["content"], project_dir)
        elif name == "append_to_file":
            return append_to_file(inputs["path"], inputs["content"], project_dir)
        elif name == "read_file":
            return read_file(inputs["path"])
        elif name == "run_command":
            return run_command(inputs["command"], inputs.get("cwd"))
        elif name == "test_endpoint":
            return test_endpoint(inputs["url"])
        elif name == "list_files":
            return list_files(inputs["directory"], project_dir)
        else:
            return f"ERROR: unknown tool '{name}'"
    except KeyError as exc:
        return f"ERROR: missing required parameter {exc} for tool '{name}'"
    except Exception as exc:
        return f"ERROR in tool '{name}': {exc}\n{traceback.format_exc()}"
