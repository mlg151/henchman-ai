"""Helpers for behavioral evaluations.

This module provides the core infrastructure for running behavioral evals,
including the EvalTestRig for setting up test environments and the eval_test
decorator for controlling test execution based on policy.

Behavioral evals use REAL LLM providers to test actual agent behavior.
Configure the provider via environment variables:
    EVAL_PROVIDER=registered-provider-name (default: deepseek)
    EVAL_MODEL=model-name (optional, uses provider default)
    EVAL_BASE_URL=http://localhost:8080/v1 (for openai_compat)
    DEEPSEEK_API_KEY=your-key (or ANTHROPIC_API_KEY, etc.)
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import shutil
import sys
import tempfile
from collections.abc import AsyncGenerator, Awaitable, Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal

import pytest

from evals.models import EvalResult as EvalResult
from evals.models import EventObserver
from evals.models import ToolLog as ToolLog
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.agent import Agent
from henchman.core.agent_config import AgentConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.providers.factory import create_configured_provider
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from evals.team_runtime import TeamEvalRuntime
    from henchman.agents.orchestrator import Orchestrator

# Eval policy types
EvalPolicy = Literal["ALWAYS_PASSES", "USUALLY_PASSES"]

_ENGINEER_EVAL_CONTEXT = (
    "This is a standalone evaluation of the engineer role in a temporary project. "
    "No leader, teammates, delegation, or shared team state is active. Complete the "
    "user's task directly using the available tools."
)


async def verify_python(workspace: Path, code: str, *, timeout: float = 5.0) -> None:
    """Run independent assertions with bounded diagnostics and an execution receipt.

    Ignore inherited Python options, including optimization that disables asserts.
    This executes project code in a child process; it is not an OS sandbox.
    """
    from henchman.tools.subprocess_utils import run_bounded_subprocess

    bootstrap = (
        "import pathlib, sys\n"
        "receipt = pathlib.Path(sys.argv[2])\n"
        "exec(compile(sys.argv[1], '<evaluation-check>', 'exec'), {'__name__': '__main__'})\n"
        "receipt.write_text('completed', encoding='utf-8')\n"
    )
    with tempfile.TemporaryDirectory(prefix="henchman-eval-check-") as directory:
        receipt = Path(directory) / "completed"
        completed = await run_bounded_subprocess(
            [sys.executable, "-E", "-X", "utf8", "-c", bootstrap, code, str(receipt)],
            cwd=workspace, timeout=timeout, max_output_bytes=8192,
        )
        if completed.returncode != 0:
            diagnostics = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
            truncation = " [diagnostics truncated]" if (
                completed.stdout_truncated or completed.stderr_truncated
            ) else ""
            raise AssertionError(f"Independent Python verification exit {completed.returncode}{truncation}:\n{diagnostics}")
        assert receipt.is_file() and receipt.read_text(encoding="utf-8") == "completed", (
            "Independent Python verification exited without completing its assertions"
        )


def get_eval_provider() -> ModelProvider:
    """Get the provider to use for evals based on environment.

    Uses EVAL_PROVIDER env var (default: deepseek).
    Explicit selection is authoritative; unrelated credentials never select a provider.

    Returns:
        A configured ModelProvider instance.

    Raises:
        RuntimeError: If no provider could be configured.
    """
    provider_name = os.environ.get("EVAL_PROVIDER", "deepseek").lower()
    model = os.environ.get("EVAL_MODEL")

    settings = ProviderSettings(default=provider_name)
    base_url = os.environ.get("EVAL_BASE_URL")
    if base_url is not None:
        if provider_name != "openai_compat":
            raise RuntimeError("EVAL_BASE_URL requires EVAL_PROVIDER=openai_compat")
        settings.openai_compat["base_url"] = base_url
    try:
        return create_configured_provider(settings, provider_name=provider_name, model=model)
    except ValueError as exc:
        raise RuntimeError(f"Cannot configure eval provider '{provider_name}': {exc}") from exc


class MockProvider(ModelProvider):
    """Mock provider that returns scripted responses for evals.

    This provider can be configured with specific responses to return,
    allowing deterministic testing of agent behavior.
    """

    def __init__(
        self,
        responses: list[str | list[ToolCall]] | None = None,
        model: str = "mock-model",
    ) -> None:
        """Initialize mock provider.

        Args:
            responses: List of responses to return in order.
                      Can be strings (content) or lists of ToolCalls.
            model: Model name to report.
        """
        self._responses = responses or []
        self._response_index = 0
        self._model = model
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        """Get the provider name."""
        return "mock"

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._model

    def add_response(self, response: str | list[ToolCall]) -> None:
        """Add a response to the queue."""
        self._responses.append(response)

    def set_tool_response(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        follow_up: str = "Done.",
    ) -> None:
        """Configure provider to call a tool then respond.

        Args:
            tool_name: Name of the tool to call.
            arguments: Arguments to pass to the tool.
            follow_up: Text response after tool result.
        """
        tool_call = ToolCall(
            id=f"call_{len(self._responses)}",
            name=tool_name,
            arguments=deepcopy(arguments),
        )
        self._responses.append([tool_call])
        self._responses.append(follow_up)

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a mock response."""
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )

        if self._response_index >= len(self._responses):
            # Default: just acknowledge
            yield StreamChunk(content="I understand.", finish_reason=FinishReason.STOP)
            return

        response = self._responses[self._response_index]
        self._response_index += 1

        if isinstance(response, str):
            # Text response
            yield StreamChunk(content=response, finish_reason=FinishReason.STOP)
        elif isinstance(response, list):
            # Tool calls
            yield StreamChunk(tool_calls=response, finish_reason=FinishReason.TOOL_CALLS)


