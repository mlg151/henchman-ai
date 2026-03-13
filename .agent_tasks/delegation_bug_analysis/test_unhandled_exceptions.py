"""Test for unhandled exceptions in delegation error handling."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from henchman.agents.delegation import DelegationRunner
from henchman.core.events import EventType
from henchman.agents.orchestrator_types import DelegationParams


@pytest.mark.asyncio
async def test_unhandled_exceptions_in_agent_creation():
    """Test that exceptions other than ValueError are properly handled."""
    
    # Mock dependencies
    mock_pool = MagicMock()
    # Simulate an unexpected exception during agent creation
    mock_pool.get_agent.side_effect = RuntimeError("Unexpected error in agent creation")
    
    mock_settings = MagicMock()
    mock_settings.agents.max_delegation_depth = 3
    
    # Mock the callbacks
    mock_run_agent_loop = AsyncMock()
    mock_assess_completion = MagicMock()
    
    # Create delegation runner
    runner = DelegationRunner(
        pool=mock_pool,
        settings=mock_settings,
        shared_context=[],
        metrics=MagicMock(),
        run_agent_loop=mock_run_agent_loop,
        assess_completion=mock_assess_completion
    )
    
    # Create delegation params
    params = DelegationParams(
        target_role="engineer",
        task="Test task",
        brief={"done_when": "Test done", "context": "Test context"}
    )
    
    # Collect events - this should not crash
    events = []
    try:
        async for event in runner.run_delegation(params):
            events.append(event)
    except RuntimeError:
        pytest.fail("RuntimeError should have been caught and converted to ERROR event")
    
    # Should yield an ERROR event
    assert len(events) == 1, f"Expected 1 ERROR event, got {len(events)}"
    assert events[0].type == EventType.ERROR
    assert "Unexpected error in agent creation" in str(events[0].data)


@pytest.mark.asyncio
async def test_import_error_in_agent_creation():
    """Test that ImportError during agent creation is properly handled."""
    
    # Mock dependencies
    mock_pool = MagicMock()
    # Simulate ImportError (e.g., missing dependency)
    mock_pool.get_agent.side_effect = ImportError("Failed to import module")
    
    mock_settings = MagicMock()
    mock_settings.agents.max_delegation_depth = 3
    
    # Mock the callbacks
    mock_run_agent_loop = AsyncMock()
    mock_assess_completion = MagicMock()
    
    # Create delegation runner
    runner = DelegationRunner(
        pool=mock_pool,
        settings=mock_settings,
        shared_context=[],
        metrics=MagicMock(),
        run_agent_loop=mock_run_agent_loop,
        assess_completion=mock_assess_completion
    )
    
    # Create delegation params
    params = DelegationParams(
        target_role="engineer",
        task="Test task",
        brief={"done_when": "Test done", "context": "Test context"}
    )
    
    # Collect events - this should not crash
    events = []
    try:
        async for event in runner.run_delegation(params):
            events.append(event)
    except ImportError:
        pytest.fail("ImportError should have been caught and converted to ERROR event")
    
    # Should yield an ERROR event
    assert len(events) == 1, f"Expected 1 ERROR event, got {len(events)}"
    assert events[0].type == EventType.ERROR
    assert "Failed to import module" in str(events[0].data)


@pytest.mark.asyncio
async def test_attribute_error_in_agent_creation():
    """Test that AttributeError during agent creation is properly handled."""
    
    # Mock dependencies
    mock_pool = MagicMock()
    # Simulate AttributeError (e.g., missing attribute)
    mock_pool.get_agent.side_effect = AttributeError("'NoneType' object has no attribute 'x'")
    
    mock_settings = MagicMock()
    mock_settings.agents.max_delegation_depth = 3
    
    # Mock the callbacks
    mock_run_agent_loop = AsyncMock()
    mock_assess_completion = MagicMock()
    
    # Create delegation runner
    runner = DelegationRunner(
        pool=mock_pool,
        settings=mock_settings,
        shared_context=[],
        metrics=MagicMock(),
        run_agent_loop=mock_run_agent_loop,
        assess_completion=mock_assess_completion
    )
    
    # Create delegation params
    params = DelegationParams(
        target_role="engineer",
        task="Test task",
        brief={"done_when": "Test done", "context": "Test context"}
    )
    
    # Collect events - this should not crash
    events = []
    try:
        async for event in runner.run_delegation(params):
            events.append(event)
    except AttributeError:
        pytest.fail("AttributeError should have been caught and converted to ERROR event")
    
    # Should yield an ERROR event
    assert len(events) == 1, f"Expected 1 ERROR event, got {len(events)}"
    assert events[0].type == EventType.ERROR
    assert "'NoneType' object has no attribute 'x'" in str(events[0].data)


if __name__ == "__main__":
    import asyncio
    print("Running tests for unhandled exceptions...")
    
    async def run_all():
        await test_unhandled_exceptions_in_agent_creation()
        print("✓ test_unhandled_exceptions_in_agent_creation")
        
        await test_import_error_in_agent_creation()
        print("✓ test_import_error_in_agent_creation")
        
        await test_attribute_error_in_agent_creation()
        print("✓ test_attribute_error_in_agent_creation")
        
        print("\nAll tests passed!")
    
    asyncio.run(run_all())