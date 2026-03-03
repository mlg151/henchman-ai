"""Pytest runner tool implementation."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000

_DEFAULT_TIMEOUT_SECONDS = 300
"""Default subprocess timeout when none is explicitly provided."""


@dataclass
class PytestConfig:
    """Configuration for pytest execution."""
    path: str
    keyword: str | None = None
    markers: str | None = None
    verbose: bool = False
    timeout: int = _DEFAULT_TIMEOUT_SECONDS
    coverage: bool = False
    coverage_source: str | None = None
    parallel: int | None = None
    collect_only: bool = False


def _build_pytest_args(config: PytestConfig) -> list[str]:
    """Build the pytest command-line argument list from *config*.

    Extracted from ``PytestRunTool._build_pytest_command`` to eliminate
    Feature Envy — the method only accessed ``config``, not ``self``.

    Args:
        config: Populated pytest configuration.

    Returns:
        Argument list suitable for ``asyncio.create_subprocess_exec``.
    """
    cmd = [sys.executable, "-m", "pytest", config.path]

    if not config.collect_only:
        cmd.append("-x")
    if config.verbose:
        cmd.append("-v")
    if config.keyword:
        cmd.extend(["-k", config.keyword])
    if config.markers:
        cmd.extend(["-m", config.markers])
    if config.coverage:
        cov_arg = f"--cov={config.coverage_source}" if config.coverage_source else "--cov"
        cmd.extend([cov_arg, "--cov-report=term-missing"])
    if config.parallel is not None and config.parallel > 0:
        cmd.extend(["-n", str(config.parallel)])
    if config.collect_only:
        cmd.extend(["--collect-only", "-q"])

    return cmd


async def _run_pytest_subprocess(
    command: list[str],
    timeout: int,
) -> tuple[bytes, bytes, int | None]:
    """Execute a pytest subprocess and return ``(stdout, stderr, returncode)``.

    Extracted from ``PytestRunTool._execute_pytest_command`` to eliminate
    Feature Envy — the method heavily accessed ``asyncio`` internals.

    Args:
        command: Full argument list (including the Python interpreter).
        timeout: Seconds to wait before killing the process (0 = no limit).

    Returns:
        Tuple of ``(stdout_bytes, stderr_bytes, return_code)``.

    Raises:
        TimeoutError: When *timeout* is exceeded.
        asyncio.CancelledError: When the calling task is cancelled.
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    effective_timeout: float | None = None if timeout == 0 else timeout
    try:
        if effective_timeout is not None:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=effective_timeout,
            )
        else:
            stdout, stderr = await process.communicate()
    except (TimeoutError, asyncio.TimeoutError):
        process.kill()
        await process.wait()
        raise
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        raise

    return stdout, stderr, process.returncode


class PytestRunTool(Tool):
    """Run pytest on a specific test file or test function.

    Provides structured test execution with clear pass/fail output,
    more targeted than using the generic ``shell`` tool.
    Supports coverage collection, parallel execution, and test discovery.
    """

    @property
    def name(self: PytestRunTool) -> str:
        """Tool name."""
        return "pytest_run"

    @property
    def description(self: PytestRunTool) -> str:
        """Tool description."""
        return (
            "Run pytest on a specific test path (file, directory, or "
            "file::test_function). Supports keyword/marker filtering, "
            "verbose mode, coverage collection, parallel execution, "
            "and collect-only (test discovery without running)."
        )

    @property
    def parameters(self: PytestRunTool) -> dict[str, object]:  # noqa
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
                    "description": f"Timeout in seconds (default: {_DEFAULT_TIMEOUT_SECONDS})",
                    "default": _DEFAULT_TIMEOUT_SECONDS,
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
    def kind(self: PytestRunTool) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]  # noqa: PLR0913
        self: PytestRunTool,
        path: str = "",
        keyword: str | None = None,
        markers: str | None = None,
        *,
        verbose: bool = False,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
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
        config = PytestConfig(
            path=path,
            keyword=keyword,
            markers=markers,
            verbose=verbose,
            timeout=timeout,
            coverage=coverage,
            coverage_source=coverage_source,
            parallel=parallel,
            collect_only=collect_only,
        )

        return await self._run_pytest(config)

    async def _run_pytest(self: PytestRunTool, config: PytestConfig) -> ToolResult:
        """Run pytest with the given configuration."""
        if not config.path:
            return ToolResult(
                content="Error: No test path provided",
                success=False,
                error="Empty path",
            )

        cmd = _build_pytest_args(config)

        try:
            stdout, stderr, returncode = await _run_pytest_subprocess(cmd, config.timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return ToolResult(
                content=f"Tests timed out after {config.timeout}s",
                success=False,
                error=f"Timeout after {config.timeout}s",
            )
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except Exception as e:  # pragma: no cover  # noqa: BLE001
            return ToolResult(
                content=f"Error running pytest: {e}",
                success=False,
                error=str(e),
            )

        output = self._process_output(stdout, stderr)
        return self._create_result(output, returncode)

    def _process_output(self: PytestRunTool, stdout: bytes, stderr: bytes) -> str:
        """Process and combine stdout/stderr output."""
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")

        parts = []
        if stdout_text:
            parts.append(stdout_text)
        if stderr_text:
            parts.append(stderr_text)

        output = "\n".join(parts) if parts else "(no output)"
        return self._truncate_output(output)

    def _truncate_output(self: PytestRunTool, output: str) -> str:
        """Truncate output if it exceeds maximum length."""
        if len(output) > MAX_OUTPUT_CHARS:
            return output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
        return output

    def _create_result(self: PytestRunTool, output: str, returncode: int | None) -> ToolResult:
        """Create ToolResult from output and return code."""
        success = returncode == 0 if returncode is not None else False
        error = None if success else f"Tests failed (exit code {returncode})"

        return ToolResult(
            content=output,
            success=success,
            error=error,
        )
