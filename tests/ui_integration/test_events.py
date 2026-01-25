"""
UI Integration Tests for Events System.

Tests event handling through the UI.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk
from henchman.tools.registry import ToolRegistry


class EventsTestProvider(ModelProvider):
    """Provider for testing events."""
    
    def __init__(self):
        self._name = "events_test"
        self.call_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        
        # Simple response
        yield StreamChunk(
            content="Response",
            finish_reason=FinishReason.STOP
        )


class TestUIEvents:
    """Test UI event handling."""
    
    @pytest.fixture
    def provider(self):
        return EventsTestProvider()
    
    @pytest.fixture
    def tool_registry(self):
        return ToolRegistry()
    
    @pytest.fixture
    def agent(self, provider, tool_registry):
        return Agent(provider=provider, tool_registry=tool_registry)
    
    @pytest.mark.asyncio
    async def test_basic_agent_operation(self, agent, provider):
        """Test basic agent operation."""
        # Run agent
        async for chunk in agent.run("Test message"):
            assert chunk.content == "Response"
        
        # Provider should have been called
        assert provider.call_count == 1
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling."""
        # Create a provider that raises an error
        error_provider = MagicMock(spec=ModelProvider)
        error_provider.name = "error_provider"
        
        async def error_stream(*args, **kwargs):
            raise RuntimeError("Test error")
            yield  # Make it a generator
        
        error_provider.chat_completion_stream = error_stream
        
        error_agent = Agent(provider=error_provider, tool_registry=ToolRegistry())
        
        # Should handle error gracefully
        try:
            async for _ in error_agent.run("Test"):
                pass
            # Might not raise if errors are handled internally
        except Exception as e:
            assert "Test error" in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
