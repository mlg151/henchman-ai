"""Tests for the RagSearchTool."""

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.rag.repo_id import compute_repository_id
from henchman.rag.store import SearchResult
from henchman.tools.base import ToolKind
from henchman.tools.builtins.rag_search import RagSearchTool


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "auth.py").write_text("\n" * 9 + "def authenticate(user):\n    pass\n\n")
    (tmp_path / "file1.py").write_text("result 1\n" + "\n" * 4)
    (tmp_path / "file2.py").write_text("\n" * 9 + "result 2\n" + "\n" * 5)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def qualify(root: Path, item: SearchResult) -> SearchResult:
    item.source_sha256 = hashlib.sha256((root / item.file_path).read_bytes()).hexdigest()
    item.repository_id = compute_repository_id(root)
    item.evidence_version = 1
    item.content = "".join(
        (root / item.file_path)
        .read_text()
        .splitlines(keepends=True)[item.start_line - 1 : item.end_line]
    )
    return item


class TestRagSearchTool:
    """Tests for the RagSearchTool."""

    def _create_mock_store(self) -> MagicMock:
        """Create a mock vector store."""
        store = MagicMock()
        store.search.return_value = []
        return store

    def test_name(self) -> None:
        """Tool has correct name."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store)
        assert tool.name == "rag_search"

    def test_description(self) -> None:
        """Tool has description."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store)
        assert "semantic" in tool.description.lower() or "search" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store)
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store)
        params = tool.parameters
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "query" in params["required"]

    async def test_execute_empty_query(self) -> None:
        """Empty query returns error."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store)
        result = await tool.execute(query="")
        assert result.success is False
        assert "query must contain" in result.error.lower()

    async def test_execute_no_results(self, repository: Path) -> None:
        """No results returns appropriate message."""
        store = self._create_mock_store()
        store.search.return_value = []
        tool = RagSearchTool(store=store, project_root=repository)
        result = await tool.execute(query="authentication")
        assert result.success is True
        assert json.loads(result.content)["items"] == []
        assert "do not prove absence" in result.content

    async def test_execute_with_results(self, repository: Path) -> None:
        """Results are formatted correctly."""
        store = self._create_mock_store()
        store.search.return_value = [
            qualify(
                repository,
                SearchResult(
                    content="def authenticate(user):\n    pass\n",
                    file_path="auth.py",
                    start_line=10,
                    end_line=12,
                    score=0.85,
                    chunk_id="auth.py::0",
                ),
            ),
        ]
        tool = RagSearchTool(store=store, project_root=repository)
        result = await tool.execute(query="authentication")

        assert result.success is True
        assert "auth.py" in result.content
        assert json.loads(result.content)["items"][0]["start_line"] == 10
        assert json.loads(result.content)["items"][0]["end_line"] == 12
        assert "0.85" in result.content
        assert "def authenticate" in result.content

    async def test_execute_uses_default_top_k(self, repository: Path) -> None:
        """Default top_k is used when not specified."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store, top_k=10, project_root=repository)
        await tool.execute(query="test")
        store.search.assert_called_once_with("test", top_k=10)

    async def test_execute_custom_top_k(self, repository: Path) -> None:
        """Custom top_k overrides default."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store, top_k=5, project_root=repository)
        await tool.execute(query="test", top_k=3)
        store.search.assert_called_once_with("test", top_k=3)

    async def test_execute_handles_exception(self, repository: Path) -> None:
        """Exceptions are handled gracefully."""
        store = self._create_mock_store()
        store.search.side_effect = Exception("Database error")
        tool = RagSearchTool(store=store, project_root=repository)
        result = await tool.execute(query="test")

        assert result.success is False
        assert "Database error" in result.error

    async def test_execute_multiple_results(self, repository: Path) -> None:
        """Multiple results are numbered correctly."""
        store = self._create_mock_store()
        store.search.return_value = [
            qualify(
                repository,
                SearchResult(
                    content="result 1",
                    file_path="file1.py",
                    start_line=1,
                    end_line=5,
                    score=0.9,
                    chunk_id="file1.py::0",
                ),
            ),
            qualify(
                repository,
                SearchResult(
                    content="result 2",
                    file_path="file2.py",
                    start_line=10,
                    end_line=15,
                    score=0.8,
                    chunk_id="file2.py::0",
                ),
            ),
        ]
        tool = RagSearchTool(store=store, project_root=repository)
        result = await tool.execute(query="test")

        assert result.success is True
        assert [item["file_path"] for item in json.loads(result.content)["items"]] == [
            "file1.py",
            "file2.py",
        ]
