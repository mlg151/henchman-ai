"""Regression tests for Henchman CLI textual mixins."""

import ast
import asyncio
import inspect
import textwrap
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.textual_mixins import _InitMixin, _NullProvider
from henchman.cli.textual_questions import ToolPromptChannel
from henchman.providers.base import Message
from henchman.tools.base import ConfirmationRequest


class TestTextualConfirmLifecycle:
    """The mixin delegates approvals and shutdown to its owned prompt channel."""

    @pytest.mark.anyio
    async def test_textual_confirm_propagates_cancellation(self) -> None:
        obj = MagicMock(spec=_InitMixin)
        obj._tool_prompts = MagicMock(spec=ToolPromptChannel)
        obj._tool_prompts.confirm = AsyncMock(side_effect=asyncio.CancelledError)
        request = ConfirmationRequest(
            tool_name="test", description="test", params={}, risk_level="low",
        )
        with pytest.raises(asyncio.CancelledError):
            await _InitMixin._textual_confirm(obj, request)

    def test_shutdown_closes_the_owned_channel(self) -> None:
        obj = MagicMock(spec=_InitMixin)
        obj._tool_prompts = MagicMock(spec=ToolPromptChannel)
        _InitMixin._cleanup_confirm_futures(obj)
        obj._tool_prompts.close.assert_called_once_with()


class TestNullProviderDeadCode:
    """Verify the null provider raises without unreachable generator code."""

    def test_no_if_false_yield_in_chat_completion_stream(self) -> None:
        source = textwrap.dedent(
            inspect.getsource(_NullProvider.chat_completion_stream)
        )
        tree = ast.parse(source)

        unreachable_yields = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Constant)
            and node.test.value is False
            and any(isinstance(child, ast.Yield) for child in ast.walk(node))
        ]

        assert not unreachable_yields

    @pytest.mark.anyio
    async def test_chat_completion_stream_raises_immediately(self) -> None:
        stream = await _NullProvider().chat_completion_stream(
            [Message(role="user", content="test")]
        )

        assert isinstance(stream, AsyncIterator)
        with pytest.raises(RuntimeError, match="No model provider available"):
            async for _ in stream:
                pytest.fail("Null provider unexpectedly yielded a chunk")


class TestBoolConversion:
    """A truthy nonboolean modal result cannot grant tool approval."""

    @pytest.mark.anyio
    @pytest.mark.parametrize("answer, approved", [(True, True), (False, False),
                                                  (None, False), ("yes", False)])
    async def test_only_explicit_true_approves(self, answer, approved) -> None:
        channel = ToolPromptChannel(MagicMock())
        channel._show = AsyncMock(return_value=answer)
        request = ConfirmationRequest(
            tool_name="test", description="test", params={}, risk_level="low",
        )
        assert await channel.confirm(request) is approved
