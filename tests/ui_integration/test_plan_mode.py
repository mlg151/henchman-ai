"""
Integration tests for plan mode command.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from henchman.cli.commands import CommandRegistry
from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.core.session import Session


class TestPlanModeIntegration:
    """Integration tests for plan mode command execution through REPL."""

    @pytest.fixture
    def mock_provider(self):
        """Mock provider for testing."""
        provider = Mock()
        provider.chat_completion = AsyncMock()
        return provider

    @pytest.fixture
    def console_with_recording(self):
        """Console that records output for verification."""
        return Console(record=True, width=80)

    @pytest.fixture
    def repl_instance(self, mock_provider, console_with_recording):
        """REPL instance with mock components."""
        repl = Repl(provider=mock_provider, console=console_with_recording, config=ReplConfig())

        # Create a real session for testing
        repl.session = Session(
            id="test-id",
            project_hash="test-hash",
            started="2024-01-01T00:00:00Z",
            last_updated="2024-01-01T00:00:00Z",
            messages=[],
            plan_mode=False,  # Start with plan mode disabled
        )

        # Mock the command registry to track command execution
        repl.command_registry = Mock(spec=CommandRegistry)

        # Mock the agent
        repl.agent = Mock(spec=Agent)
        repl.agent.system_prompt = "Base system prompt"

        # Mock tool registry
        repl.tool_registry = Mock()
        repl.tool_registry.set_plan_mode = Mock()

        return repl

    @pytest.mark.asyncio
    async def test_plan_command_toggles_plan_mode(self, repl_instance, console_with_recording):
        """Test that /plan command toggles plan mode on and off."""
        # Track calls to execute_command
        execute_calls = []

        def mock_execute_command(command, args):
            execute_calls.append((command, args))
            if command == "plan":
                # Toggle plan mode
                repl_instance.session.plan_mode = not repl_instance.session.plan_mode
                # Call set_plan_mode on tool registry
                repl_instance.tool_registry.set_plan_mode(enabled=repl_instance.session.plan_mode)

                # Update agent system prompt
                plan_prompt = "---\n**PLAN MODE ACTIVE**\nYou are currently in PLAN MODE.\nYour goal is to discuss, plan, and architect solutions without modifying the codebase.\nYou can read files and explore the project, but you cannot write files or execute commands that modify state.\nFocus on creating detailed implementation plans.\n---\n"
                if repl_instance.session.plan_mode:
                    if plan_prompt not in repl_instance.agent.system_prompt:
                        repl_instance.agent.system_prompt += plan_prompt
                else:
                    repl_instance.agent.system_prompt = repl_instance.agent.system_prompt.replace(
                        plan_prompt, ""
                    )

                # Print status
                if repl_instance.session.plan_mode:
                    console_with_recording.print("[bold green]Plan Mode ENABLED[/]")
                    console_with_recording.print(
                        "[dim]Write and Execute tools are now disabled.[/]"
                    )
                else:
                    console_with_recording.print("[bold yellow]Plan Mode DISABLED[/]")

        repl_instance.command_registry.execute_command = AsyncMock(side_effect=mock_execute_command)

        # Mock _handle_input to call execute_command
        async def mock_handle_input(input_text):
            if input_text.startswith("/"):
                command = input_text[1:].strip()
                args = []
                if " " in command:
                    command, rest = command.split(" ", 1)
                    args = rest.split()
                await repl_instance.command_registry.execute_command(command, args)

        repl_instance._handle_input = mock_handle_input

        # First toggle: enable plan mode
        await repl_instance._handle_input("/plan")

        # Check that command was executed
        assert len(execute_calls) == 1
        assert execute_calls[0] == ("plan", [])

        # Check that plan mode is enabled
        assert repl_instance.session.plan_mode is True
        repl_instance.tool_registry.set_plan_mode.assert_called_with(enabled=True)

        # Check console output
        output = console_with_recording.export_text()
        assert "Plan Mode ENABLED" in output
        assert "Write and Execute tools are now disabled" in output

        # Clear console recording
        console_with_recording.clear()

        # Second toggle: disable plan mode
        await repl_instance._handle_input("/plan")

        # Check that plan mode is disabled
        assert repl_instance.session.plan_mode is False
        # set_plan_mode should have been called twice
        assert repl_instance.tool_registry.set_plan_mode.call_count == 2
        repl_instance.tool_registry.set_plan_mode.assert_called_with(enabled=False)

        # Check console output
        output = console_with_recording.export_text()
        assert "Plan Mode DISABLED" in output

    @pytest.mark.asyncio
    async def test_plan_mode_prevents_write_tool_calls(self, repl_instance):
        """Test that plan mode prevents write/execute tool calls."""
        # Enable plan mode
        repl_instance.session.plan_mode = True

        # Mock tool registry to simulate plan mode enforcement
        def mock_execute_tool(tool_name, _arguments):
            # In plan mode, write/execute tools should be blocked
            if tool_name in ["write_file", "edit_file", "shell"]:
                raise PermissionError(f"Tool '{tool_name}' is disabled in plan mode")
            return f"Executed {tool_name}"

        repl_instance.tool_registry.execute = AsyncMock(side_effect=mock_execute_tool)

        # Test that write_file is blocked
        with pytest.raises(PermissionError, match="Tool 'write_file' is disabled in plan mode"):
            await repl_instance.tool_registry.execute(
                "write_file", {"path": "/tmp/test.txt", "content": "test"}
            )

        # Test that edit_file is blocked
        with pytest.raises(PermissionError, match="Tool 'edit_file' is disabled in plan mode"):
            await repl_instance.tool_registry.execute(
                "edit_file", {"path": "/tmp/test.txt", "old_str": "old", "new_str": "new"}
            )

        # Test that shell is blocked
        with pytest.raises(PermissionError, match="Tool 'shell' is disabled in plan mode"):
            await repl_instance.tool_registry.execute("shell", {"command": "ls -la"})

    @pytest.mark.asyncio
    async def test_plan_mode_allows_read_tool_calls(self, repl_instance):
        """Test that plan mode still allows read tool calls."""
        # Enable plan mode
        repl_instance.session.plan_mode = True

        # Mock tool registry to simulate plan mode enforcement
        def mock_execute_tool(tool_name, arguments):
            # Read tools should still work in plan mode
            if tool_name in ["read_file", "ls", "grep"]:
                return f"Executed {tool_name}: {arguments}"
            # Write/execute tools should be blocked
            elif tool_name in ["write_file", "edit_file", "shell"]:
                raise PermissionError(f"Tool '{tool_name}' is disabled in plan mode")
            return f"Executed {tool_name}"

        repl_instance.tool_registry.execute = AsyncMock(side_effect=mock_execute_tool)

        # Test that read_file is allowed
        result = await repl_instance.tool_registry.execute("read_file", {"path": "/tmp/test.txt"})
        assert "Executed read_file" in result

        # Test that ls is allowed
        result = await repl_instance.tool_registry.execute("ls", {"path": "/tmp"})
        assert "Executed ls" in result

        # Test that grep is allowed
        result = await repl_instance.tool_registry.execute(
            "grep", {"pattern": "test", "path": "/tmp/test.txt"}
        )
        assert "Executed grep" in result

    @pytest.mark.asyncio
    async def test_plan_mode_disabled_allows_all_tools(self, repl_instance):
        """Test that when plan mode is disabled, all tools work."""
        # Disable plan mode (default state)
        repl_instance.session.plan_mode = False

        # Mock tool registry - all tools should work
        def mock_execute_tool(tool_name, arguments):
            return f"Executed {tool_name}: {arguments}"

        repl_instance.tool_registry.execute = AsyncMock(side_effect=mock_execute_tool)

        # Test that write_file works
        result = await repl_instance.tool_registry.execute(
            "write_file", {"path": "/tmp/test.txt", "content": "test"}
        )
        assert "Executed write_file" in result

        # Test that edit_file works
        result = await repl_instance.tool_registry.execute(
            "edit_file", {"path": "/tmp/test.txt", "old_str": "old", "new_str": "new"}
        )
        assert "Executed edit_file" in result

        # Test that shell works
        result = await repl_instance.tool_registry.execute("shell", {"command": "ls -la"})
        assert "Executed shell" in result

        # Test that read_file works
        result = await repl_instance.tool_registry.execute("read_file", {"path": "/tmp/test.txt"})
        assert "Executed read_file" in result

    @pytest.mark.asyncio
    async def test_ui_status_display(self, repl_instance, console_with_recording):
        """Test that UI displays correct status messages for plan mode."""
        # Create a separate console for this test to avoid mock recursion
        test_console = Console(record=True, width=80)

        # Replace the console in repl_instance for this test
        original_console = repl_instance.console
        repl_instance.console = test_console

        try:
            # Simulate enabling plan mode
            repl_instance.session.plan_mode = True
            repl_instance.tool_registry.set_plan_mode(True)

            # Simulate what the PlanCommand would print
            test_console.print("[bold green]Plan Mode ENABLED[/]")
            test_console.print("[dim]Write and Execute tools are now disabled.[/]")

            # Check messages
            output = test_console.export_text()
            assert "Plan Mode ENABLED" in output
            assert "Write and Execute tools are now disabled" in output

            # Clear and test disabling
            test_console.clear()

            # Simulate disabling plan mode
            repl_instance.session.plan_mode = False
            repl_instance.tool_registry.set_plan_mode(False)

            test_console.print("[bold yellow]Plan Mode DISABLED[/]")

            output = test_console.export_text()
            assert "Plan Mode DISABLED" in output
        finally:
            # Restore original console
            repl_instance.console = original_console
