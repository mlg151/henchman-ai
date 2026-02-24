"""Pytest runner tool implementation."""

import asyncio
import sys

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


class PytestRunTool(Tool):
    """Run pytest on a specific test file or test function.

    Provides structured test execution with clear pass/fail output,
    more targeted than using the generic ``shell`` tool.
    Supports coverage collection, parallel execution, and test discovery.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "pytest_run"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Run pytest on a specific test path (file, directory, or "
            "file::test_function). Supports keyword/marker filtering, "
            "verbose mode, coverage collection, parallel execution, "
            "and collect-only (test discovery without running)."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": ("Test path: file, directory, or file::test_name"),
                },
                "keyword": {
                    "type": "string",
                    "description": "Filter tests by keyword expression (-k)",
                },
                "markers": {
                    "type": "string",
                    "description": "Filter tests by marker expression (-m)",
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Enable verbose output (-v)",
                    "default": False,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 300)",
                    "default": 300,
                },
                "coverage": {
                    "type": "boolean",
                    "description": "Collect coverage with --cov",
                    "default": False,
                },
                "coverage_source": {
                    "type": "string",
                    "description": "Source directory for --cov (e.g. 'src')",
                },
                "parallel": {
                    "type": "integer",
                    "description": "Number of parallel workers (-n, requires pytest-xdist)",
                },
                "collect_only": {
                    "type": "boolean",
                    "description": "List matching tests without running them",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        keyword: str | None = None,
        markers: str | None = None,
        verbose: bool = False,
        timeout: int = 300,
        coverage: bool = False,
        coverage_source: str | None = None,
        parallel: int | None = None,
        collect_only: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Run pytest on the given path.

        Args:
            path: Test path (file, directory, or file::test_name).
            keyword: Optional keyword filter (-k).
            markers: Optional marker filter (-m).
            verbose: Enable verbose output.
            timeout: Execution timeout in seconds.
            coverage: Collect coverage data.
            coverage_source: Source directory for coverage.
            parallel: Number of parallel workers.
            collect_only: List tests without running them.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with test results.
        """
        if not path:
            return ToolResult(
                content="Error: No test path provided",
                success=False,
                error="Empty path",
            )

        cmd = [sys.executable, "-m", "pytest", path]
        if not collect_only:
            cmd.append("-x")
        if verbose:
            cmd.append("-v")
        if keyword:
            cmd.extend(["-k", keyword])
        if markers:
            cmd.extend(["-m", markers])
        if coverage:
            cov_arg = f"--cov={coverage_source}" if coverage_source else "--cov"
            cmd.extend([cov_arg, "--cov-report=term-missing"])
        if parallel is not None and parallel > 0:
            cmd.extend(["-n", str(parallel)])
        if collect_only:
            cmd.append("--collect-only")
            cmd.append("-q")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            effective_timeout: float | None = None if timeout == 0 else timeout
            try:
                if effective_timeout is not None:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=effective_timeout,
                    )
                else:
                    stdout, stderr = await process.communicate()
            except (TimeoutError, asyncio.TimeoutError):
                process.kill()
                await process.wait()
                return ToolResult(
                    content=f"Tests timed out after {timeout}s",
                    success=False,
                    error=f"Timeout after {timeout}s",
                )
            except asyncio.CancelledError:
                process.kill()
                await process.wait()
                raise

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            parts = []
            if stdout_text:
                parts.append(stdout_text)
            if stderr_text:
                parts.append(stderr_text)

            output = "\n".join(parts) if parts else "(no output)"

            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
                )

            return ToolResult(
                content=output,
                success=process.returncode == 0,
                error=(
                    f"Tests failed (exit code {process.returncode})"
                    if process.returncode != 0
                    else None
                ),
            )

        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error running pytest: {e}",
                success=False,
                error=str(e),
            )
