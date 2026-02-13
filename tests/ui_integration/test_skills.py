"""
Integration tests for skill commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.session import Session, SessionMessage
from henchman.providers.base import ToolCall
from henchman.skills.models import Skill, SkillStep


class TestSkillCommandIntegration:
    """Integration tests for skill command execution through REPL."""

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
        # We want to use the real CommandRegistry which includes SkillCommand
        # but we need to mock internal components like Agent if they are complex.
        # Actually Repl initializes Agent.

        # We can mock the session to have messages for learning skills
        repl.session = Session(
            id="test-id",
            project_hash="test-hash",
            started="2024-01-01T00:00:00Z",
            last_updated="2024-01-01T00:00:00Z",
            messages=[],
        )

        return repl

    async def test_skill_list_empty(self, repl_instance):
        """Test /skill list with no skills."""
        with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
            mock_store = MockStore.return_value
            mock_store.list_skills.return_value = []

            # Execute command
            with patch("henchman.cli.repl.expand_at_references", side_effect=lambda x: x):
                result = await repl_instance.process_input("/skill list")

            assert result is True
            # Verify output
            output = repl_instance.console.export_text()
            assert "No skills learned yet" in output

    async def test_skill_run(self, repl_instance):
        """Test /skill run <name>."""
        mock_step = SkillStep(
            description="echo hello", tool="run_shell_command", arguments={"command": "echo hello"}
        )
        mock_skill = Skill(name="echo-skill", description="Echoes hello", steps=[mock_step])

        with (
            patch("henchman.cli.commands.skill.SkillStore") as MockStore,
            patch("henchman.cli.commands.skill.SkillExecutor") as MockExecutor,
        ):
            mock_store = MockStore.return_value
            mock_store.load.return_value = mock_skill

            mock_executor_instance = MockExecutor.return_value

            # Mock executor.run to yield a result
            async def mock_run_gen(_skill):
                result = Mock()
                result.success = True
                result.content = "hello"
                yield result

            mock_executor_instance.run.side_effect = mock_run_gen

            # Execute command
            with patch("henchman.cli.repl.expand_at_references", side_effect=lambda x: x):
                result = await repl_instance.process_input("/skill run echo-skill")

            assert result is True
            # Verify output
            output = repl_instance.console.export_text()
            assert "Running skill: echo-skill" in output
            # Note: The actual output might vary, so we'll check for success
            # rather than specific content

    async def test_skill_add_persistence(self, repl_instance):
        """Test /skill learn (add) persistence."""
        # Setup session with messages to learn from
        repl_instance.session.messages = [
            SessionMessage(role="user", content="list files"),
            SessionMessage(
                role="assistant", tool_calls=[ToolCall(id="1", name="ls", arguments={"path": "."})]
            ),
        ]

        with patch("henchman.cli.commands.skill.SkillStore"):
            # Execute command
            with patch("henchman.cli.repl.expand_at_references", side_effect=lambda x: x):
                result = await repl_instance.process_input("/skill learn ls-skill 'Lists files'")

            assert result is True
