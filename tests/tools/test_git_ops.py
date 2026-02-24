"""Tests for git_ops tool."""

import tempfile

from henchman.tools.base import ToolKind
from henchman.tools.builtins.git_ops import GitOpsTool


class TestGitOpsTool:
    """Tests for GitOpsTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = GitOpsTool()
        assert tool.name == "git_ops"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = GitOpsTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind (auto-approved)."""
        tool = GitOpsTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = GitOpsTool()
        params = tool.parameters
        assert "action" in params["properties"]
        assert "action" in params["required"]

    async def test_empty_action(self) -> None:
        """Handle empty action."""
        tool = GitOpsTool()
        result = await tool.execute(action="")
        assert result.success is False
        assert "no action" in result.content.lower()

    async def test_unknown_action(self) -> None:
        """Handle unknown action."""
        tool = GitOpsTool()
        result = await tool.execute(action="reset_hard")
        assert result.success is False
        assert "unknown" in result.content.lower()

    async def test_status(self) -> None:
        """Get git status of current repo."""
        tool = GitOpsTool()
        result = await tool.execute(action="status")
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_log(self) -> None:
        """Get git log."""
        tool = GitOpsTool()
        result = await tool.execute(action="log", max_count=5)
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_branch_list(self) -> None:
        """List git branches."""
        tool = GitOpsTool()
        result = await tool.execute(action="branch_list")
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_stash_list(self) -> None:
        """List git stashes."""
        tool = GitOpsTool()
        result = await tool.execute(action="stash_list")
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_blame_requires_path(self) -> None:
        """Blame requires a file path."""
        tool = GitOpsTool()
        result = await tool.execute(action="blame")
        assert result.success is False
        assert "path" in result.content.lower()

    async def test_blame_with_path(self) -> None:
        """Blame a tracked file."""
        tool = GitOpsTool()
        result = await tool.execute(action="blame", path="pyproject.toml")
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_blame_with_line_range(self) -> None:
        """Blame specific lines."""
        tool = GitOpsTool()
        result = await tool.execute(action="blame", path="pyproject.toml", start_line=1, end_line=5)
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_show_default(self) -> None:
        """Show HEAD commit."""
        tool = GitOpsTool()
        result = await tool.execute(action="show")
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_show_with_stat(self) -> None:
        """Show commit with stat."""
        tool = GitOpsTool()
        result = await tool.execute(action="show", stat=True)
        assert result.success is True
        assert isinstance(result.content, str)

    async def test_diff_branches_requires_refs(self) -> None:
        """diff_branches requires both ref and ref2."""
        tool = GitOpsTool()
        result = await tool.execute(action="diff_branches", ref="main")
        assert result.success is False
        assert "ref" in result.content.lower()

    async def test_log_with_stat(self) -> None:
        """Log with stat output."""
        tool = GitOpsTool()
        result = await tool.execute(action="log", max_count=3, stat=True)
        assert result.success is True

    async def test_log_with_path(self) -> None:
        """Log filtered to a specific file."""
        tool = GitOpsTool()
        result = await tool.execute(action="log", path="pyproject.toml", max_count=3)
        assert result.success is True

    async def test_status_in_non_git_dir(self) -> None:
        """Handle non-git directory gracefully."""
        tool = GitOpsTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(action="status", cwd=tmpdir)
            assert result.success is False