class EvalTestRig:
    """Test rig for running behavioral evaluations.

    Provides a temporary workspace for testing agent behavior, including:
    - Temporary directory for file operations
    - Tool call logging
    - Real LLM provider for actual behavior testing
    - Assertion helpers

    Example:
        >>> rig = EvalTestRig()
        >>> rig.setup()
        >>> rig.create_file("test.txt", "Hello")
        >>> result = await rig.run("Read test.txt")
        >>> assert rig.tool_was_called("read_file")
        >>> rig.cleanup()
    """

    def __init__(
        self,
        provider: ModelProvider | None = None,
        system_prompt: str | None = None,
        config: AgentConfig | None = None,
        *,
        profile: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialize the test rig.

        Args:
            provider: Provider to use. If None, uses get_eval_provider().
            system_prompt: System prompt for the agent.
            config: Optional core-agent configuration, copied for each setup.
            profile: basic, engineer or team; None uses EVAL_PROFILE, default basic.
            settings: Copied production settings, supported only by the team profile.
        """
        self._profile = profile if profile is not None else os.environ.get("EVAL_PROFILE", "basic")
        if self._profile not in ("basic", "engineer", "team"):
            raise ValueError(f"Unknown evaluation profile: {self._profile}")
        if settings is not None and self._profile != "team":
            raise ValueError("Evaluation settings require the team profile")
        if self._profile == "team" and (config is not None or system_prompt is not None):
            raise ValueError("The team profile rejects custom core config or system prompt")
        self._settings = (
            settings.model_copy(deep=True) if settings is not None else Settings()
        ) if self._profile == "team" else None
        self._config = replace(config) if config is not None else AgentConfig()
        if self._profile == "team":
            self._system_prompt = ""
        elif self._profile == "engineer":
            if system_prompt is not None or self._config.system_prompt:
                raise ValueError("The engineer profile requires its canonical system prompt")
            from henchman.agents.prompts import get_agent_prompt

            self._system_prompt = get_agent_prompt(
                "engineer", environment_context=_ENGINEER_EVAL_CONTEXT,
            )
        else:
            self._system_prompt = (
                system_prompt if system_prompt is not None
                else self._config.system_prompt or self._get_eval_system_prompt()
            )
        self._provider = provider or get_eval_provider()
        self._providers = [self._provider]
        self._temp_dir: Path | None = None
        self._tool_logs: list[ToolLog] = []
        self._events: list[AgentEvent] = []
        self._agent: Agent | None = None
        self._team_runtime: TeamEvalRuntime | None = None
        self._original_cwd: Path | None = None
        self._run_outcomes: list[tuple[bool, str | None]] = []

    def _get_eval_system_prompt(self) -> str:
        """Get the system prompt for behavioral evals."""
        return """You are a helpful coding assistant being evaluated.

You have access to tools for file operations, shell commands, and web fetching.
When the user asks you to perform a task:
1. Use the appropriate tool(s) to complete it
2. Be concise in your responses
3. If unsure, ask for clarification rather than guessing

The current working directory contains test files for this evaluation."""

    @property
    def test_dir(self) -> Path:
        """Get the temporary test directory."""
        if self._temp_dir is None:
            raise RuntimeError("Test rig not set up. Call setup() first.")
        return self._temp_dir

    @property
    def provider(self) -> ModelProvider:
        """Get the provider."""
        return self._provider

    @property
    def providers(self) -> list[ModelProvider]:
        """Snapshot caller-owned providers, retained even after failed setup cleanup."""
        current = self._team_runtime.providers if self._team_runtime is not None else []
        for provider in current:
            if not any(existing is provider for existing in self._providers):
                self._providers.append(provider)
        return list(self._providers)

    @property
    def orchestrator(self) -> Orchestrator:
        """Return the initialized production team; other profiles have no team."""
        if self._profile != "team":
            raise RuntimeError("The orchestrator is available only for the team profile")
        if self._team_runtime is None:
            raise RuntimeError("Test rig not set up. Call setup() first.")
        return self._team_runtime.orchestrator

    @property
    def profile_metadata(self) -> dict[str, Any]:
        """Describe the initialized profile without prompts or provider credentials."""
        if self._agent is None:
            raise RuntimeError("Test rig not set up. Call setup() first.")
        if self._team_runtime is not None:
            return self._team_runtime.metadata
        return {
            "profile": self._profile,
            "scope": "single_agent",
            "tool_names": sorted(self._agent.tool_registry.list_tools()),
            "prompt_sha256": hashlib.sha256(self._system_prompt.encode("utf-8")).hexdigest(),
            "prompt_chars": len(self._system_prompt),
            "max_tokens": self._agent.max_tokens,
            "context_window": self._agent.context_window,
        }

    def setup(self, test_name: str = "eval") -> None:
        """Set up the test environment.

        Args:
            test_name: Name of the test (used for logging).
        """
        # Create temp directory
        self._temp_dir = Path(tempfile.mkdtemp(prefix=f"eval_{test_name}_"))
        self._original_cwd = Path.cwd()
        os.chdir(self._temp_dir)

        # Reset state
        self._tool_logs = []
        self._events = []
        self._run_outcomes = []

        try:
            if self._profile == "team":
                from evals.team_runtime import TeamEvalRuntime

                assert self._settings is not None
                self._team_runtime = TeamEvalRuntime(
                    self._provider, self._settings, self.test_dir,
                    self._events, self._tool_logs,
                )
                self._team_runtime.initialize_roles()
                self._providers = self.providers
                self._agent = self._team_runtime.orchestrator.tech_lead
                return
            registry = self._create_wrapped_registry()
            # AgentPool does not accept the full core AgentConfig. Reuse its
            # canonical prompt/preset/scope composition, preserving every knob.
            self._agent = Agent(
                provider=self._provider,
                tool_registry=registry,
                config=replace(self._config, system_prompt=self._system_prompt),
            )
        except BaseException:
            self.cleanup()
            raise

    def _create_wrapped_registry(self) -> ToolRegistry:
        """Create the profile's production tools without changing their policies."""
        if self._profile == "engineer":
            return self._create_engineer_registry()
        from henchman.tools.builtins import (
            AskUserTool,
            EditFileTool,
            GlobTool,
            GrepTool,
            LsTool,
            ReadFileTool,
            ShellTool,
            WebFetchTool,
            WriteFileTool,
        )

        registry = ToolRegistry()

        # Use production tools; authoritative outcomes come from runtime events.
        builtin_tools = [
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            LsTool(),
            GlobTool(),
            GrepTool(),
            ShellTool(),
            WebFetchTool(),
            AskUserTool(),
        ]

        for tool in builtin_tools:
            registry.register(tool)

        # Auto-approve all tools for evals
        for tool_name in registry._tools:
            registry.add_auto_approve_policy(tool_name)

        return registry

    def _create_engineer_registry(self) -> ToolRegistry:
        """Use production tool assembly and role filtering without a team runtime."""
        from evals.team_runtime import create_eval_registry
        from henchman.agents.pool import create_scoped_registry
        from henchman.agents.presets import get_default_team

        parent = create_eval_registry(self.test_dir)
        role = get_default_team()["engineer"]
        registry = create_scoped_registry(parent, role.tools)
        for name in registry.list_tools():
            registry.add_auto_approve_policy(name)
        return registry

    def cleanup(self) -> None:
        """Clean up the test environment."""
        if self._team_runtime is not None:
            self._providers = self.providers
            self._team_runtime.orchestrator.pool.shutdown()
            self._team_runtime = None
        if self._original_cwd:
            os.chdir(self._original_cwd)
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None
        self._agent = None

    def create_file(self, path: str, content: str) -> Path:
        """Create a file in the test directory.

        Args:
            path: Relative path for the file.
            content: Content to write.

        Returns:
            Absolute path to the created file.
        """
        file_path = self.test_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path

    def read_file(self, path: str) -> str:
        """Read a file from the test directory.

        Args:
            path: Relative path to the file.

        Returns:
            File contents.
        """
        return (self.test_dir / path).read_text()

    def file_exists(self, path: str) -> bool:
        """Check if a file exists in the test directory.

        Args:
            path: Relative path to check.

        Returns:
            True if file exists.
        """
        return (self.test_dir / path).exists()

    async def run(
        self,
        prompt: str,
        max_iterations: int = 10,
        timeout: float | None = None,
        *,
        observe_event: Callable[[AgentEvent], None] | None = None,
    ) -> EvalResult:
        """Run the agent with the given prompt.

        Handles the full agent loop including tool execution.

        Args:
            prompt: User prompt to send.
            max_iterations: Maximum tool call iterations.
            timeout: Whole-turn timeout in seconds; defaults to EVAL_TIMEOUT or 60.
            observe_event: Called after each event is retained. Observer errors propagate.

        Returns:
            EvalResult with full details.
        """
        import time

        from evals.team_runtime import ToolObservations
        from henchman.cli.app import _run_headless_json_mode

        if self._agent is None:
            raise RuntimeError("Test rig not set up. Call setup() first.")
        if type(max_iterations) is not int or max_iterations < 0:
            raise ValueError("max_iterations must be a nonnegative integer")
        effective_timeout = float(os.environ.get("EVAL_TIMEOUT", "60")) if timeout is None else timeout
        if isinstance(effective_timeout, bool) or not math.isfinite(effective_timeout) or effective_timeout <= 0:
            raise ValueError("timeout must be a finite positive number")

        outcome_index = len(self._run_outcomes)
        self._run_outcomes.append((False, "Evaluation did not complete"))
        if self._team_runtime is not None:
            result = await self._team_runtime.run(
                prompt, max_iterations, effective_timeout, observe_event=observe_event,
            )
            self._run_outcomes[outcome_index] = (result.success, result.error)
            return result
        start_time = time.perf_counter()
        final_response = ""
        tokens_in = 0
        tokens_out = 0
        error: str | None = None
        self._events.clear()
        self._tool_logs.clear()
        observations = ToolObservations(self._events, self._tool_logs)
        observer = EventObserver(observe_event)

        def record(event: AgentEvent) -> None:
            observations.record(event)
            observer(event)

        old_limit = self._agent.base_tool_iterations
        self._agent.base_tool_iterations = max_iterations
        runtime = SimpleNamespace(agent=self._agent, tool_registry=self._agent.tool_registry)
        success = False
        try:
            async with asyncio.timeout(effective_timeout):
                success = await _run_headless_json_mode(runtime, prompt, record)
        except TimeoutError:
            if observer.failed:
                raise
            error = f"Evaluation timed out after {effective_timeout:g}s"
            record(AgentEvent(EventType.ERROR, error))
            record(AgentEvent(EventType.FINISHED, {"finish_reason": "error"}))
        except Exception as e:
            if observer.failed:
                raise
            error = str(e)
            record(AgentEvent(EventType.ERROR, error))
        finally:
            self._agent.base_tool_iterations = old_limit

        for event in self._events:
            if event.type == EventType.CONTENT:
                final_response += event.data or ""
            elif event.type == EventType.ERROR and error is None:
                error = str(event.data)
            elif event.type == EventType.FINISHED and isinstance(event.data, dict):
                usage = event.data.get("usage") or {}
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
        if not success and error is None:
            error = "Evaluation ended without successful completion"

        duration_ms = (time.perf_counter() - start_time) * 1000

        result = EvalResult(
            prompt=prompt,
            final_response=final_response,
            tool_logs=list(self._tool_logs),
            events=list(self._events),
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=success and error is None,
            error=error,
            diagnostics=list(observations.diagnostics),
        )
        self._run_outcomes[outcome_index] = (result.success, result.error)
        return result

    def assert_successful_runs(self) -> None:
        """Reject missing, failed or interrupted turns, even if their result was ignored."""
        assert self._run_outcomes, "Evaluation did not run an agent turn"
        failures = [
            f"Turn {index}: {error or 'Evaluation failed'}"
            for index, (success, error) in enumerate(self._run_outcomes, start=1)
            if not success
        ]
        assert not failures, "\n".join(failures)

    def tool_was_called(self, tool_name: str) -> bool:
        """Check if a tool was called during the eval.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if the tool was called.
        """
        return any(log.tool_name == tool_name for log in self._tool_logs)

    def get_tool_calls(self, tool_name: str) -> list[ToolLog]:
        """Get all calls to a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            List of tool logs for that tool.
        """
        return [log for log in self._tool_logs if log.tool_name == tool_name]

    def get_tool_args(self, tool_name: str, index: int = 0) -> dict[str, Any]:
        """Get arguments from a specific tool call.

        Args:
            tool_name: Name of the tool.
            index: Which call to get (0 = first).

        Returns:
            Arguments dict, or empty dict if not found.
        """
        calls = self.get_tool_calls(tool_name)
        if index < len(calls):
            return calls[index].arguments
        return {}

    def get_all_tool_calls(self) -> list[ToolLog]:
        """Get all tool calls made during the eval."""
        return list(self._tool_logs)

    async def expect_tool_call(
        self,
        tool_name: str,
        timeout: float = 5.0,
    ) -> ToolLog | None:
        """Wait for a specific tool to be called.

        Args:
            tool_name: Name of the tool to wait for.
            timeout: Timeout in seconds.

        Returns:
            The tool log if found, None otherwise.
        """
        import asyncio

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            for log in self._tool_logs:
                if log.tool_name == tool_name:
                    return log
            await asyncio.sleep(0.1)
        return None


class LoggingToolWrapper(Tool):
    """Legacy direct-call logger; runtime evals observe final registry events."""

    def __init__(self, tool: Tool, log_list: list[ToolLog]) -> None:
        """Initialize wrapper.

        Args:
            tool: The tool to wrap.
            log_list: List to append logs to.
        """
        self._tool = tool
        self._log_list = log_list

    @property
    def name(self) -> str:
        """Get tool name."""
        return self._tool.name

    @property
    def description(self) -> str:
        """Get tool description."""
        return self._tool.description

    @property
    def parameters(self) -> dict[str, object]:
        """Get tool parameters."""
        return self._tool.parameters

    @property
    def kind(self) -> ToolKind:
        """Get tool kind."""
        return self._tool.kind

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        """Preserve the wrapped tool's invocation-specific policy."""
        return self._tool.execution_kind(params)

    def needs_confirmation(self, params: dict[str, object]) -> ConfirmationRequest | None:
        """Preserve the wrapped tool's confirmation contract."""
        return self._tool.needs_confirmation(params)

    async def execute(self, **kwargs: object) -> ToolResult:
        """Execute the tool and log the call."""
        result = await self._tool.execute(**kwargs)

        self._log_list.append(
            ToolLog(
                tool_name=self.name,
                arguments=dict(kwargs),
                result=result.content[:500] if result.content else "",
                success=result.success,
            )
        )

        return result


def eval_test(policy: EvalPolicy) -> Callable[..., Callable[..., Awaitable[None]]]:
    """Decorator for behavioral eval tests.

    Args:
        policy: The consistency expectation for this test.
            - ALWAYS_PASSES: Must pass 100%, runs in CI.
            - USUALLY_PASSES: May have flakiness, runs nightly.

    Returns:
        Decorated test function.

    Example:
        >>> @eval_test("ALWAYS_PASSES")
        ... async def test_reads_files(rig):
        ...     rig.create_file("test.txt", "content")
        ...     result = await rig.run("Read test.txt")
        ...     assert rig.tool_was_called("read_file")
    """

    def decorator(
        func: Callable[[EvalTestRig], Awaitable[None]],
    ) -> Callable[[], Awaitable[None]]:
        async def wrapper() -> None:
            rig = EvalTestRig()
            try:
                rig.setup(func.__name__)
                await func(rig)
                rig.assert_successful_runs()
            finally:
                rig.cleanup()

        # Copy over the name and module, but NOT the signature
        wrapper.__name__ = func.__name__
        wrapper.__qualname__ = func.__qualname__
        wrapper.__module__ = func.__module__
        wrapper.__doc__ = func.__doc__

        # Apply pytest markers based on policy
        if policy == "ALWAYS_PASSES":
            wrapper = pytest.mark.always_passes(wrapper)
        elif policy == "USUALLY_PASSES":
            # Skip unless RUN_ALL_EVALS is set
            if not os.environ.get("RUN_ALL_EVALS"):
                wrapper = pytest.mark.skip(
                    reason="USUALLY_PASSES test - set RUN_ALL_EVALS=1 to run"
                )(wrapper)
            wrapper = pytest.mark.usually_passes(wrapper)

        return wrapper

    return decorator


# Convenience fixture for pytest
@pytest.fixture
async def eval_rig() -> AsyncGenerator[EvalTestRig, None]:
    """Pytest fixture providing an EvalTestRig.

    Yields:
        A configured EvalTestRig for the test.
    """
    rig = EvalTestRig()
    rig.setup("fixture_test")
    try:
        yield rig
    finally:
        rig.cleanup()
