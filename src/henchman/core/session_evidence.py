"""Session evidence fields are redacted separately from protocol identities."""

from __future__ import annotations

from typing import Any, cast

from henchman.utils.evidence_redaction import PRESERVE_IDENTITY, EvidenceRedactor
from henchman.utils.tool_results import TOOL_RESULT_SCHEMA

_TOOL_CALL = {
    "id": PRESERVE_IDENTITY, "name": PRESERVE_IDENTITY, "type": PRESERVE_IDENTITY,
    "arguments": None,
    "function": {"name": PRESERVE_IDENTITY, "arguments": None},
}
_MESSAGE = {
    "role": PRESERVE_IDENTITY, "tool_call_id": PRESERVE_IDENTITY,
    "agent_id": PRESERVE_IDENTITY, "agent_role": PRESERVE_IDENTITY,
    "content": None, "reasoning_content": None, "reasoning_details": None,
    "tool_calls": [_TOOL_CALL],
    "tool_result": TOOL_RESULT_SCHEMA,
}
_SUMMARY = {
    "turn_number": PRESERVE_IDENTITY, "kind": PRESERVE_IDENTITY,
    "timestamp": PRESERVE_IDENTITY, "source_turns": PRESERVE_IDENTITY,
    "tool_count": PRESERVE_IDENTITY, "summary_text": None, "files_modified": None,
    "retained_messages": [_MESSAGE],
}
_MEMORY = {
    "id": PRESERVE_IDENTITY, "kind": None, "source": None,
    "created_at": PRESERVE_IDENTITY, "message_index": PRESERVE_IDENTITY, "content": None,
}
_PROVENANCE = {
    "version": PRESERVE_IDENTITY, "captured_at": PRESERVE_IDENTITY,
    "digest": PRESERVE_IDENTITY,
    "sources": [{
        "path": None, "scope": None, "kind": PRESERVE_IDENTITY,
        "order": PRESERVE_IDENTITY, "chars": PRESERVE_IDENTITY,
        "original_chars": PRESERVE_IDENTITY, "truncated": PRESERVE_IDENTITY,
        "sha256": PRESERVE_IDENTITY,
    }],
}
_METADATA = {
    "session_memories": [_MEMORY], "memory_extraction_opt_out": PRESERVE_IDENTITY,
    "goal": {"id": PRESERVE_IDENTITY, "status": PRESERVE_IDENTITY,
             "objective": None, "completion_summary": None},
    "instruction_sources": _PROVENANCE, "instruction_sources_history": [_PROVENANCE],
    "imported_at": PRESERVE_IDENTITY, "original_id": PRESERVE_IDENTITY,
    "merged_from": PRESERVE_IDENTITY, "merge_strategy": PRESERVE_IDENTITY,
    "merge_timestamp": PRESERVE_IDENTITY,
}
_SESSION = {
    "id": PRESERVE_IDENTITY, "project_hash": PRESERVE_IDENTITY,
    "started": PRESERVE_IDENTITY, "last_updated": PRESERVE_IDENTITY,
    "parent_id": PRESERVE_IDENTITY, "branch_point": PRESERVE_IDENTITY,
    "template_id": PRESERVE_IDENTITY, "active_agents": PRESERVE_IDENTITY,
    "plan_mode": PRESERVE_IDENTITY, "plan_mode_origin": PRESERVE_IDENTITY,
    "_storage": {"version": PRESERVE_IDENTITY, "sha256": PRESERVE_IDENTITY},
    "accounting": {"store_id": PRESERVE_IDENTITY, "active_run_id": PRESERVE_IDENTITY,
                   "run_ids": PRESERVE_IDENTITY, "active_owner_key": PRESERVE_IDENTITY},
    "operations": {"persistence": PRESERVE_IDENTITY, "observed_ids": PRESERVE_IDENTITY,
                   "reference": {"store_id": PRESERVE_IDENTITY, "project_hash": PRESERVE_IDENTITY,
                                 "session_id": PRESERVE_IDENTITY, "version": PRESERVE_IDENTITY},
                   "conversations": [{"id": PRESERVE_IDENTITY, "messages": [_MESSAGE]}],
                   "bindings": [{"operation_id": PRESERVE_IDENTITY, "assistant_index": PRESERVE_IDENTITY, "conversation_id": PRESERVE_IDENTITY,
                                 "context": dict.fromkeys(("project_hash", "session_id", "run_id", "turn_id", "agent_id", "tool_call_id"), PRESERVE_IDENTITY)}]},
    "tag": None, "messages": [_MESSAGE], "turn_summaries": [_SUMMARY],
    "delegation_log": None, "template_parameters": None, "export_metadata": _METADATA,
}
_TEMPLATE = {
    "id": PRESERVE_IDENTITY, "created_at": PRESERVE_IDENTITY,
    "name": None, "description": None, "parameters": None, "session_data": _SESSION,
}


def redact_session_payload(data: dict[str, Any], redactor: EvidenceRedactor) -> dict[str, Any]:
    """Keep IDs, timestamps, roles and correlation fields usable after redaction."""
    return cast(dict[str, Any], redactor.redact(data, schema=_SESSION))


def redact_template_payload(data: dict[str, Any], redactor: EvidenceRedactor) -> dict[str, Any]:
    """Apply the session policy inside a template's structural envelope."""
    return cast(dict[str, Any], redactor.redact(data, schema=_TEMPLATE))
