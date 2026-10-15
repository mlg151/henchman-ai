"""Comprehensive tests for ask_user tool."""

import asyncio
import inspect

import pytest

from henchman.tools.builtins.ask_user import AskUserTool


class TestAskUserTool:
    """Comprehensive tests for AskUserTool."""

    def test_properties(self) -> None:
        """Test tool properties."""
        tool = AskUserTool()

        assert tool.name == "ask_user"
        assert "Ask the user a question" in tool.description
        assert tool.kind.name == "READ"  # ToolKind.READ

        # Check parameters schema
        params = tool.parameters
        assert params["type"] == "object"
        assert "question" in params["properties"]
        assert "timeout" in params["properties"]
        assert "question" in params["required"]

    @pytest.mark.anyio
    async def test_execute_basic(self) -> None:
        """Test basic execution with user response."""
        async def answer(question):
            assert question == "What is your name?"
            return "Ada"
        tool = AskUserTool(question_handler=answer)
        result = await tool.execute(question="What is your name?")

        assert result.content == "Ada"
        assert "What is your name?" in result.display
        assert result.success is True

    @pytest.mark.anyio
    async def test_execute_with_timeout(self) -> None:
        """Test execution with timeout."""
        tool = AskUserTool()

        result = await tool.execute(question="Test", timeout=30)

        assert not result.success
        assert "No user input handler" in result.content

    @pytest.mark.anyio
    async def test_execute_empty_question(self) -> None:
        """Test execution with empty question."""
        tool = AskUserTool()

        result = await tool.execute(question="")

        assert not result.success
        assert "question" in result.error.lower()

    def test_str_representation(self) -> None:
        """Test string representation of tool result."""
        from henchman.tools.base import ToolResult

        result = ToolResult(content="Test answer")
        assert "Test answer" in str(result)

    def test_tool_registration(self) -> None:
        """Test that tool can be registered in registry."""
        from henchman.tools.registry import ToolRegistry

        registry = ToolRegistry()
        tool = AskUserTool()
        registry.register(tool)

        # Check tool is registered
        declarations = registry.get_declarations()
        tool_names = [d.name for d in declarations]
        assert "ask_user" in tool_names

        # Check tool declaration matches
        for decl in declarations:
            if decl.name == "ask_user":
                assert "Ask the user a question" in decl.description
                break

    @pytest.mark.anyio
    async def test_execute_method_is_async(self) -> None:
        """Test the execute method exists and is async."""
        tool = AskUserTool()

        assert hasattr(tool, "execute")
        assert inspect.iscoroutinefunction(tool.execute)


@pytest.mark.parametrize("question", ["", "  ", None, 42])
async def test_invalid_question_never_invokes_input_handler(question):
    called = False

    async def answer(_question):
        nonlocal called
        called = True
        return "not an answer"

    result = await AskUserTool(question_handler=answer).execute(question=question)
    assert not result.success
    assert not called


@pytest.mark.parametrize("answer", [None, "", "  ", 42])
async def test_missing_or_invalid_answer_does_not_report_success(answer):
    async def handler(_question):
        return answer

    result = await AskUserTool(question_handler=handler).execute(question="Which file?")
    assert not result.success
    assert result.error
    assert "Which file?" in result.display


async def test_timeout_cancels_pending_question():
    closed = False

    async def handler(_question):
        nonlocal closed
        try:
            await asyncio.sleep(2)
        finally:
            closed = True
        return "too late"

    result = await AskUserTool(question_handler=handler).execute(question="Which file?", timeout=1)
    assert not result.success
    assert "timed out" in result.error.lower()
    assert "Which file?" in result.content
    assert closed


async def test_cancellation_propagates_and_closes_pending_question():
    started = asyncio.Event()
    closed = False

    async def handler(_question):
        nonlocal closed
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            closed = True
        return "never"

    task = asyncio.create_task(AskUserTool(question_handler=handler).execute(question="Which file?"))
    await started.wait()
    task.cancel("User stopped")
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed


@pytest.mark.parametrize("timeout", [-1, True, "1"])
async def test_invalid_timeout_fails_without_asking(timeout):
    async def handler(_question):
        pytest.fail("invalid timeout must not ask the user")

    result = await AskUserTool(question_handler=handler).execute(question="Which file?", timeout=timeout)
    assert not result.success
    assert "timeout" in result.error.lower()


async def test_handler_failure_is_not_an_answer():
    async def handler(_question):
        raise RuntimeError("input channel disconnected")

    result = await AskUserTool(question_handler=handler).execute(question="Which file?")
    assert not result.success
    assert "input channel disconnected" in result.error
