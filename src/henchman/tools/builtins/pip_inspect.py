"""Pip inspect tool implementation."""

from __future__ import annotations

import asyncio
import sys

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000
_PIP_SUBPROCESS_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _build_pip_command(package: str | None) -> list[str]:
    """Return the pip command for listing all packages or inspecting one.

    Args:
        package: Specific package name, or None to list all.

    Returns:
        Command list for asyncio subprocess.
    """
    if package:
        return [sys.executable, "-m", "pip", "show", package]
    return [sys.executable, "-m", "pip", "list", "--format=columns"]


async def _run_pip_command(cmd: list[str]) -> tuple[bytes, bytes, int | None]:
    """Execute a pip subprocess and return (stdout, stderr, returncode).

    Args:
        cmd: Full command list including the Python interpreter.

    Returns:
        Tuple of (stdout_bytes, stderr_bytes, return_code).
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=_PIP_SUBPROCESS_TIMEOUT,
    )
    return stdout, stderr, process.returncode


def _build_pip_output_result(stdout: bytes, stderr: bytes, returncode: int | None) -> ToolResult:
    """Decode pip output and build a ToolResult.

    Args:
        stdout: Raw stdout bytes from pip subprocess.
        stderr: Raw stderr bytes from pip subprocess.
        returncode: Process return code.

    Returns:
        ToolResult with package information or an error message.
    """
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if returncode != 0:
        error_msg = stderr_text.strip() or stdout_text.strip()
        return ToolResult(
            content=f"Error: {error_msg}",
            success=False,
            error=error_msg,
        )

    output = stdout_text.strip()
    if not output:
        return ToolResult(content="No packages found", success=True)

    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"

    return ToolResult(content=output, success=True)


class PipInspectTool(Tool):
    """Query installed Python packages, versions, and dependency info.

    Provides structured package information without the overhead of
    constructing ``pip`` commands manually.
    """

    @property
    def name(self: PipInspectTool) -> str:
        """Tool name."""
        return "pip_inspect"

    @property
    def description(self: PipInspectTool) -> str:
        """Tool description."""
        return (
            "Query installed Python packages. List all packages or inspect "
            "a specific package for version, dependencies, and location."
        )

    @property
    def parameters(self: PipInspectTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": (
                        "Specific package name to inspect. Omit to list all installed packages."
                    ),
                },
            },
        }

    @property
    def kind(self: PipInspectTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: PipInspectTool,
        package: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Query pip for package information.

        Args:
            package: Specific package to inspect, or None for full list.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with package information.
        """
        cmd = _build_pip_command(package)
        try:
            stdout, stderr, returncode = await _run_pip_command(cmd)
            return _build_pip_output_result(stdout, stderr, returncode)
        except Exception as e:  # pragma: no cover  # noqa: BLE001
            return ToolResult(
                content=f"Error querying pip: {e}",
                success=False,
                error=str(e),
            )
