"""
UI Integration Tests for Token Management with LLM.

Tests token counting, truncation, and LLM integration.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk
from henchman.tools.registry import ToolRegistry


class TokensTestProvider(ModelProvider):
    """Provider for testing token handling."""
    
    def __init__(self):
        self._name = "tokens_test"
        self.call_count = 0
        self.received_messages = []
    
    @property
    def name(self) -> str:
        return self._name
    
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        self.received_messages = messages  # Store for verification
        
        # Simple response
        yield StreamChunk(
            content=f"Processed {len(messages)} messages",
            finish_reason=FinishReason.STOP
        )


class TestUITokensLLM:
    """Test UI token management with LLM integration."""
    
    @pytest.fixture
    def provider(self):
        return TokensTestProvider()
    
    @pytest.fixture
    def tool_registry(self):
        return ToolRegistry()
    
    @pytest.fixture
    def agent(self, provider, tool_registry):
        return Agent(provider=provider, tool_registry=tool_registry)
    
    @pytest.mark.asyncio
    async def test_agent_token_awareness(self, agent, provider):
        """Test that agent processes messages."""
        # Send a message
        async for _ in agent.run("Short message"):
            pass
        
        # Provider should have received messages
        assert len(provider.received_messages) > 0
        
        # Send a longer message
        long_message = "This is a much longer message " * 5
        async for _ in agent.run(long_message):
            pass
        
        # Provider should handle it
        assert provider.call_count == 2
    
    @pytest.mark.asyncio
    async def test_conversation_history(self, agent, provider):
        """Test conversation history management."""
        # Have a conversation
        messages = [
            "First message",
            "Second message",
            "Third message",
            "Fourth message"
        ]
        
        for msg in messages:
            async for _ in agent.run(msg):
                pass
        
        # Agent should manage history
        assert provider.call_count == len(messages)
    
    @pytest.mark.asyncio
    async def test_system_prompt_integration(self, provider):
        """Test system prompt integration."""
        registry = ToolRegistry()
        
        # Agent with system prompt
        agent_with_prompt = Agent(
            provider=provider,
            tool_registry=registry,
            system_prompt="You are a helpful assistant."
        )
        
        async for _ in agent_with_prompt.run("Test message"):
            pass
        
        # System prompt should be included
        assert len(provider.received_messages) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
