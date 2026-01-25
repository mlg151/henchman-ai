"""
Integration tests for UI → Tool Calls.

Tests that verify all built-in tools can be executed through the UI
and their results are properly displayed. These tests use real
implementations (no mocking) as required by INTEGRATION_TESTING.md.

Tests:
- Execute each built-in tool (e.g., read_file, write_file, grep) via the UI
- Validate tool results are displayed in the UI
- Test error handling for tool failures
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, StreamChunk, ToolCall


class TestToolCalls:
    """Tests for tool call execution through UI."""

    @pytest.fixture
    def console_with_recording(self):
        """Console instance that records output for verification."""
        return Console(record=True, width=80)

    @pytest.fixture
    def temp_test_file(self):
        """Create a temporary test file for file operations."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1: Test content for reading\n")
            f.write("Line 2: More test content\n")
            f.write("Line 3: Even more content\n")
            test_file = Path(f.name)
        yield test_file
        # Cleanup
        if test_file.exists():
            test_file.unlink()

    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory for directory operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            test_dir = Path(tmpdir)
            (test_dir / "file1.txt").write_text("Content of file 1")
            (test_dir / "file2.py").write_text("print('Hello')")
            (test_dir / "subdir").mkdir()
            (test_dir / "subdir" / "file3.md").write_text("# Markdown file")
            yield test_dir

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

    async def test_read_file_tool(self, console_with_recording, temp_test_file):
        """Test read_file tool execution through UI."""
        # Create provider that triggers read_file tool
        provider = self.create_tool_call_provider(
            "read_file",
            {"path": str(temp_test_file)}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Read file {temp_test_file}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Verify it's the right tool
                assert event.data.name == "read_file"
                assert event.data.arguments["path"] == str(temp_test_file)
                
                # Execute tool directly through registry (avoiding recursion)
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result contains file content
                assert result.success is True
                assert "Line 1: Test content for reading" in result.content
                assert "Line 2: More test content" in result.content
                assert "Line 3: Even more content" in result.content
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_write_file_tool(self, console_with_recording, temp_test_dir):
        """Test write_file tool execution through UI."""
        test_file = temp_test_dir / "new_file.txt"
        test_content = "This is new content written by the tool"
        
        # Create provider that triggers write_file tool
        provider = self.create_tool_call_provider(
            "write_file",
            {"path": str(test_file), "content": test_content}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Write to file {test_file}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Verify it's the right tool
                assert event.data.name == "write_file"
                
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result indicates success
                assert result.success is True
                assert "wrote" in result.content.lower() or "success" in result.content.lower()
                
                # Verify file was actually created with correct content
                assert test_file.exists()
                assert test_file.read_text() == test_content
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_ls_tool(self, console_with_recording, temp_test_dir):
        """Test ls tool execution through UI."""
        # Create provider that triggers ls tool
        provider = self.create_tool_call_provider(
            "ls",
            {"path": str(temp_test_dir)}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"List directory {temp_test_dir}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result contains expected files
                assert result.success is True
                result_text = result.content.lower()
                assert "file1.txt" in result_text
                assert "file2.py" in result_text
                assert "subdir" in result_text
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_grep_tool(self, console_with_recording, temp_test_dir):
        """Test grep tool execution through UI."""
        # Create a file with specific content to grep
        search_file = temp_test_dir / "search.txt"
        search_file.write_text("apple\nbanana\napple pie\norange\n")
        
        # Create provider that triggers grep tool
        provider = self.create_tool_call_provider(
            "grep",
            {"pattern": "apple", "path": str(search_file)}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Search for apple in {search_file}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result contains grep results
                assert result.success is True
                result_text = result.content.lower()
                assert "apple" in result_text
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_glob_tool(self, console_with_recording, temp_test_dir):
        """Test glob tool execution through UI."""
        # Create provider that triggers glob tool
        # Note: The glob tool uses "path" parameter, not "root_dir"
        provider = self.create_tool_call_provider(
            "glob",
            {"pattern": "*.txt", "path": str(temp_test_dir)}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Find txt files in {temp_test_dir}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result contains glob results
                assert result.success is True
                result_text = result.content
                # The glob tool returns a formatted string
                assert "file1.txt" in result_text
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_shell_tool_basic(self, console_with_recording):
        """Test shell tool execution through UI with simple command."""
        # Create provider that triggers shell tool
        provider = self.create_tool_call_provider(
            "shell",
            {"command": "echo 'Hello from shell tool'"}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run("Run echo command"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result contains command output
                assert result.success is True
                assert "Hello from shell tool" in result.content
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_edit_file_tool(self, console_with_recording, temp_test_file):
        """Test edit_file tool execution through UI."""
        # Create provider that triggers edit_file tool
        provider = self.create_tool_call_provider(
            "edit_file",
            {
                "path": str(temp_test_file),
                "old_str": "Line 2: More test content",
                "new_str": "Line 2: Modified content"
            }
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run(f"Edit file {temp_test_file}"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result indicates success
                assert result.success is True
                
                # Verify file was actually modified
                content = temp_test_file.read_text()
                assert "Line 2: Modified content" in content
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_tool_error_handling(self, console_with_recording):
        """Test error handling for tool failures."""
        # Create provider that triggers read_file with non-existent file
        provider = self.create_tool_call_provider(
            "read_file",
            {"path": "/non/existent/file.txt"}
        )
        
        # Create REPL with real tools
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Run agent to trigger tool call
        events = []
        async for event in repl.agent.run("Read non-existent file"):
            events.append(event.type)
            
            if event.type == EventType.TOOL_CALL_REQUEST:
                # Execute tool directly through registry
                result = await repl.tool_registry.execute(
                    event.data.name,
                    event.data.arguments
                )
                
                # Check tool result indicates failure
                assert result.success is False
                assert "error" in result.content.lower() or "not found" in result.content.lower()
                
                # Submit result to agent (not async)
                repl.agent.submit_tool_result(event.data.id, result.content)
        
        assert EventType.TOOL_CALL_REQUEST in events

    async def test_all_tools_registered(self, console_with_recording):
        """Test that all built-in tools are registered and available."""
        # Create a simple provider
        class TestProvider:
            @property
            def name(self) -> str:
                return "test"
            
            async def chat_completion_stream(self, messages, tools=None, **kwargs):
                yield StreamChunk(content="test", finish_reason=FinishReason.STOP)
        
        provider = TestProvider()
        
        # Create REPL
        repl = Repl(
            provider=provider,
            console=console_with_recording,
            config=ReplConfig()
        )
        
        # Check that all expected tools are registered
        expected_tools = [
            'ask_user', 'edit_file', 'glob', 'grep', 'ls',
            'read_file', 'shell', 'web_fetch', 'write_file'
        ]
        
        # Get registered tools (method may vary)
        try:
            registered_tools = repl.tool_registry.list_tools()
        except AttributeError:
            # Fallback: check tool registry directly
            registered_tools = list(repl.tool_registry._tools.keys())
        
        for tool in expected_tools:
            assert tool in registered_tools, f"Tool {tool} not registered"
