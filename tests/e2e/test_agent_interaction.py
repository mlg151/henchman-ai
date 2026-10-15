from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.cli.textual_app import HenchmanTextualApp, TextualConfig
from henchman.cli.textual_widgets import ChatMessage
from henchman.providers.base import ModelProvider


@pytest.mark.asyncio
async def test_agent_interaction_flow():
    """
    E2E test to verify the full loop:
    1. User types message
    2. User presses Enter (Submit)
    3. App authenticates/initializes agent
    4. Agent processes message
    5. Agent response appears in Chat Pane
    """

    # Mock Provider
    class MockProvider(ModelProvider):
        def __init__(self):
            pass

        @property
        def name(self) -> str:
            return "MockProvider"

        async def chat_async(self, *args, **kwargs):
            return "Mock response"

        async def generate_async(self, *args, **kwargs):
            return "Mock response"

        async def chat_stream_async(self, *args, **kwargs):
            yield "Mock response"

        async def generate_stream_async(self, *args, **kwargs):
            yield "Mock response"

        async def chat_completion_stream(self, *args, **kwargs):
            from henchman.providers.base import FinishReason, StreamChunk

            yield StreamChunk(content="Mock response", finish_reason=FinishReason.STOP)

        async def embed_async(self, *args, **kwargs):
            return [0.0] * 10

        def count_tokens(self, text: str) -> int:
            return len(text.split())

        def get_model_name(self) -> str:
            return "mock-model"

    mock_provider = MockProvider()

    # We need to mock the Orchestrator's run_direct or the session manager to return a stream
    # But HenchmanTextualApp initializes its own CoreContext.
    # We can mock create_core_context to return a mock context with a mock orchestrator

    mock_event_stream = AsyncMock()  # noqa: F841
    # Simulate a stream of events
    from henchman.core.events import AgentEvent, EventType  # noqa: E402

    async def event_generator(input_text: str) -> AsyncIterator[AgentEvent]:  # noqa: ARG001
        # 1. Thought
        yield AgentEvent(
            type=EventType.THOUGHT,
            source_agent="Assistant",
            data="I should reply to the user.",
        )
        # 2. Content chunks
        yield AgentEvent(
            type=EventType.CONTENT,
            source_agent="Assistant",
            data="Hello",
        )
        yield AgentEvent(
            type=EventType.CONTENT,
            source_agent="Assistant",
            data=" World!",
        )
        # 3. Finished
        yield AgentEvent(type=EventType.FINISHED, source_agent="Assistant", data="stop")

    # Mock the orchestrator
    mock_orchestrator = MagicMock()
    mock_orchestrator.run = MagicMock(side_effect=event_generator)
    mock_orchestrator.aclose = AsyncMock()

    # Mock CoreContext
    mock_core_context = MagicMock()
    mock_core_context.orchestrator = mock_orchestrator
    mock_core_context.background_tasks = set()
    mock_core_context.mcp_manager = None
    mock_core_context.session_manager = MagicMock()  # To prevent AttributeError in set_session
    mock_core_context.session_manager.current = None

    # Patch create_core_context to return our mock
    with patch("henchman.cli.textual_app.create_core_context", return_value=mock_core_context):
        config = TextualConfig()
        app = HenchmanTextualApp(
            provider=mock_provider, config=config, environment_context="TestEnv"
        )

        async with app.run_test() as pilot:
            # 1. Type message
            await pilot.click("#input")
            await pilot.press("h", "e", "l", "l", "o")

            # 2. Press Ctrl+Enter (Submit)
            await pilot.press("ctrl+enter")

            # Wait for processing - increase time to allow worker thread to pick up
            await pilot.pause(2.0)

            # Debug: Check if we have the right orchestrator
            assert app.core_context is not None
            assert app.core_context.orchestrator is mock_orchestrator, (
                f"Orchestrator mismatch! Got {app.core_context.orchestrator} expected {mock_orchestrator}"
            )

            # 3. Verify user message in chat
            _chat_pane = app.query_one("#chat-pane")  # noqa: F841
            # We can't easily check RichLog content directly without private attributes or scraping lines
            # But we can check if write() was called on it if we mock it, or just rely on no exceptions.
            # Actually, standard RichLog has .lines usually? No.

            # Verify Orchestrator was called
            mock_orchestrator.run.assert_called_once_with("hello")

            messages = app.query(ChatMessage)
            assert any(message._content_text == "Hello World!" for message in messages)

            # 4. Verify Agent response
            # run_direct return value (generator) should be iterated

            # 5. Check if text appeared in UI (simulated inspection)
            # Since we can't grep lines easily from RichLog in test, we verify the flow logic completed
            assert app.input_handler is not None

            # Check input cleared
            input_widget = app.query_one("#input")
            assert input_widget.text == ""
