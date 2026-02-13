"""Integration test for REPL startup message."""

from io import StringIO
from typing import Any
from unittest.mock import patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class MockProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(self, messages: list[Message], **kwargs: Any) -> Any:
        yield StreamChunk(content="Hi", finish_reason=FinishReason.STOP)


@pytest.mark.anyio
async def test_repl_startup_displays_info_message() -> None:
    """Verify that the REPL displays the startup info message."""
    console = Console(file=StringIO(), force_terminal=True)
    provider = MockProvider()
    repl = Repl(provider=provider, console=console)

    # Mock input to immediately exit via EOF
    with patch("henchman.cli.repl.Repl._get_input", side_effect=EOFError):
        await repl.run()

    output = console.file.getvalue()
    # Check for the actual startup message
    assert "Henchman-AI" in output
    # Check for the help hint (styled text will be present in some form)
    assert "help" in output.lower()
