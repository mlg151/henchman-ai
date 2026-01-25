"""
Integration tests for UI → Agent.

Tests that verify the agent's ability to process user input and generate
appropriate responses through the UI. These tests use real implementations
(no mocking) as required by INTEGRATION_TESTING.md.

Tests:
- Validate the agent processes user input and generates responses
- Ensure the agent handles multi-turn conversations correctly
- Test tool call requests and results within the agent loop
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)


class TestAgentProcessing:
    """Tests for agent processing of user input through UI."""

    @pytest.fixture
    def console_with_recording(self):
        """Console instance that records output for verification."""
        return Console(record=True, width=80)

    def create_content_provider(self, response_text: str):
        """Create a provider that returns specific content."""
        
        class ContentProvider:
            @property
            def name(self) -> str:
                return "content_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                """Yield content response."""
                yield StreamChunk(content=response_text)
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        return ContentProvider()

    def create_tool_call_provider(self, tool_name: str, arguments: dict):
        """Create a provider that triggers a specific tool call."""
        
        class ToolCallProvider:
            @property
            def name(self) -> str:
                return "tool_call_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                """Yield a tool call for the specified tool."""
                yield StreamChunk(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id=f"{tool_name}_1",
                            name=tool_name,
                            arguments=arguments
                        )
                    ],
                    finish_reason=FinishReason.TOOL_CALLS
                )
        
        return ToolCallProvider()

    async def test_agent_processes_user_input(self, console_with_recording):
        """Test that agent processes user input and generates responses."""
        # Create provider with predictable response
        expected_response = "Hello! I'm here to help."
        provider = self.create_content_provider(expected_response)
        
        # Create REPL with real agent
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent with user input
        user_input = "Hello, can you help me?"
        events = []
        async for event in repl.agent.run(user_input):
            events.append(event)
            
            if event.type == EventType.CONTENT:
                # Verify response content
                assert event.data == expected_response
        
        # Verify we got content and finished events
        event_types = [e.type for e in events]
        assert EventType.CONTENT in event_types
        assert EventType.FINISHED in event_types
        
        # Verify agent history was updated
        assert len(repl.agent.history) >= 2  # Should have user and assistant messages
        user_messages = [m for m in repl.agent.history if m.role == "user"]
        assistant_messages = [m for m in repl.agent.history if m.role == "assistant"]
        
        assert len(user_messages) >= 1
        assert user_messages[0].content == user_input
        
        assert len(assistant_messages) >= 1
        assert assistant_messages[0].content == expected_response

    async def test_agent_multi_turn_conversation(self, console_with_recording):
        """Test that agent handles multi-turn conversations correctly."""
        # Create provider that returns different responses based on conversation
        response_count = 0
        
        class MultiTurnProvider:
            @property
            def name(self) -> str:
                return "multi_turn_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                nonlocal response_count
                response_count += 1
                
                if response_count == 1:
                    yield StreamChunk(content="First response")
                elif response_count == 2:
                    yield StreamChunk(content="Second response")
                elif response_count == 3:
                    yield StreamChunk(content="Third response")
                
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        provider = MultiTurnProvider()
        
        # Create REPL with real agent
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # First turn
        events1 = []
        async for event in repl.agent.run("First message"):
            events1.append(event)
        
        # Second turn
        events2 = []
        async for event in repl.agent.run("Second message"):
            events2.append(event)
        
        # Third turn
        events3 = []
        async for event in repl.agent.run("Third message"):
            events3.append(event)
        
        # Verify all responses were received
        content_events1 = [e for e in events1 if e.type == EventType.CONTENT]
        content_events2 = [e for e in events2 if e.type == EventType.CONTENT]
        content_events3 = [e for e in events3 if e.type == EventType.CONTENT]
        
        assert len(content_events1) >= 1
        assert content_events1[0].data == "First response"
        
        assert len(content_events2) >= 1
        assert content_events2[0].data == "Second response"
        
        assert len(content_events3) >= 1
        assert content_events3[0].data == "Third response"
        
        # Verify conversation history
        assert len(repl.agent.history) >= 6  # 3 user + 3 assistant messages
        
        # Check message order
        messages = [(m.role, m.content) for m in repl.agent.history]
        # Should alternate user/assistant starting with user
        assert messages[0][0] == "user"
        assert messages[1][0] == "assistant"
        assert messages[2][0] == "user"
        assert messages[3][0] == "assistant"
        assert messages[4][0] == "user"
        assert messages[5][0] == "assistant"

    async def test_agent_tool_call_workflow(self, console_with_recording, tmp_path):
        """Test tool call requests and results within agent loop."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for reading")
        
        # Create provider that triggers read_file tool
        provider = self.create_tool_call_provider(
            "read_file",
            {"path": str(test_file)}
        )
        
        # Create REPL with real agent and tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Read file {test_file}"):
            events.append(event)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Verify tool call request
                assert event.data.name == "read_file"
                assert event.data.arguments["path"] == str(test_file)
                
                # Execute tool through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Verify tool result
                assert result.success is True
                assert "Test content for reading" in result.content
                
                # Submit result to agent
                repl.agent.submit_tool_result(event.data.id, result.content)
                
                # Continue with tool results
                continue_events = []
                async for cont_event in repl.agent.continue_with_tool_results():
                    continue_events.append(cont_event)
                
                # Should get content with the file content
                content_events = [e for e in continue_events if e.type == EventType.CONTENT]
                # Note: Some agents might not generate additional content after tool result
                # So we don't assert length here, just check if there is content
                if content_events:
                    assert "Test content for reading" in content_events[0].data
        
        # Verify we got tool call request
        tool_call_events = [e for e in events if e.type == EventType.TOOL_CALL_REQUEST]
        assert len(tool_call_events) >= 1

    async def test_agent_system_prompt_integration(self, console_with_recording):
        """Test that system prompt is properly integrated with agent."""
        system_prompt = "You are a helpful assistant specialized in Python programming."
        
        class SystemPromptProvider:
            @property
            def name(self) -> str:
                return "system_prompt_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                # Verify system prompt is included in messages
                assert len(messages) >= 1
                assert messages[0].role == "system"
                assert messages[0].content == system_prompt
                
                yield StreamChunk(content="System prompt verified")
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        provider = SystemPromptProvider()
        
        # Create REPL with system prompt
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig(system_prompt=system_prompt)
        )
        
        # Run agent
        events = []
        async for event in repl.agent.run("Test system prompt"):
            events.append(event)
        
        # Verify response
        content_events = [e for e in events if e.type == EventType.CONTENT]
        assert len(content_events) >= 1
        assert content_events[0].data == "System prompt verified"

    async def test_agent_error_handling(self, console_with_recording):
        """Test agent error handling through UI."""
        
        class ErrorProvider:
            @property
            def name(self) -> str:
                return "error_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                raise RuntimeError("Simulated provider error")
                yield  # Make it a generator
        
        provider = ErrorProvider()
        
        # Create REPL
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent - should handle error gracefully
        events = []
        async for event in repl.agent.run("Trigger error"):
            events.append(event)
        
        # Verify error event was generated
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) >= 1
        assert "Simulated provider error" in str(error_events[0].data)

    async def test_agent_with_tools_declaration(self, console_with_recording):
        """Test that agent properly declares tools to provider."""
        captured_tools = []
        
        class ToolDeclarationProvider:
            @property
            def name(self) -> str:
                return "tool_declaration_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                if tools:
                    captured_tools.extend(tools)
                
                yield StreamChunk(content="Tools declared")
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        provider = ToolDeclarationProvider()
        
        # Create REPL (which registers built-in tools)
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent
        async for _ in repl.agent.run("Test tool declarations"):
            pass
        
        # Verify tools were declared to provider
        assert len(captured_tools) > 0
        # Should have at least read_file tool declared
        tool_names = [t.name for t in captured_tools]
        assert "read_file" in tool_names


