"""
UI Integration Tests for Session Management.

Tests session management.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from henchman.core.agent import Agent
from henchman.core.session import Session
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk
from henchman.tools.registry import ToolRegistry


class SessionTestProvider(ModelProvider):
    """Provider for testing sessions."""
    
    def __init__(self):
        self._name = "session_test"
        self.call_count = 0
    
    @property
    def name(self) -> str:
        return self._name
    
    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.call_count += 1
        
        # Simple response
        yield StreamChunk(
            content=f"Response #{self.call_count}",
            finish_reason=FinishReason.STOP
        )


class TestUISession:
    """Test UI session management."""
    
    @pytest.fixture
    def provider(self):
        return SessionTestProvider()
    
    @pytest.fixture
    def tool_registry(self):
        return ToolRegistry()
    
    @pytest.fixture
    def agent(self, provider, tool_registry):
        return Agent(provider=provider, tool_registry=tool_registry)
    
    @pytest.fixture
    def session(self):
        """Create a test session."""
        import uuid
        from datetime import datetime, timezone
        
        return Session(
            id=str(uuid.uuid4()),
            project_hash="test_project",
            started=datetime.now(timezone.utc).isoformat(),
            last_updated=datetime.now(timezone.utc).isoformat()
        )
    
    @pytest.mark.asyncio
    async def test_session_creation(self, session):
        """Test session creation."""
        assert session.id is not None
        assert session.project_hash == "test_project"
        assert session.messages == []  # Should be empty list by default
    
    @pytest.mark.asyncio
    async def test_agent_with_session_context(self, agent, session):
        """Test agent operation with session context."""
        # Agent should work independently of session
        async for chunk in agent.run("Test message"):
            assert chunk.content == "Response #1"
        
        # Session remains unchanged (agent doesn't automatically modify it)
        # This is expected - session integration would be at a higher level


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
