"""RAG search tool for semantic code search.

This tool provides semantic search over git-tracked files using
the RAG (Retrieval Augmented Generation) system.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from henchman.rag.evidence import (
    EVIDENCE_VERSION,
    MAX_FILE_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_QUERY_CHARS,
    MAX_SOURCE_BYTES,
    MAX_TOP_K,
    EvidenceUnavailable,
    SourceSnapshot,
    WorkspaceBinding,
    WorkspaceSnapshot,
    read_source,
    validate_query,
)
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
        self: RagSearchTool,
        store: VectorStore,
        top_k: int = 5,
        *,
        project_root: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        """Initialize the RAG search tool.

        Args:
            store: Vector store containing indexed code chunks.
            top_k: Default number of results to return.
        """
        self._store = store
        self._top_k = top_k
        self._binding = WorkspaceBinding.bind(project_root) if project_root is not None else None
        self._manifest_path = manifest_path

    @property
    def name(self: RagSearchTool) -> str:
        """Tool name."""
        return "rag_search"

    @property
    def description(self: RagSearchTool) -> str:
        """Tool description."""
        return (
            "Search the codebase using semantic similarity. "
            "Use this to find relevant code snippets, function definitions, "
            "documentation, or any content related to a natural language query. "
            "Returns bounded current-file evidence from git-tracked files. "
            "Stale or legacy candidates require reindexing; no automatic indexing is performed."
        )

    @property
    def parameters(self: RagSearchTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_QUERY_CHARS,
                    "description": (
                        "Natural language query to search for. "
                        "Describe what you're looking for in plain English, e.g., "
                        "'authentication middleware', 'database connection setup', "
                        "'error handling for API requests'."
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_TOP_K,
                    "description": f"Number of results to return (default: {self._top_k})",
                    "default": self._top_k,
                },
            },
            "required": ["query"],
        }

    @property
    def kind(self: RagSearchTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: RagSearchTool,
        query: str = "",
        top_k: int | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Search for relevant code chunks.

        Args:
            query: Natural language query to search for.
            top_k: Number of results to return.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with search results or error.
        """
        k = top_k if top_k is not None else self._top_k
        try:
            validate_query(query, k)
            if self._binding is None:
                raise EvidenceUnavailable("RAG search requires an explicitly bound project_root")
            workspace = self._binding.snapshot()
            if self._manifest_path is not None:
                from henchman.rag.indexer import IndexManifest

                manifest = IndexManifest.load(self._manifest_path)
                if (
                    manifest.evidence_version != EVIDENCE_VERSION
                    or manifest.repository_id != self._binding.repository_id
                    or manifest.generation_id is None
                ):
                    raise EvidenceUnavailable("index_unavailable_reindex_required")
                if (
                    not isinstance(manifest.collection_id, str)
                    or manifest.collection_id != self._store.collection_id
                ):
                    raise EvidenceUnavailable("index_collection_unavailable_reindex_required")
                query_embedder = self._store.embedder
                query_model = query_embedder.model_name
                if (
                    not isinstance(query_model, str)
                    or not query_model.strip()
                    or manifest.model_name != query_model
                ):
                    raise EvidenceUnavailable("index_embedding_profile_changed_reindex_required")
            results = self._store.search(query, top_k=k)
            result = _current_report(workspace, results, k)
            if self._manifest_path is not None and (
                manifest.collection_id != self._store.collection_id
                or IndexManifest.load(self._manifest_path) != manifest
                or self._store.embedder is not query_embedder
                or query_embedder.model_name != query_model
            ):
                raise EvidenceUnavailable("index_generation_changed_reindex_required")
            return result
        except Exception as exc:
            from henchman.utils.evidence_redaction import EvidenceRedactor

            reason = EvidenceRedactor().text(str(exc))
            if len(reason) > 1024:
                reason = "RAG search failed [truncated: oversized diagnostic omitted]"
            return ToolResult(
                content=json.dumps({"items": [], "error": reason}), success=False, error=reason
            )


