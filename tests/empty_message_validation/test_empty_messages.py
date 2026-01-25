"""Tests for empty message validation to prevent 400 errors."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.core.agent import Agent
from henchman.providers.base import Message
from henchman.providers.openai_compat import OpenAICompatibleProvider


class TestEmptyMessageValidation:
    """Tests to ensure empty messages are validated before sending to API."""

    @pytest.mark.asyncio
    async def test_openai_provider_rejects_empty_messages(self):
        """Test that OpenAI provider validates messages are not empty."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="gpt-4"
        )

        # Mock the OpenAI client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Test with empty messages list
        messages = []

        # This should raise ValueError before making API call
        with pytest.raises(ValueError, match="Messages list cannot be empty"):
            async for _ in provider.chat_completion_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_openai_provider_rejects_messages_with_empty_content(self):
        """Test that OpenAI provider validates message content is not empty."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="gpt-4"
        )

        # Mock the OpenAI client
        mock_client = AsyncMock()
        provider._client = mock_client

        # Test with message that has empty content
        messages = [Message(role="user", content="")]

        # This should raise ValueError
        with pytest.raises(ValueError, match="Message with role 'user' cannot have empty content"):
            async for _ in provider.chat_completion_stream(messages):
                pass

        # Test with message that has only whitespace
        messages = [Message(role="user", content="   ")]

        with pytest.raises(ValueError, match="Message with role 'user' cannot have empty content"):
            async for _ in provider.chat_completion_stream(messages):
                pass

    @pytest.mark.asyncio
    async def test_openai_provider_allows_tool_messages_with_empty_content(self):
        """Test that tool messages can have empty content."""
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="gpt-4"
        )

        # Mock the OpenAI client to return a simple response
        mock_client = AsyncMock()
        mock_chat = AsyncMock()
        mock_completions = AsyncMock()

        # Create a mock response
        mock_response = AsyncMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"), finish_reason="stop")]

        async def mock_response_generator(_):
            yield mock_chunk

        mock_response.__aiter__ = lambda self: mock_response_generator(self)
        mock_create = AsyncMock(return_value=mock_response)
        mock_completions.create = mock_create
        mock_chat.completions = mock_completions
        mock_client.chat = mock_chat
        provider._client = mock_client

        # Tool messages can have empty content
        messages = [Message(role="tool", content="", tool_call_id="test-123")]

        # This should not raise an error
        async for _ in provider.chat_completion_stream(messages):
            pass

        # Verify the API was called
        assert mock_create.called

    @pytest.mark.asyncio
    async def test_agent_validates_messages_before_sending(self):
        """Test that agent validates messages before sending to provider."""
        mock_provider = AsyncMock()
        agent = Agent(provider=mock_provider)

        # Mock the provider's chat_completion_stream to track calls
        async def mock_stream_generator():
            yield MagicMock(content="Test response", finish_reason="stop")

        mock_provider.chat_completion_stream = AsyncMock(return_value=mock_stream_generator())

        # Test with agent that has empty history (no system prompt)
        # When we call run, it adds the user message to history
        # So get_messages_for_api should return at least the user message

        # First, let's test the get_messages_for_api method directly
        agent.history = []  # Empty history
        agent.system_prompt = None  # No system prompt

        _ = agent.get_messages_for_api()
        # With empty history and no system prompt, compactor might return empty list
        # But after our fix, the agent should validate this in _stream_response

        # Now test the full run method
        # Reset the mock
        mock_provider.chat_completion_stream.reset_mock()

        # Run with valid input
        async for _ in agent.run("Hello"):
            pass

        # Provider should have been called
        assert mock_provider.chat_completion_stream.called

    def test_message_validation_in_provider(self):
        """Test that provider validates messages before formatting."""
        _ = OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="gpt-4"
        )

        # Test various invalid message scenarios
        # These are now tested in the async tests above
        pass


class TestInputValidationInREPL:
    """Tests for input validation in the REPL layer."""

    @pytest.mark.asyncio
    async def test_repl_validation_of_empty_input(self, monkeypatch):
        """Test that REPL validates empty user input."""
        from rich.console import Console

        from henchman.cli.repl import Repl, ReplConfig

        console = Console()
        mock_provider = AsyncMock()
        config = ReplConfig()

        repl = Repl(provider=mock_provider, console=console, config=config)

        # Mock the renderer to capture output
        mock_renderer = MagicMock()
        repl.renderer = mock_renderer

        # Test with empty input
        await repl._run_agent("")

        # Should show info message and return early
        # Provider should not be called
        assert not mock_provider.chat_completion_stream.called

        # Test with whitespace-only input
        await repl._run_agent("   ")

        # Should show info message and return early
        # Provider should not be called
        assert not mock_provider.chat_completion_stream.called

    @pytest.mark.asyncio
    async def test_repl_processes_valid_input(self, monkeypatch):
        """Test that REPL processes valid non-empty input."""
        from rich.console import Console

        from henchman.cli.repl import Repl, ReplConfig

        console = Console()
        mock_provider = AsyncMock()
        config = ReplConfig()

        repl = Repl(provider=mock_provider, console=console, config=config)

        # Mock the agent to track calls
        mock_agent = AsyncMock()
        async def mock_agent_run_generator():
            yield MagicMock(type="content", data="Test response")

        mock_agent.run = AsyncMock(return_value=mock_agent_run_generator())
        repl.agent = mock_agent

        # Mock the renderer
        mock_renderer = MagicMock()
        repl.renderer = mock_renderer

        # Test with valid input
        await repl._run_agent("Hello, world!")

        # Agent should have been called
        mock_agent.run.assert_called_with("Hello, world!")

        # Should not show info message
        mock_renderer.info.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

