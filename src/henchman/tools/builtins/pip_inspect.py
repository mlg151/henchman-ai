"""Pip inspect tool implementation."""

import asyncio
import sys

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


class PipInspectTool(Tool):
    """Query installed Python packages, versions, and dependency info.

    Provides structured package information without the overhead of
    constructing ``pip`` commands manually.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "pip_inspect"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Query installed Python packages. List all packages or inspect "
            "a specific package for version, dependencies, and location."
        )

    @property
    def parameters(self) -> dict[str, object]:
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
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
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
        if package:
            cmd = [sys.executable, "-m", "pip", "show", package]
        else:
            cmd = [sys.executable, "-m", "pip", "list", "--format=columns"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if process.returncode != 0:
                error_msg = stderr_text.strip() or stdout_text.strip()
                return ToolResult(
                    content=f"Error: {error_msg}",
                    success=False,
                    error=error_msg,
                )

            output = stdout_text.strip()
            if not output:
                return ToolResult(
                    content="No packages found",
                    success=True,
                )

            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
                )

            return ToolResult(content=output, success=True)

        except Exception as e:  # pragma: no cover  # noqa: BLE001
            return ToolResult(
                content=f"Error querying pip: {e}",
                success=False,
                error=str(e),
            )