def _qualify_candidate(
    workspace: WorkspaceSnapshot,
    result: Any,
    sources: dict[str, SourceSnapshot],
) -> dict[str, object]:
    """Only current bytes may substantiate a stored similarity candidate."""
    if type(result.evidence_version) is not int or result.evidence_version != EVIDENCE_VERSION:
        raise EvidenceUnavailable("legacy_evidence_reindex_required")
    if result.repository_id != workspace.binding.repository_id:
        raise EvidenceUnavailable("foreign_repository_reindex_required")
    digest = result.source_sha256
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise EvidenceUnavailable("source_digest_unavailable_reindex_required")
    if not isinstance(result.file_path, str):
        raise EvidenceUnavailable("source_path_invalid")
    source = sources.get(result.file_path)
    if source is None:
        source = read_source(
            workspace,
            result.file_path,
            max_bytes=MAX_SOURCE_BYTES - sum(item.size for item in sources.values()),
        )
        sources[result.file_path] = source
    if source.sha256 != digest:
        raise EvidenceUnavailable("source_changed_reindex_required")
    start, end = result.start_line, result.end_line
    lines = source.text.splitlines(keepends=True)
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise EvidenceUnavailable("source_range_invalid_reindex_required")
    current_content = "".join(lines[start - 1 : end])
    if not isinstance(result.content, str) or result.content != current_content:
        raise EvidenceUnavailable("cached_content_mismatch_reindex_required")
    if type(result.score) not in (int, float) or not math.isfinite(result.score):
        raise EvidenceUnavailable("similarity_score_invalid")
    revision = result.indexed_revision
    if revision is not None and (
        not isinstance(revision, str)
        or len(revision) not in (40, 64)
        or any(char not in "0123456789abcdef" for char in revision)
    ):
        raise EvidenceUnavailable("indexed_revision_invalid")
    return {
        "file_path": source.relative_path,
        "start_line": start,
        "end_line": end,
        "content": current_content,
        "score": result.score,
        "source_sha256": source.sha256,
        "repository_id": workspace.binding.repository_id,
        "indexed_revision": revision,
        "current_revision": workspace.revision,
        "freshness": "current_file_verified",
        "retrieval_reason": "semantic_similarity",
    }


def _current_report(workspace: WorkspaceSnapshot, results: Any, top_k: int) -> ToolResult:
    if not isinstance(results, list):
        raise EvidenceUnavailable("invalid_store_response")
    items: list[dict[str, object]] = []
    diagnostics: list[str] = []
    sources: dict[str, SourceSnapshot] = {}
    for result in results[:top_k]:
        try:
            items.append(_qualify_candidate(workspace, result, sources))
        except (EvidenceUnavailable, OSError) as exc:
            diagnostics.append(
                str(exc) if isinstance(exc, EvidenceUnavailable) else "source_unavailable"
            )
    if len(results) > top_k:
        diagnostics.append("store_result_limit_exceeded")
    report: dict[str, Any] = {
        "kind": "rag_current_evidence",
        "version": EVIDENCE_VERSION,
        "repository_id": workspace.binding.repository_id,
        "current_revision": workspace.revision,
        "items": items,
        "diagnostics": diagnostics,
        "coverage": {
            "candidates_returned": len(results),
            "candidates_examined": min(len(results), top_k),
        },
        "limits": {
            "top_k": top_k,
            "source_bytes": MAX_SOURCE_BYTES,
            "source_recheck_bytes": MAX_SOURCE_BYTES,
            "file_bytes": MAX_FILE_BYTES,
            "output_bytes": MAX_OUTPUT_BYTES,
        },
        "limitations": [
            "Similarity ranking covers indexed candidates, not all current repository files.",
            "Current-file verification is an observation, not an atomic filesystem snapshot or task verification.",
            "New or changed files may need explicit reindexing; no matches do not prove absence.",
        ],
    }
    while True:
        report["complete"] = not diagnostics
        content = json.dumps(report, ensure_ascii=False, allow_nan=False)
        if len(content.encode("utf-8")) <= MAX_OUTPUT_BYTES:
            break
        if not items:
            raise EvidenceUnavailable("output_byte_budget_exceeded")
        items.pop()
        if "output_byte_budget_exceeded" not in diagnostics:
            diagnostics.append("output_byte_budget_exceeded")
    # Revalidate after formatting, immediately before publication. No rejected
    # candidate's cached document is ever included in an error response.
    for path in dict.fromkeys(str(item["file_path"]) for item in items):
        sources[path].check(workspace)
    workspace.check()
    return ToolResult(
        content=content,
        success=not diagnostics,
        error="RAG evidence incomplete; inspect diagnostics and reindex where required"
        if diagnostics
        else None,
        structured_content=report,
        structured_content_present=True,
    )
