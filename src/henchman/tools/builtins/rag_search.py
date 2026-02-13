"""RAG search tool for semantic code search.

This tool provides semantic search over git-tracked files using
the RAG (Retrieval Augmented Generation) system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from henchman.rag.store import VectorStore


class RagSearchTool(Tool):
    """Search codebase using semantic similarity.

    This tool performs semantic search over indexed git-tracked files,
    returning the most relevant code chunks for a given query.

    Attributes:
        store: The vector store to search.
        top_k: Default number of results to return.
    """

    def __init__(
        self,
        store: VectorStore,
        top_k: int = 5,
    ) -> None:
        """Initialize the RAG search tool.

        Args:
            store: Vector store containing indexed code chunks.
            top_k: Default number of results to return.
        """
        self._store = store
        self._top_k = top_k

    @property
    def name(self) -> str:
        """Tool name."""
        return "rag_search"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Search the codebase using semantic similarity. "
            "Use this to find relevant code snippets, function definitions, "
            "documentation, or any content related to a natural language query. "
            "Returns the most similar code chunks from git-tracked files."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language query to search for. "
                        "Describe what you're looking for in plain English, e.g., "
                        "'authentication middleware', 'database connection setup', "
                        "'error handling for API requests'."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": f"Number of results to return (default: {self._top_k})",
                    "default": self._top_k,
                },
            },
            "required": ["query"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        query: str = "",
        top_k: int | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Search for relevant code chunks.

        Args:
            query: Natural language query to search for.
            top_k: Number of results to return.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with search results or error.
        """
        if not query:
            return ToolResult(
                content="Error: query is required",
                success=False,
                error="query parameter is required",
            )

        k = top_k if top_k is not None else self._top_k

        try:
            results = self._store.search(query, top_k=k)

            if not results:
                return ToolResult(
                    content="No relevant results found for the query.",
                    success=True,
                )

            # Format results for LLM
            formatted_parts = [f"Found {len(results)} relevant code chunks:\n"]
            for i, result in enumerate(results, 1):
                formatted_parts.append(
                    f"\n[{i}] {result.file_path} "
                    f"(lines {result.start_line}-{result.end_line}, "
                    f"score: {result.score:.3f})\n"
                )
                formatted_parts.append("```\n")
                formatted_parts.append(result.content)
                if not result.content.endswith("\n"):
                    formatted_parts.append("\n")
                formatted_parts.append("```\n")

            content = "".join(formatted_parts)

            return ToolResult(
                content=content,
                success=True,
            )

        except Exception as e:
            return ToolResult(
                content=f"Error searching: {e}",
                success=False,
                error=str(e),
            )
