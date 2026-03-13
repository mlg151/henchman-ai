"""Unit of Doom: Tests for _prepare_execution edge cases and protocol violations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from unittest.mock import Mock

import pytest

from henchman.agents.delegation import _prepare_execution, AgentProtocol
from henchman.agents.orchestrator_types import DelegationParams
from henchman.providers.base import Message


class TestPrepareExecutionUnitOfDoom:
    """Comprehensive tests for _prepare_execution edge cases."""
    
    def _make_runner(self) -> Mock:
        """Create a mock DelegationRunner."""
        runner = Mock()
        runner._prepare_delegation_context = Mock(return_value={})
        runner._assemble_delegation_input = Mock(return_value="Full task")
        runner.ledger = Mock()
        runner.ledger.goal = "Test mission"
        return runner
    
    # -----------------------------------------------------------------
    # TEST 1: Protocol Compliance Edge Cases
    # -----------------------------------------------------------------
    
    def test_object_without_any_protocol_attributes(self) -> None:
        """Test: Plain object without any protocol attributes."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        params.target_agent = object()  # Plain object
        
        with pytest.raises(TypeError, match="does not conform to AgentProtocol"):
            _prepare_execution(runner, params)
    
    def test_object_with_messages_but_no_clear_history(self) -> None:
        """Test: Object has messages but missing clear_history."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = []  # Has messages but no clear_history
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="does not conform to AgentProtocol"):
            _prepare_execution(runner, params)
    
    def test_object_with_clear_history_but_no_messages(self) -> None:
        """Test: Object has clear_history but missing messages."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            def clear_history(self) -> None:
                pass  # Has clear_history but no messages
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="does not conform to AgentProtocol"):
            _prepare_execution(runner, params)
    
    # -----------------------------------------------------------------
    # TEST 2: Type Safety Edge Cases
    # -----------------------------------------------------------------
    
    def test_messages_is_none(self) -> None:
        """Test: messages attribute exists but is None."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = None
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="messages=None"):
            _prepare_execution(runner, params)
    
    def test_messages_is_string(self) -> None:
        """Test: messages is a string (technically a Sequence but invalid)."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = "not a sequence of messages"
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="strings/bytes are not valid message sequences"):
            _prepare_execution(runner, params)
    
    def test_messages_is_bytes(self) -> None:
        """Test: messages is bytes (technically a Sequence but invalid)."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = b"not a sequence of messages"
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="strings/bytes are not valid message sequences"):
            _prepare_execution(runner, params)
    
    def test_clear_history_not_callable(self) -> None:
        """Test: clear_history exists but is not callable."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = []
            clear_history = "not a method"  # String, not callable
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="clear_history attribute is not callable"):
            _prepare_execution(runner, params)
    
    # -----------------------------------------------------------------
    # TEST 3: Sequence Validation Edge Cases
    # -----------------------------------------------------------------
    
    def test_messages_is_not_sequence(self) -> None:
        """Test: messages is not a Sequence at all."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = 42  # Integer, not a sequence
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="expected Sequence"):
            _prepare_execution(runner, params)
    
    def test_messages_sequence_with_wrong_types(self) -> None:
        """Test: messages is Sequence but contains wrong types."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = ["not a message", "also not a message"]  # Strings, not Messages
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        # This should fail when checking first message
        with pytest.raises(TypeError, match="messages appear to not be Message instances"):
            _prepare_execution(runner, params)
    
    def test_broken_sequence_cannot_index(self) -> None:
        """Test: messages is a broken sequence that raises on indexing."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenSequence:
            """A sequence that raises exceptions."""
            def __len__(self) -> int:
                return 1
            
            def __getitem__(self, index: int) -> Any:
                raise TypeError("Cannot index this broken sequence")
        
        class BrokenAgent:
            messages = BrokenSequence()
            def clear_history(self) -> None:
                pass
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(TypeError, match="expected Sequence"):
            _prepare_execution(runner, params)
    
    # -----------------------------------------------------------------
    # TEST 4: Execution Edge Cases
    # -----------------------------------------------------------------
    
    def test_clear_history_raises_exception(self) -> None:
        """Test: clear_history() method raises an exception."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = []
            def clear_history(self) -> None:
                raise RuntimeError("Failed to clear history")
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(RuntimeError, match="Failed to clear history"):
            _prepare_execution(runner, params)
    
    def test_clear_history_raises_attribute_error(self) -> None:
        """Test: clear_history() raises AttributeError (method disappeared)."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        class BrokenAgent:
            messages = []
            def clear_history(self) -> None:
                # Simulate method that disappears at runtime
                raise AttributeError("'BrokenAgent' object has no attribute 'clear_history'")
        
        params.target_agent = BrokenAgent()
        
        with pytest.raises(AttributeError, match="missing 'clear_history\\(\\)' method"):
            _prepare_execution(runner, params)
    
    # -----------------------------------------------------------------
    # TEST 5: Successful Execution
    # -----------------------------------------------------------------
    
    def test_valid_agent_passes_all_checks(self) -> None:
        """Test: Valid agent passes all validation checks."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        # Create a proper agent that conforms to AgentProtocol
        class ValidAgent:
            messages: Sequence[Message] = []
            
            def clear_history(self) -> None:
                self.messages = []
        
        params.target_agent = ValidAgent()
        
        # Should not raise any exceptions
        _prepare_execution(runner, params)
        
        # Verify params were updated
        assert params.full_task == "Full task"
        assert params.msg_start == 0
    
    def test_agent_with_existing_messages(self) -> None:
        """Test: Agent with existing messages gets correct msg_start."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        # Mock Message objects
        mock_message = Mock(spec=Message)
        mock_message.role = "user"
        mock_message.content = "Hello"
        
        class ValidAgent:
            messages: Sequence[Message] = [mock_message, mock_message]  # 2 messages
            
            def clear_history(self) -> None:
                self.messages = []
        
        params.target_agent = ValidAgent()
        
        _prepare_execution(runner, params)
        
        # msg_start should be 0 after clear_history() clears messages
        assert params.msg_start == 0
    
    # -----------------------------------------------------------------
    # TEST 6: Integration with AgentProtocol
    # -----------------------------------------------------------------
    
    def test_agent_actually_conforms_to_protocol(self) -> None:
        """Test: Agent that actually implements AgentProtocol passes isinstance check."""
        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        
        # Create agent that actually conforms to AgentProtocol
        class ProtocolCompliantAgent(AgentProtocol):  # type: ignore[misc]
            messages: Sequence[Message] = []
            
            def clear_history(self) -> None:
                self.messages = []
        
        params.target_agent = ProtocolCompliantAgent()
        
        # Verify it passes isinstance check
        assert isinstance(params.target_agent, AgentProtocol)
        
        # Should pass all validation
        _prepare_execution(runner, params)
        
        assert params.full_task == "Full task"