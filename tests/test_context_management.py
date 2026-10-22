"""Validation tests for the project's copilot instructions.

These tests verify that the shared instruction file (backed by
.github/copilot-instructions.md, reached via .claude/CLAUDE.md) is present
and retains its core project guidance sections.
"""

from pathlib import Path


class TestCopilotInstructions:
    """The shared copilot instructions must stay present and complete."""

    def setup_method(self):
        """Load copilot instructions for testing."""
        self.copilot_path = Path(__file__).parent.parent / ".github" / "copilot-instructions.md"
        with open(self.copilot_path, encoding="utf-8") as f:
            self.content = f.read()

    def test_file_exists_and_is_nonempty(self):
        assert self.copilot_path.is_file(), "copilot-instructions.md is missing"
        assert len(self.content) > 1000, "copilot instructions are too short"

    def test_architecture_section_exists(self):
        assert "## Architecture" in self.content

    def test_key_pattern_sections_exist(self):
        required = [
            "## Key Patterns",
            "### Providers",
            "### Core Types, Registry & Agent Loop",
            "### REPL, Tools & Config",
            "### Session, MCP & Extensions",
            "## Conventions",
            "## Testing",
            "## Development Workflow",
        ]
        for section in required:
            assert section in self.content, f"Missing instruction section: {section}"

    def test_no_agent_tasks_convention(self):
        """The .agent_tasks workspace convention is removed; instructions must not reference it."""
        assert ".agent_tasks" not in self.content
