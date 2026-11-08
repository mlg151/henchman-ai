"""Small typed repository evidence records and whole-item output bounds."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from henchman.rag.evidence import SourceSnapshot
from henchman.tools.base import ToolResult

MAX_OUTPUT_BYTES = 48 * 1024
MAX_EXCERPT_CHARS = 4096


def source_record(source: SourceSnapshot, *, start: int, end: int,
                  revision: str | None, tracked: bool) -> dict[str, Any]:
    """Retain the full-byte digest and disclose any excerpt omission separately."""
    lines = source.text.splitlines(keepends=True)
    excerpt = "".join(lines[start - 1:min(end, start + 39)])
    return {
        "path": source.relative_path, "start_line": start, "end_line": end,
        "content": excerpt[:MAX_EXCERPT_CHARS], "source_sha256": source.sha256,
        "excerpt_truncated": end >= start + 40 or len(excerpt) > MAX_EXCERPT_CHARS,
        "tracked": tracked, "current_revision": revision,
    }


def evidence_id(path: str, symbol: str, line: int) -> str:
    """An evidence-link identity, never execution or instruction authority."""
    return hashlib.sha256(f"{path}\0{symbol}\0{line}".encode()).hexdigest()[:24]


def encode_pack(pack: dict[str, Any]) -> str:
    return json.dumps(pack, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def bounded_result(pack: dict[str, Any]) -> ToolResult:
    """Omit whole records, never emit truncated JSON or fabricate task verification."""
    omitted = 0
    while len(encode_pack(pack).encode()) > MAX_OUTPUT_BYTES:
        for field in ("references", "tests", "instructions", "implementations", "diagnostics"):
            if pack[field]:
                pack[field].pop()
                omitted += 1
                break
        else:
            return unavailable("repository_output_budget_exceeded")
        pack["complete"] = False
        pack["output_omitted_items"] = omitted
    pack["status"] = "complete" if pack["complete"] else "partial"
    # Reserve the status/omission marker in the same bound.
    if len(encode_pack(pack).encode()) > MAX_OUTPUT_BYTES:
        return unavailable("repository_output_budget_exceeded")
    content = encode_pack(pack)
    return ToolResult(content=content, success=pack["complete"],
                      error=None if pack["complete"] else "Repository evidence is partial",
                      structured_content=pack, structured_content_present=True)


def unavailable(code: str) -> ToolResult:
    """A value-free failure carries no stale or newly forbidden evidence."""
    pack: dict[str, Any] = {"version": 1, "kind": "repository_evidence",
                           "status": "unavailable", "complete": False, "task_verified": False,
                           "implementations": [], "tests": [], "references": [],
                           "instructions": [], "diagnostics": [{"code": code}]}
    return ToolResult(content=encode_pack(pack), success=False, error=code,
                      structured_content=pack, structured_content_present=True)
