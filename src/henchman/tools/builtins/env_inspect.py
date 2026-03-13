"""Environment inspector tool implementation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

# Env vars that should never be exposed
SECRET_PATTERNS: frozenset[str] = frozenset(
    {
        "KEY",
        "SECRET",
        "TOKEN",
        "PASSWORD",
        "PASSWD",
        "CREDENTIAL",
        "AUTH",
        "PRIVATE",
    },
)


_MAX_ENV_VALUE_LENGTH = 200


class EnvInspectTool(Tool):
    """Inspect the Python environment and project setup.

    Reports Python version, virtualenv status, installed packages,
    project configuration, and available system tools — all in one call.
    """

    @property
    def name(self: EnvInspectTool) -> str:
        """Tool name."""
        return "env_inspect"

    @property
    def description(self: EnvInspectTool) -> str:
        """Tool description."""
        return (
            "Inspect the Python environment: version, virtualenv, installed packages, "
            "project type, available tools. Replaces multiple shell commands with one call."
        )

    @property
    def parameters(self: EnvInspectTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "cwd": {
                    "type": "string",
                    "description": "Working directory to inspect (default: current)",
                },
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific packages to check versions for",
                },
                "show_env_vars": {
                    "type": "boolean",
                    "description": "Include safe environment variables",
                    "default": False,
                },
                "show_path": {
                    "type": "boolean",
                    "description": "Include sys.path entries",
                    "default": False,
                },
            },
        }

    @property
    def kind(self: EnvInspectTool) -> ToolKind:
        """Tool kind - read-only inspection."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]  # noqa: C901, PLR0912
        self: EnvInspectTool,
        cwd: str | None = None,
        packages: list[str] | None = None,
        *,
        show_env_vars: bool = False,
        show_path: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Inspect the environment.

        Args:
            cwd: Working directory to inspect.
            packages: Specific packages to check.
            show_env_vars: Include environment variables.
            show_path: Include sys.path.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with environment information.
        """
        parts: list[str] = []
        append_part = parts.append
        work_dir = Path(cwd) if cwd else Path.cwd()

        # Python info
        append_part("Python Environment:")
        append_part(f"  Version: {sys.version.split()[0]}")
        append_part(f"  Executable: {sys.executable}")
        append_part(f"  Platform: {sys.platform}")

        # Virtualenv
        venv = os.environ.get("VIRTUAL_ENV", "")
        conda = os.environ.get("CONDA_DEFAULT_ENV", "")
        if venv:
            append_part(f"  Virtual env: {venv}")
        elif conda:
            append_part(f"  Conda env: {conda}")
        else:
            append_part("  Virtual env: (none)")

        # Package versions
        if packages:
            append_part("\nPackage Versions:")
            for pkg_name in packages:
                version = self._get_package_version(pkg_name)
                append_part(f"  {pkg_name}: {version}")

        # Project detection
        append_part(f"\nProject ({work_dir.name}):")
        project_files = self._detect_project(work_dir)
        if project_files:
            for pf in project_files:
                append_part(f"  {pf}")
        else:
            append_part("  (no project files detected)")

        # sys.path
        if show_path:
            append_part("\nsys.path:")
            for p in sys.path:
                if p:
                    append_part(f"  {p}")

        # Environment variables (filtered)
        if show_env_vars:
            append_part("\nEnvironment Variables (safe):")
            safe_vars = self._get_safe_env_vars()
            for key, value in sorted(safe_vars.items()):
                append_part(f"  {key}={value}")
            if not safe_vars:
                append_part("  (none)")

        return ToolResult(content="\n".join(parts), success=True)

    def _get_package_version(self: EnvInspectTool, name: str) -> str:
        """Get installed version of a package.

        Args:
            name: Package name.

        Returns:
            Version string or 'not installed'.
        """
        try:
            from importlib.metadata import version  # noqa: PLC0415

            return version(name)
        except Exception:  # noqa: BLE001
            return "not installed"

    def _detect_project(self: EnvInspectTool, directory: Path) -> list[str]:
        """Detect project type from config files.

        Args:
            directory: Directory to inspect.

        Returns:
            List of detected project indicators.
        """
        indicators: list[str] = []
        checks = {
            "pyproject.toml": "Python (pyproject.toml)",
            "setup.py": "Python (setup.py)",
            "setup.cfg": "Python (setup.cfg)",
            "requirements.txt": "Python (requirements.txt)",
            "package.json": "Node.js (package.json)",
            "Cargo.toml": "Rust (Cargo.toml)",
            "go.mod": "Go (go.mod)",
            "Makefile": "Makefile present",
            "Dockerfile": "Docker",
            "docker-compose.yaml": "Docker Compose",
            "docker-compose.yml": "Docker Compose",
            ".git": "Git repository",
        }

        for filename, label in checks.items():
            if (directory / filename).exists():
                indicators.append(label)

        return indicators

    def _get_safe_env_vars(self: EnvInspectTool) -> dict[str, str]:
        """Get environment variables, filtering out secrets.

        Returns:
            Dict of safe environment variable name/value pairs.
        """
        safe: dict[str, str] = {}
        for key, value in os.environ.items():
            upper = key.upper()
            if any(pattern in upper for pattern in SECRET_PATTERNS):
                continue
            # Also skip very long values
            if len(value) > _MAX_ENV_VALUE_LENGTH:
                safe[key] = value[:_MAX_ENV_VALUE_LENGTH] + "..."
            else:
                safe[key] = value
        return safe
