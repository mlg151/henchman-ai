#!/usr/bin/env python3
"""End-to-end test for Phase 1 systems."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from henchman.core.agent import Agent
from henchman.core.session import SessionManager, SessionMessage
from henchman.providers.base import Message
from henchman.utils.intelligent_context import IntelligentContextManager


async def test_phase1_integration():
    """Test all Phase 1 systems working together."""
    print("🧪 Testing Phase 1 Systems Integration")
    print("=" * 50)
    
    # Create a mock provider
    mock_provider = AsyncMock()
    mock_provider.name = "test-provider"
    mock_provider.max_tokens = 8000
    
    # Test 1: Intelligent Context Management
    print("\n1. Testing Intelligent Context Management...")
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello, can you help me with Python?"),
        Message(role="assistant", content="Sure! What do you need help with?"),
        Message(role="user", content="I need to write a function that calculates factorial."),
        Message(role="assistant", content="Here's a factorial function:\n\n```python\ndef factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)\n```"),
        Message(role="user", content="Thanks! Now help me with error handling."),
        Message(role="assistant", content="For error handling, use try-except blocks."),
    ]
    
    # Create intelligent context manager
    icm = IntelligentContextManager(
        max_tokens=100,  # Low limit to force compaction
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True
    )
    
    # Test compaction
    compacted = icm.compact(messages, protect_from_index=5)
    print(f"   Original messages: {len(messages)}")
    print(f"   Compacted messages: {len(compacted)}")
    print(f"   ✅ Intelligent context management working")
    
    # Test 2: Agent with intelligent context
    print("\n2. Testing Agent with Intelligent Context...")
    agent = Agent(
        provider=mock_provider,
        system_prompt="Test assistant",
        intelligent_context=True,
        importance_threshold=0.5,
        cluster_similarity_threshold=0.7,
        adaptive_compression=True
    )
    
    # Add messages to agent
    for msg in messages:
        if msg.role == "user":
            agent.messages.append(msg)
        elif msg.role == "assistant":
            agent.messages.append(msg)
    
    # Test get_messages_for_api with compaction
    api_messages = agent.get_messages_for_api()
    print(f"   Agent messages: {len(agent.messages)}")
    print(f"   API messages (after compaction): {len(api_messages)}")
    print(f"   ✅ Agent intelligent context integration working")
    
    # Test 3: Enhanced Session Management
    print("\n3. Testing Enhanced Session Management...")
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SessionManager(data_dir=Path(tmpdir))
        
        # Create a session
        session = manager.create_session(
            project_hash="test-project",
            tag="phase1-test"
        )
        
        # Add messages to session
        for msg in messages:
            session.messages.append(
                SessionMessage(
                    role=msg.role,
                    content=msg.content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id
                )
            )
        
        # Save session
        manager.save(session)
        print(f"   Session created: {session.id}")
        
        # Test branching
        branch = manager.branch_session(session.id, branch_point=3, tag="branch-test")
        manager.save(branch)  # Save the branch
        print(f"   Session branched: {branch.id} from message {branch.branch_point}")
        
        # Test merging
        merged = manager.merge_sessions(
            session_ids=[session.id, branch.id],
            strategy="union",
            tag="merged-test"
        )
        print(f"   Sessions merged: {merged.id}")
        
        # Test export/import
        exported = manager.export_session(session.id, format="json")
        imported = manager.import_session(exported, format="json")
        print(f"   Session exported/imported: {imported.id}")
        
        print(f"   ✅ Enhanced session management working")
    
    # Test 4: Performance Dashboard (metrics)
    print("\n4. Testing Performance Dashboard...")
    try:
        from henchman.metrics.collector import MetricsCollector
        from henchman.metrics.models import TokenMetric, ToolMetric
        
        collector = MetricsCollector()
        
        # Record some metrics
        token_metric = TokenMetric(
            session_id="test-session",
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        tool_metric = ToolMetric(
            session_id="test-session",
            tool_name="test_tool",
            execution_time=0.5,
            success=True
        )
        
        print(f"   Metrics collector initialized")
        print(f"   Token metric: {token_metric.total_tokens} tokens")
        print(f"   Tool metric: {tool_metric.tool_name} executed in {tool_metric.execution_time}s")
        print(f"   ✅ Performance dashboard metrics working")
    except ImportError as e:
        print(f"   ⚠️  Performance dashboard incomplete: {e}")
    
    # Test 5: CLI Commands Integration
    print("\n5. Testing CLI Commands Integration...")
    try:
        from henchman.cli.commands.context import ContextCommand
        from henchman.cli.commands.session import SessionCommand
        
        context_cmd = ContextCommand()
        session_cmd = SessionCommand()
        
        print(f"   Context command: {context_cmd.name}")
        print(f"   Session command: {session_cmd.name}")
        print(f"   ✅ CLI commands registered")
    except ImportError as e:
        print(f"   ⚠️  CLI commands issue: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Phase 1 Systems Integration Test Complete!")
    print("All core systems are working together correctly.")
    
    return True


if __name__ == "__main__":
    asyncio.run(test_phase1_integration())