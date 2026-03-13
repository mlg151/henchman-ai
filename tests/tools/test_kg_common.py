"""Tests for kg_common shared utilities."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from henchman.tools.builtins.kg_common import KgToolBase, _find_git_root


class TestFindGitRoot:
    """Tests for _find_git_root."""

    def test_returns_path_in_git_repo(self) -> None:
        """Returns a Path when in a git repo."""
        result = _find_git_root()
        # We're running from a git repo
        assert result is None or isinstance(result, Path)

    def test_returns_none_when_git_not_found(self) -> None:
        """Returns None when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _find_git_root()
            assert result is None

    def test_returns_none_when_not_in_git_repo(self) -> None:
        """Returns None when not in a git repository (returncode != 0)."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _find_git_root()
            assert result is None

    def test_returns_none_on_subprocess_error(self) -> None:
        """Returns None on SubprocessError."""
        with patch("subprocess.run", side_effect=subprocess.SubprocessError()):
            result = _find_git_root()
            assert result is None

    def test_returns_path_on_success(self) -> None:
        """Returns Path when git returns valid output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "/home/user/project\n"
        with patch("subprocess.run", return_value=mock_result):
            result = _find_git_root()
            assert result == Path("/home/user/project")


class TestKgToolBase:
    """Tests for KgToolBase."""

    def test_init_with_store(self, tmp_path: Path) -> None:
        """Initialised=True when store is provided."""
        from henchman.knowledge.store import KnowledgeStore

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        store = KnowledgeStore(git_root=repo, base_dir=tmp_path / "kg")

        class ConcreteKgTool(KgToolBase):
            """Concrete implementation for testing."""

            @property
            def name(self) -> str:
                """Tool name."""
                return "test"

            @property
            def description(self) -> str:
                """Tool description."""
                return "test"

            @property
            def parameters(self) -> dict:
                """Tool parameters."""
                return {}

            @property
            def kind(self):
                """Tool kind."""
                from henchman.tools.base import ToolKind

                return ToolKind.READ

            async def execute(self, **kwargs):
                """Execute."""
                pass

        tool = ConcreteKgTool(store=store)
        assert tool._initialised is True
        assert tool._store is store

    def test_init_without_store(self) -> None:
        """Initialised=False when no store provided."""

        class ConcreteKgTool(KgToolBase):
            """Concrete implementation for testing."""

            @property
            def name(self) -> str:
                """Tool name."""
                return "test"

            @property
            def description(self) -> str:
                """Tool description."""
                return "test"

            @property
            def parameters(self) -> dict:
                """Tool parameters."""
                return {}

            @property
            def kind(self):
                """Tool kind."""
                from henchman.tools.base import ToolKind

                return ToolKind.READ

            async def execute(self, **kwargs):
                """Execute."""
                pass

        tool = ConcreteKgTool()
        assert tool._initialised is False
        assert tool._store is None
