"""Unit test demonstrating the fixed delegation error type consistency."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from henchman.agents.delegation import (
    _prepare_execution,
    _finalize_execution,
    DelegationPreparationError,
    DelegationFinalizationError,
    AgentProtocolError,
    DelegationRunner,
)
from henchman.agents.orchestrator_types import DelegationParams
from henchman.config.schema import Settings
from henchman.core.events import EventType


class TestDelegationErrorTypeConsistency:
    """Test that delegation errors use consistent, specific exception types."""
    
    def test_prepare_execution_target_agent_none_raises_delegation_preparation_error(self):
        """_prepare_execution raises DelegationPreparationError when target_agent is None."""
        runner = MagicMock()
        params = DelegationParams(target_role="engineer", task="fix bug")
        params.target_agent = None
        
        with pytest.raises(DelegationPreparationError, match="target_agent is None"):
            _prepare_execution(runner, params)
    
    def test_prepare_execution_not_agent_protocol_raises_delegation_preparation_error(self):
        """_prepare_execution raises DelegationPreparationError when agent doesn't conform to AgentProtocol."""
        runner = MagicMock()
        params = DelegationParams(target_role="engineer", task="fix bug")
        params.target_agent = object()  # Plain object without required interface
        
        with pytest.raises(DelegationPreparationError, match="does not conform to AgentProtocol"):
            _prepare_execution(runner, params)
    
    def test_prepare_execution_messages_none_raises_delegation_preparation_error(self):
        """_prepare_execution raises DelegationPreparationError when messages is None."""
        runner = MagicMock()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class AgentWithNoneMessages:
            messages = None
            
            def clear_history(self) -> None:
                pass
        
        params.target_agent = AgentWithNoneMessages()
        
        with pytest.raises(DelegationPreparationError, match="has messages=None"):
            _prepare_execution(runner, params)
    
    @pytest.mark.anyio
    async def test_finalize_execution_target_none_raises_delegation_finalization_error(self):
        """_finalize_execution raises DelegationFinalizationError when target_agent is None."""
        runner = MagicMock()
        params = DelegationParams(target_role="engineer", task="fix bug")
        params.target_agent = None
        
        with pytest.raises(DelegationFinalizationError, match="target_agent is None"):
            async for _ in _finalize_execution(runner, params):
                pass
    
    @pytest.mark.anyio
    async def test_get_target_agent_not_protocol_raises_agent_protocol_error(self):
        """_get_target_agent raises AgentProtocolError when agent doesn't conform to protocol."""
        pool = MagicMock()
        pool.get_agent.return_value = object()  # Plain object
        
        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )
        
        with pytest.raises(AgentProtocolError, match="does not conform to AgentProtocol"):
            await runner._get_target_agent("explorer")
    
    def test_error_hierarchy(self):
        """Verify that delegation errors form a proper hierarchy."""
        # DelegationPreparationError should be a subclass of Exception
        assert issubclass(DelegationPreparationError, Exception)
        
        # DelegationFinalizationError should be a subclass of Exception
        assert issubclass(DelegationFinalizationError, Exception)
        
        # AgentProtocolError should be a subclass of Exception
        assert issubclass(AgentProtocolError, Exception)
        
        # These should NOT be generic exceptions
        assert not issubclass(DelegationPreparationError, ValueError)
        assert not issubclass(DelegationPreparationError, TypeError)
        assert not issubclass(DelegationPreparationError, RuntimeError)
    
    def test_error_messages_are_descriptive(self):
        """Verify that error messages provide useful context."""
        # Test DelegationPreparationError
        error = DelegationPreparationError("engineer", "target_agent is None")
        assert "engineer" in str(error)
        assert "target_agent is None" in str(error)
        
        # Test DelegationFinalizationError
        error = DelegationFinalizationError("explorer", "target_agent is None")
        assert "explorer" in str(error)
        assert "target_agent is None" in str(error)
        
        # Test AgentProtocolError
        error = AgentProtocolError("explorer", "has messages=None")
        assert "explorer" in str(error)
        assert "has messages=None" in str(error)


class TestDelegationErrorPropagation:
    """Test that delegation errors propagate correctly through the system."""
    
    @pytest.mark.anyio
    async def test_run_delegation_propagates_preparation_error(self):
        """run_delegation yields ERROR event when preparation fails."""
        from henchman.agents.delegation import DelegationRunner
        
        pool = MagicMock()
        
        # Mock _get_target_agent to return an agent that will fail preparation
        class BadAgent:
            messages = None  # Will cause DelegationPreparationError
            
            def clear_history(self) -> None:
                pass
        
        pool.get_agent.return_value = BadAgent()
        
        runner = DelegationRunner(
            pool=pool,
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )
        
        params = DelegationParams(
            target_role="explorer",
            task="test task",
            brief=None,
            depth=0,
        )
        
        events = []
        async for event in runner.run_delegation(params):
            events.append(event)
        
        # Should have ERROR event
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) > 0
        # The error should mention the agent protocol violation
        error_data = str(error_events[0].data)
        assert "agent protocol violation" in error_data.lower() or "messages=none" in error_data.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])