"""Refactored _prepare_execution with stronger type safety."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from henchman.agents.delegation import DelegationRunner, DelegationParams
    from henchman.providers.base import Message


def _prepare_execution_refactored(runner: DelegationRunner, params: DelegationParams) -> None:
    """Prepare agent and context for delegation execution - REFACTORED VERSION.
    
    Key improvements:
    1. Uses isinstance() with AgentProtocol for runtime type checking
    2. Better separation of concerns
    3. More defensive programming
    4. Clearer error messages
    
    Args:
        runner: The DelegationRunner that owns this delegation.
        params: Delegation parameters (must have target_agent set).
    
    Raises:
        ValueError: If params.target_agent is None or invalid.
        TypeError: If target_agent doesn't conform to AgentProtocol.
        RuntimeError: If agent operations fail after validation.
    """
    # -----------------------------------------------------------------
    # PHASE 1: Input Validation (Defensive Programming)
    # -----------------------------------------------------------------
    if params.target_agent is None:
        raise ValueError(
            f"Cannot prepare execution for agent '{params.target_role}': "
            "target_agent is None. This indicates a bug in delegation setup."
        )
    
    target_agent = params.target_agent
    
    # -----------------------------------------------------------------
    # PHASE 2: Protocol Compliance (Type Safety)
    # -----------------------------------------------------------------
    # Use runtime_checkable protocol for primary validation
    # This ensures consistency with type hints
    from henchman.agents.delegation import AgentProtocol
    
    if not isinstance(target_agent, AgentProtocol):
        # Provide detailed diagnostic information
        missing_attrs = []
        if not hasattr(target_agent, "messages"):
            missing_attrs.append("messages: Sequence[Message]")
        if not hasattr(target_agent, "clear_history"):
            missing_attrs.append("clear_history() -> None")
        
        error_msg = (
            f"Agent '{params.target_role}' (type: {type(target_agent).__name__}) "
            f"does not conform to AgentProtocol."
        )
        
        if missing_attrs:
            error_msg += f"\nMissing: {', '.join(missing_attrs)}"
        
        # Check for common mis-implementations
        if hasattr(target_agent, "messages") and target_agent.messages is None:
            error_msg += "\nNote: 'messages' attribute exists but is None (should be Sequence[Message])"
        
        if hasattr(target_agent, "clear_history") and not callable(target_agent.clear_history):
            error_msg += f"\nNote: 'clear_history' exists but is not callable (type: {type(target_agent.clear_history).__name__})"
        
        raise TypeError(error_msg)
    
    # -----------------------------------------------------------------
    # PHASE 3: Semantic Validation (Beyond Protocol Checking)
    # -----------------------------------------------------------------
    # @runtime_checkable doesn't validate types, only existence
    # We need additional checks for semantic correctness
    
    # 3.1: Validate messages is a proper Sequence (not string/bytes)
    if isinstance(target_agent.messages, (str, bytes)):
        raise TypeError(
            f"Agent '{params.target_role}' has invalid 'messages' attribute: "
            f"expected Sequence[Message], got {type(target_agent.messages).__name__} "
            f"(strings/bytes are technically Sequences but not valid for messages)"
        )
    
    if not isinstance(target_agent.messages, Sequence):
        raise TypeError(
            f"Agent '{params.target_role}' has invalid 'messages' attribute: "
            f"expected Sequence[Message], got {type(target_agent.messages).__name__}"
        )
    
    # 3.2: Validate clear_history is actually callable
    if not callable(target_agent.clear_history):
        raise TypeError(
            f"Agent '{params.target_role}' clear_history attribute is not callable: "
            f"got {type(target_agent.clear_history).__name__}"
        )
    
    # 3.3: Optional: Sample validation of message structure
    # This catches type mismatches early without checking entire sequence
    if target_agent.messages:
        try:
            first_msg = target_agent.messages[0]
            # Check for minimal Message-like structure
            if not (hasattr(first_msg, "role") and hasattr(first_msg, "content")):
                raise TypeError(
                    f"Agent '{params.target_role}' messages don't appear to be Message instances. "
                    f"First message missing 'role' or 'content' attributes."
                )
        except (IndexError, TypeError) as e:
            # Handle broken sequences
            raise TypeError(
                f"Agent '{params.target_role}' messages sequence appears broken: {e}"
            ) from e
    
    # -----------------------------------------------------------------
    # PHASE 4: Execution Preparation
    # -----------------------------------------------------------------
    # 4.1: Clear agent history
    try:
        target_agent.clear_history()
    except Exception as e:
        # Wrap any exception in RuntimeError with context
        raise RuntimeError(
            f"Failed to clear history for agent '{params.target_role}': {e}"
        ) from e
    
    # 4.2: Prepare delegation context
    prepared_brief = runner._prepare_delegation_context(params.target_role, params.brief)
    params.full_task = runner._assemble_delegation_input(
        params.task,
        prepared_brief,
        mission=runner.ledger.goal if runner.ledger else None,
    )
    
    # 4.3: Calculate message start position
    try:
        params.msg_start = len(target_agent.messages)
    except (AttributeError, TypeError) as e:
        # This should never happen after our validation, but be defensive
        raise RuntimeError(
            f"Failed to get message count for agent '{params.target_role}': {e}"
        ) from e