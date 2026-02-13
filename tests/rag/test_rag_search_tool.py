"""Tests for the RagSearchTool."""

from unittest.mock import MagicMock

from henchman.rag.store import SearchResult
from henchman.tools.base import ToolKind
from henchman.tools.builtins.rag_search import RagSearchTool


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
        assert "required" in result.error.lower()

    async def test_execute_no_results(self) -> None:
        """No results returns appropriate message."""
        store = self._create_mock_store()
        store.search.return_value = []
        tool = RagSearchTool(store=store)
        result = await tool.execute(query="authentication")
        assert result.success is True
        assert "no relevant results" in result.content.lower()

    async def test_execute_with_results(self) -> None:
        """Results are formatted correctly."""
        store = self._create_mock_store()
        store.search.return_value = [
            SearchResult(
                content="def authenticate(user):\n    pass\n",
                file_path="auth.py",
                start_line=10,
                end_line=12,
                score=0.85,
                chunk_id="auth.py::0",
            ),
        ]
        tool = RagSearchTool(store=store)
        result = await tool.execute(query="authentication")

        assert result.success is True
        assert "auth.py" in result.content
        assert "10-12" in result.content
        assert "0.85" in result.content
        assert "def authenticate" in result.content

    async def test_execute_uses_default_top_k(self) -> None:
        """Default top_k is used when not specified."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store, top_k=10)
        await tool.execute(query="test")
        store.search.assert_called_once_with("test", top_k=10)

    async def test_execute_custom_top_k(self) -> None:
        """Custom top_k overrides default."""
        store = self._create_mock_store()
        tool = RagSearchTool(store=store, top_k=5)
        await tool.execute(query="test", top_k=3)
        store.search.assert_called_once_with("test", top_k=3)

    async def test_execute_handles_exception(self) -> None:
        """Exceptions are handled gracefully."""
        store = self._create_mock_store()
        store.search.side_effect = Exception("Database error")
        tool = RagSearchTool(store=store)
        result = await tool.execute(query="test")

        assert result.success is False
        assert "Database error" in result.error

    async def test_execute_multiple_results(self) -> None:
        """Multiple results are numbered correctly."""
        store = self._create_mock_store()
        store.search.return_value = [
            SearchResult(
                content="result 1",
                file_path="file1.py",
                start_line=1,
                end_line=5,
                score=0.9,
                chunk_id="file1.py::0",
            ),
            SearchResult(
                content="result 2",
                file_path="file2.py",
                start_line=10,
                end_line=15,
                score=0.8,
                chunk_id="file2.py::0",
            ),
        ]
        tool = RagSearchTool(store=store)
        result = await tool.execute(query="test")

        assert result.success is True
        assert "[1]" in result.content
        assert "[2]" in result.content
        assert "Found 2" in result.content
