"""Pytest runner tool implementation."""

from __future__ import annotations
import asyncio
import sys
from dataclasses import dataclass

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


@dataclass
class PytestConfig:
    """Configuration for pytest execution."""
    path: str
    keyword: str | None = None
    markers: str | None = None
    verbose: bool = False
    timeout: int = 300
    coverage: bool = False
    coverage_source: str | None = None
    parallel: int | None = None
    collect_only: bool = False


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
    def parameters(self: PytestRunTool) -> dict[str, object]:
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
    def kind(self: PytestRunTool) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self: PytestRunTool,
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

        cmd = self._build_pytest_command(config)

        try:
            return await self._execute_pytest_command(cmd, config)
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error running pytest: {e}",
                success=False,
                error=str(e),
            )

    def _build_pytest_command(self: PytestRunTool, config: PytestConfig) -> list[str]:
        """Build the pytest command line arguments."""
        cmd = [sys.executable, "-m", "pytest", config.path]
        cmd_append = cmd.append
        cmd_extend = cmd.extend
        config_collect_only = config.collect_only

        if not config_collect_only:
            cmd_append("-x")
        if config.verbose:
            cmd_append("-v")
        if config.keyword:
            cmd_extend(["-k", config.keyword])
        if config.markers:
            cmd_extend(["-m", config.markers])
        if config.coverage:
            cov_arg = f"--cov={config.coverage_source}" if config.coverage_source else "--cov"
            cmd_extend([cov_arg, "--cov-report=term-missing"])
        if config.parallel is not None and config.parallel > 0:
            cmd_extend(["-n", str(config.parallel)])
        if config_collect_only:
            cmd_append("--collect-only")
            cmd_append("-q")

        return cmd

    async def _execute_pytest_command(self: PytestRunTool, cmd: list[str], config: PytestConfig) -> ToolResult:  # noqa: E501
        """Execute the pytest command and handle timeout."""
        create_subprocess_exec = asyncio.create_subprocess_exec
        PIPE = asyncio.subprocess.PIPE
        process = await create_subprocess_exec(
            *cmd,
            stdout=PIPE,
            stderr=PIPE,
        )

        config_timeout = config.timeout
        try:
            stdout, stderr = await self._communicate_with_timeout(process, config_timeout)
        except (TimeoutError, asyncio.TimeoutError):
            process.kill()
            await process.wait()
            return ToolResult(
                content=f"Tests timed out after {config_timeout}s",
                success=False,
                error=f"Timeout after {config_timeout}s",
            )
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise

        output = self._process_output(stdout, stderr)
        return self._create_result(output, process.returncode)

    async def _communicate_with_timeout(
        self: PytestRunTool, process: asyncio.subprocess.Process, timeout: int,
    ) -> tuple[bytes, bytes]:
        """Communicate with process with optional timeout."""
        effective_timeout: float | None = None if timeout == 0 else timeout
        if effective_timeout is not None:
            return await asyncio.wait_for(process.communicate(), timeout=effective_timeout)
        return await process.communicate()

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