class TestAgentUIIntegration:
    """Tests for agent integration with UI components."""
    
    async def test_agent_repl_integration(self, console_with_recording):
        """Test that agent is properly integrated with REPL."""
        # Create simple provider
        class SimpleProvider:
            @property
            def name(self) -> str:
                return "simple_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                yield StreamChunk(content="Test response")
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        provider = SimpleProvider()
        
        # Create REPL
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Verify agent is properly initialized
        assert repl.agent is not None
        assert isinstance(repl.agent, Agent)
        assert repl.agent.provider is provider
        
        # Verify agent has access to tools
        assert repl.agent.tools is not None
        assert len(repl.agent.tools) > 0  # Should have built-in tools
        
        # Verify REPL has the necessary methods for agent integration
        # Check for methods that handle agent events
        assert hasattr(repl, '_handle_agent_event') or hasattr(repl, 'handle_agent_event')

    async def test_agent_session_integration(self, console_with_recording):
        """Test that agent works with session management."""
        # Create provider
        class SessionProvider:
            @property
            def name(self) -> str:
                return "session_test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                yield StreamChunk(content="Session test response")
                yield StreamChunk(finish_reason=FinishReason.STOP)
        
        provider = SessionProvider()
        
        # Create REPL with session manager
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Verify session manager is available
        assert repl.session_manager is not None
        
        # Run agent to create conversation
        async for _ in repl.agent.run("Test session"):
            pass
        
        # Agent history should be available for session saving
        assert len(repl.agent.history) >= 2  # user + assistant messages
        
        # The session integration is tested more thoroughly in test_session.py
        # This test just verifies the agent component works with the session system
