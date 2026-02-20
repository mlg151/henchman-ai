"""Environment context detection for agent awareness.

This module gathers environment information once at startup and formats it
into a structured block that is injected into every agent's system prompt.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Files that indicate a project type
_PROJECT_MARKERS: dict[str, str] = {
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "requirements.txt": "Python",
    "package.json": "Node.js",
    "tsconfig.json": "TypeScript",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "Makefile": "Make",
    "Dockerfile": "Docker",
    "docker-compose.yaml": "Docker Compose",
    "docker-compose.yml": "Docker Compose",
}

# Tools to probe for availability
_PROBE_TOOLS: list[str] = [
    "git",
    "python",
    "node",
    "ruff",
    "mypy",
    "pytest",
    "pip",
    "npm",
    "cargo",
    "go",
    "make",
    "docker",
]

_SUBPROCESS_TIMEOUT = 5


@dataclass(frozen=True)
class EnvironmentContext:
    """Snapshot of the runtime environment, gathered once at startup.

    Attributes:
        working_directory: Absolute path to the current working directory.
        git_root: Absolute path to the git repository root, or None.
        git_branch: Current git branch name, or None.
        git_status: Short git status summary, or None.
        os_info: OS name and release (e.g. "Linux 6.1.0").
        shell: User's default shell path, or None.
        python_version: Python version string.
        project_types: Detected project types and their marker files.
        directory_snapshot: Top-level directory listing.
        available_tools: CLI tools detected as available.
    """

    working_directory: str
    git_root: str | None
    git_branch: str | None
    git_status: str | None
    os_info: str
    shell: str | None
    python_version: str
    project_types: list[tuple[str, str]] = field(default_factory=list)
    directory_snapshot: list[str] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)


def _run_cmd(*args: str) -> str | None:
    """Run a subprocess command and return stripped stdout, or None on failure.

    Args:
        *args: Command and arguments.

    Returns:
        Stripped stdout string, or None if the command failed.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _detect_git_root(cwd: Path) -> str | None:
    """Detect the git repository root.

    Args:
        cwd: Current working directory.

    Returns:
        Absolute path to git root, or None.
    """
    output = _run_cmd("git", "-C", str(cwd), "rev-parse", "--show-toplevel")
    return output if output else None


def _detect_git_branch(cwd: Path) -> str | None:
    """Detect the current git branch.

    Args:
        cwd: Current working directory.

    Returns:
        Branch name, or None.
    """
    return _run_cmd("git", "-C", str(cwd), "branch", "--show-current")


def _detect_git_status(cwd: Path) -> str | None:
    """Detect a short git status summary.

    Args:
        cwd: Current working directory.

    Returns:
        Summarised git status string, or None.
    """
    output = _run_cmd("git", "-C", str(cwd), "status", "--short")
    if output is None:
        return None
    if not output:
        return "clean (no uncommitted changes)"

    lines = output.splitlines()
    if len(lines) <= 10:
        return output

    # Summarise by category
    modified = sum(1 for line in lines if line.strip().startswith("M"))
    added = sum(1 for line in lines if line.strip().startswith("A"))
    deleted = sum(1 for line in lines if line.strip().startswith("D"))
    untracked = sum(1 for line in lines if line.strip().startswith("?"))
    other = len(lines) - modified - added - deleted - untracked

    parts: list[str] = []
    if modified:
        parts.append(f"{modified} modified")
    if added:
        parts.append(f"{added} added")
    if deleted:
        parts.append(f"{deleted} deleted")
    if untracked:
        parts.append(f"{untracked} untracked")
    if other:
        parts.append(f"{other} other")
    return ", ".join(parts)


def _detect_project_types(root: Path) -> list[tuple[str, str]]:
    """Detect project types by checking for marker files.

    Args:
        root: Directory to inspect (typically git root or cwd).

    Returns:
        List of (project_type, marker_file) tuples, deduplicated by type.
    """
    seen_types: set[str] = set()
    results: list[tuple[str, str]] = []
    for marker, proj_type in _PROJECT_MARKERS.items():
        if (root / marker).exists() and proj_type not in seen_types:
            results.append((proj_type, marker))
            seen_types.add(proj_type)
    return results


def _get_directory_snapshot(directory: Path, max_entries: int = 30) -> list[str]:
    """Get a top-level directory listing.

    Args:
        directory: Directory to list.
        max_entries: Maximum number of entries to return.

    Returns:
        Sorted list of entry names (directories suffixed with /).
    """
    try:
        entries: list[str] = []
        for item in sorted(directory.iterdir()):
            if item.name.startswith("."):
                continue
            name = f"{item.name}/" if item.is_dir() else item.name
            entries.append(name)
            if len(entries) >= max_entries:
                break
        return entries
    except OSError:
        return []


def _detect_available_tools() -> list[str]:
    """Detect which common CLI tools are available on PATH.

    Returns:
        List of available tool names.
    """
    available: list[str] = []
    for tool in _PROBE_TOOLS:
        if shutil.which(tool) is not None:
            available.append(tool)
    return available


def gather_environment(cwd: Path | None = None) -> EnvironmentContext:
    """Gather a complete environment snapshot.

    This should be called once at startup. The result is a frozen dataclass
    that can be shared across all agents.

    Args:
        cwd: Working directory to inspect. Defaults to ``Path.cwd()``.

    Returns:
        A frozen :class:`EnvironmentContext` instance.
    """
    cwd = Path.cwd().resolve() if cwd is None else cwd.resolve()

    git_root = _detect_git_root(cwd)
    inspect_root = Path(git_root) if git_root else cwd

    return EnvironmentContext(
        working_directory=str(cwd),
        git_root=git_root,
        git_branch=_detect_git_branch(cwd),
        git_status=_detect_git_status(cwd),
        os_info=f"{platform.system()} {platform.release()}",
        shell=os.environ.get("SHELL"),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        project_types=_detect_project_types(inspect_root),
        directory_snapshot=_get_directory_snapshot(inspect_root),
        available_tools=_detect_available_tools(),
    )


def format_environment_block(ctx: EnvironmentContext) -> str:
    """Render an environment context as a structured prompt block.

    Args:
        ctx: The environment context to render.

    Returns:
        A string suitable for injection into a system prompt.
    """
    lines: list[str] = ["<environment_context>"]
    lines.append(f"* Working directory: {ctx.working_directory}")

    if ctx.git_root:
        lines.append(f"* Git repository root: {ctx.git_root}")
    if ctx.git_branch:
        lines.append(f"* Git branch: {ctx.git_branch}")
    if ctx.git_status:
        lines.append(f"* Git status: {ctx.git_status}")

    lines.append(f"* OS: {ctx.os_info}")

    if ctx.shell:
        lines.append(f"* Shell: {ctx.shell}")

    lines.append(f"* Python: {ctx.python_version}")

    if ctx.project_types:
        types_str = ", ".join(f"{ptype} ({marker})" for ptype, marker in ctx.project_types)
        lines.append(f"* Project type: {types_str}")

    if ctx.directory_snapshot:
        snapshot_str = " ".join(ctx.directory_snapshot)
        lines.append(f"* Directory contents (top-level): {snapshot_str}")

    if ctx.available_tools:
        lines.append(f"* Available tools: {', '.join(ctx.available_tools)}")

    lines.append("</environment_context>")
    return "\n".join(lines)
