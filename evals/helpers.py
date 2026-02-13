"""Helpers for behavioral evaluations.

This module provides the core infrastructure for running behavioral evals,
including the EvalTestRig for setting up test environments and the eval_test
decorator for controlling test execution based on policy.

Behavioral evals use REAL LLM providers to test actual agent behavior.
Configure the provider via environment variables:
    EVAL_PROVIDER=deepseek|anthropic|ollama (default: deepseek)
    EVAL_MODEL=model-name (optional, uses provider default)
    DEEPSEEK_API_KEY=your-key (or ANTHROPIC_API_KEY, etc.)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pytest

from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry

# Eval policy types
EvalPolicy = Literal["ALWAYS_PASSES", "USUALLY_PASSES"]


def get_eval_provider() -> ModelProvider:
    """Get the provider to use for evals based on environment.

    Uses EVAL_PROVIDER env var (default: deepseek).
    Falls back through providers if API keys aren't set.

    Returns:
        A configured ModelProvider instance.

    Raises:
        RuntimeError: If no provider could be configured.
    """
    provider_name = os.environ.get("EVAL_PROVIDER", "deepseek").lower()
    model = os.environ.get("EVAL_MODEL")

    # Try the requested provider first
    if provider_name == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if api_key:
            from henchman.providers.deepseek import DeepSeekProvider

            return DeepSeekProvider(api_key=api_key, model=model or "deepseek-chat")

    if provider_name == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            from henchman.providers.anthropic import AnthropicProvider

            return AnthropicProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514")

    if provider_name == "ollama":
        from henchman.providers.ollama import OllamaProvider

        return OllamaProvider(model=model or "llama3.2")

    # Fallback: try any available provider
    if os.environ.get("DEEPSEEK_API_KEY"):
        from henchman.providers.deepseek import DeepSeekProvider

        return DeepSeekProvider(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            model=model or "deepseek-chat",
        )

    if os.environ.get("ANTHROPIC_API_KEY"):
        from henchman.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model=model or "claude-sonnet-4-20250514",
        )

    # Last resort: try Ollama (no API key needed)
    try:
        from henchman.providers.ollama import OllamaProvider

        return OllamaProvider(model=model or "llama3.2")
    except Exception:
        pass

    raise RuntimeError(
        "No provider configured for evals. Set one of:\n"
        "  DEEPSEEK_API_KEY=your-key\n"
        "  ANTHROPIC_API_KEY=your-key\n"
        "  EVAL_PROVIDER=ollama (for local models)"
    )


@dataclass
class ToolLog:
    """Log entry for a tool call during an eval."""

    tool_name: str
    arguments: dict[str, Any]
    result: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvalResult:
    """Result of running an eval."""

    prompt: str
    final_response: str
    tool_logs: list[ToolLog]
    events: list[AgentEvent]
    duration_ms: float
    tokens_in: int
    tokens_out: int
    success: bool
    error: str | None = None


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
            arguments=json.dumps(arguments),
        )
        self._responses.append([tool_call])
        self._responses.append(follow_up)

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
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

    Provides a sandboxed environment for testing agent behavior, including:
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
    ) -> None:
        """Initialize the test rig.

        Args:
            provider: Provider to use. If None, uses get_eval_provider().
            system_prompt: System prompt for the agent.
        """
        self._provider = provider or get_eval_provider()
        self._system_prompt = system_prompt or self._get_eval_system_prompt()
        self._temp_dir: Path | None = None
        self._tool_logs: list[ToolLog] = []
        self._events: list[AgentEvent] = []
        self._agent: Agent | None = None
        self._original_cwd: Path | None = None

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

        # Create agent with wrapped registry
        registry = self._create_wrapped_registry()
        self._agent = Agent(
            provider=self._provider,
            tool_registry=registry,
            system_prompt=self._system_prompt,
        )

    def _create_wrapped_registry(self) -> ToolRegistry:
        """Create a tool registry with logging wrappers."""
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

        # Create and register built-in tools with logging wrappers
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

        # Register built-in tools with logging wrappers
        for tool in builtin_tools:
            wrapped = LoggingToolWrapper(tool, self._tool_logs)
            registry.register(wrapped)

        # Auto-approve all tools for evals
        for tool in registry._tools:
            registry.add_auto_approve_policy(tool)

        return registry

    def cleanup(self) -> None:
        """Clean up the test environment."""
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
        timeout: float = 60.0,
    ) -> EvalResult:
        """Run the agent with the given prompt.

        Handles the full agent loop including tool execution.

        Args:
            prompt: User prompt to send.
            max_iterations: Maximum tool call iterations.
            timeout: Timeout in seconds.

        Returns:
            EvalResult with full details.
        """
        import time

        if self._agent is None:
            raise RuntimeError("Test rig not set up. Call setup() first.")

        start_time = time.perf_counter()
        final_response = ""
        tokens_in = 0
        tokens_out = 0
        error: str | None = None
        iteration = 0

        try:
            # Initial run
            pending_tool_calls: list[ToolCall] = []

            async for event in self._agent.run(prompt):
                self._events.append(event)

                if event.type == EventType.CONTENT:
                    final_response += event.data or ""
                elif event.type == EventType.TOOL_CALL_REQUEST:
                    pending_tool_calls.append(event.data)
                elif event.type == EventType.FINISHED:
                    break

            # Tool execution loop
            while pending_tool_calls and iteration < max_iterations:
                iteration += 1

                # Execute all pending tool calls
                for tool_call in pending_tool_calls:
                    result = await self._execute_tool(tool_call)
                    self._agent.submit_tool_result(tool_call.id, result)

                # Clear pending calls
                pending_tool_calls = []

                # Continue with tool results
                async for event in self._agent.continue_with_tool_results():
                    self._events.append(event)

                    if event.type == EventType.CONTENT:
                        final_response += event.data or ""
                    elif event.type == EventType.TOOL_CALL_REQUEST:
                        pending_tool_calls.append(event.data)
                    elif event.type == EventType.FINISHED:
                        break

        except Exception as e:
            error = str(e)

        duration_ms = (time.perf_counter() - start_time) * 1000

        return EvalResult(
            prompt=prompt,
            final_response=final_response,
            tool_logs=list(self._tool_logs),
            events=list(self._events),
            duration_ms=duration_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=error is None,
            error=error,
        )

    async def _execute_tool(self, tool_call: ToolCall) -> str:
        """Execute a tool call and return the result.

        Args:
            tool_call: The tool call to execute.

        Returns:
            The tool result as a string.
        """
        if self._agent is None:
            return "Error: Agent not initialized"

        try:
            result = await self._agent.tool_registry.execute(
                tool_call.name,
                tool_call.arguments,
            )
            return result.content or ""
        except Exception as e:
            return f"Error executing {tool_call.name}: {e}"

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
    """Wrapper that logs tool calls for evaluation tracking."""

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
