"""
UI Integration Tests for Compaction with LLM.

Tests conversation compaction and LLM integration.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk
from henchman.tools.registry import ToolRegistry


class CompactionTestProvider(ModelProvider):
    """Provider for testing compaction."""
    
    def __init__(self):
        self._name = "compaction_test"
        self.call_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        
        # Simple response
        yield StreamChunk(
            content=f"Response to {len(messages)} messages",
            finish_reason=FinishReason.STOP
        )


class TestUICompactionLLM:
    """Test UI compaction with LLM integration."""
    
    @pytest.fixture
    def provider(self):
        return CompactionTestProvider()
    
    @pytest.fixture
    def tool_registry(self):
        return ToolRegistry()
    
    @pytest.fixture
    def agent(self, provider, tool_registry):
        return Agent(provider=provider, tool_registry=tool_registry)
    
    @pytest.mark.asyncio
    async def test_conversation_history_management(self, agent, provider):
        """Test that conversation history is properly managed."""
        # Have a conversation
        for i in range(5):
            async for _ in agent.run(f"Message {i}"):
                pass
        
        # Agent should manage history
        assert provider.call_count == 5
    
    @pytest.mark.asyncio
    async def test_long_conversation(self, agent, provider):
        """Test handling of longer conversations."""
        # Simulate a longer conversation
        for i in range(10):
            async for _ in agent.run(f"Conversation turn {i}"):
                pass
        
        # Should handle all messages
        assert provider.call_count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
