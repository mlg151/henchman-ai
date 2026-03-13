"""Debug the delegation bug."""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from henchman.agents.delegation import DelegationRunner
from henchman.core.events import EventType
from henchman.agents.orchestrator_types import DelegationParams

async def debug_bug():
    print("Debugging delegation bug...")
    
    # Mock dependencies
    mock_pool = MagicMock()
    mock_pool.get_agent.side_effect = ValueError("Agent 'unknown' not found")
    
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
    
    # Create delegation params - using correct structure
    params = DelegationParams(
        target_role="unknown",
        task="Test task",
        brief={"done_when": "Test done", "context": "Test context"}
    )
    
    print(f"Params: {params}")
    print(f"Params.target_role: {params.target_role}")
    
    # Collect events
    events = []
    try:
        async for event in runner.run_delegation(params):
            events.append(event)
            print(f"  Yielded: {event.type} - {event.data}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTotal events: {len(events)}")
    
    # Analyze events
    error_events = [e for e in events if e.type == EventType.ERROR]
    completed_events = [e for e in events if e.type == EventType.AGENT_COMPLETED]
    
    print(f"Error events: {len(error_events)}")
    print(f"Completed events: {len(completed_events)}")
    
    if error_events:
        print(f"Error message: {error_events[0].data}")
    
    if completed_events:
        print(f"Completion data: {completed_events[0].data}")
    
    # The bug: duplicate reporting
    if len(error_events) > 0 and len(completed_events) > 0:
        print("\n⚠️ BUG CONFIRMED: Both ERROR and AGENT_COMPLETED events for same failure")
        print("   This creates duplicate error reporting in the UI")
    
    return events

if __name__ == "__main__":
    events = asyncio.run(debug_bug())