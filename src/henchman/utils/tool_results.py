"""Detached typed tool evidence and explicit portable text projections."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

from henchman.utils.evidence_redaction import PRESERVE_IDENTITY

if TYPE_CHECKING:
    from henchman.tools.base import ToolResult

_BLOCK = {
    "type": PRESERVE_IDENTITY,
    "text": None,
    "data": None,
    "mimeType": None,
    "name": None,
    "title": None,
    "description": None,
    "uri": None,
    "size": None,
    "annotations": None,
    "_meta": None,
    "resource": {"uri": None, "mimeType": None, "text": None, "blob": None, "_meta": None},
}
TOOL_RESULT_SCHEMA = {
    "success": PRESERVE_IDENTITY,
    "error": None,
    "content_blocks": [_BLOCK],
    "structured_content_present": PRESERVE_IDENTITY,
    "structured_content": None,
    "metadata": None,
    "projection_truncated": PRESERVE_IDENTITY,
    "payload_sha256": PRESERVE_IDENTITY,
    "original_structured_content_present": PRESERVE_IDENTITY,
}


def _validate_payload(payload: dict[str, Any]) -> None:
    # Local import avoids a provider -> tools package initialization cycle.
    from henchman.tools.contracts import SchemaContract, SchemaContractError

    SchemaContract(True).validate(payload)
    if payload.get("projection_truncated") is True:
        if (
            type(payload.get("success")) is not bool
            or type(payload.get("original_structured_content_present")) is not bool
            or not isinstance(payload.get("payload_sha256"), str)
            or re.fullmatch(r"[a-f0-9]{64}", payload["payload_sha256"]) is None
            or set(payload)
            != {
                "success",
                "projection_truncated",
                "payload_sha256",
                "original_structured_content_present",
            }
        ):
            raise SchemaContractError("typed_result_truncation")
        return
    if (
        type(payload.get("success")) is not bool
        or type(payload.get("structured_content_present")) is not bool
    ):
        raise SchemaContractError("typed_result_shape")
    if set(payload) - {
        "success",
        "error",
        "content_blocks",
        "structured_content_present",
        "structured_content",
        "metadata",
    }:
        raise SchemaContractError("typed_result_shape")
    if payload["structured_content_present"] != ("structured_content" in payload):
        raise SchemaContractError("typed_result_presence")
    if not isinstance(payload.get("content_blocks"), list) or any(
        not isinstance(block, dict)
        or block.get("type") not in ("text", "image", "audio", "resource", "resource_link")
        for block in payload["content_blocks"]
    ):
        raise SchemaContractError("typed_result_content_blocks")
    if payload.get("error") is not None and not isinstance(payload["error"], str):
        raise SchemaContractError("typed_result_error")
    if payload.get("metadata") is not None and not isinstance(payload["metadata"], dict):
        raise SchemaContractError("typed_result_metadata")


def copy_tool_result_payload(payload: object) -> dict[str, Any] | None:
    """Validate protocol identities before exposing a detached evidence copy."""
    from henchman.tools.contracts import SchemaContractError

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise SchemaContractError("typed_result_shape")
    _validate_payload(payload)
    return copy.deepcopy(payload)


def tool_result_payload(result: ToolResult) -> dict[str, Any] | None:
    """Copy typed evidence without changing legacy successful text-only results."""
    if not (
        result.content_blocks
        or result.structured_content_present
        or result.metadata is not None
        or not result.success
        or result.error is not None
    ):
        return None
    payload: dict[str, Any] = {
        "success": result.success,
        "error": result.error,
        "content_blocks": list(result.content_blocks),
        "structured_content_present": result.structured_content_present,
        "metadata": result.metadata,
    }
    if result.structured_content_present:
        payload["structured_content"] = result.structured_content
    return copy_tool_result_payload(payload)


def tool_result_from_payload(content: str, payload: dict[str, Any] | None) -> ToolResult:
    """Restore typed event/session evidence with exact missing/null semantics."""
    from henchman.tools.base import ToolResult

    if payload is None:
        return ToolResult(content)
    value = copy_tool_result_payload(payload)
    assert value is not None
    if value.get("projection_truncated"):
        return ToolResult(content=content, success=value["success"], metadata=value)
    return ToolResult(
        content=content,
        success=value.get("success", True),
        error=value.get("error"),
        content_blocks=tuple(value.get("content_blocks", [])),
        structured_content=value.get("structured_content"),
        structured_content_present=value.get("structured_content_present", False),
        metadata=value.get("metadata"),
    )


def tool_result_event_data(tool_call_id: str, tool_name: str, result: ToolResult) -> dict[str, Any]:
    """Retain the existing event envelope and add typed evidence when available."""
    data: dict[str, Any] = {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "result": result.content,
        "success": result.success,
    }
    payload = tool_result_payload(result)
    if payload is not None:
        data["tool_result"] = payload
    return data


def _visible_block(block: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(block)
    kind = result.get("type")
    if kind in ("image", "audio") and "data" in result:
        data = result.pop("data")
        result["projection"] = {
            "representation": "typed text summary",
            "reason": "Binary media transport is unsupported by this tool-result adapter; data is not sent as binary.",
            "provided_data_characters": len(data) if isinstance(data, str) else None,
        }
    if (
        kind == "resource"
        and isinstance(result.get("resource"), dict)
        and "blob" in result["resource"]
    ):
        blob = result["resource"].pop("blob")
        result["resource"]["projection"] = {
            "reason": "Binary resource transport is unsupported; resource data is not sent as binary.",
            "provided_blob_characters": len(blob) if isinstance(blob, str) else None,
        }
    return result


def tool_message_content(content: str | None, payload: dict[str, Any] | None) -> str:
    """Project portable text explicitly without mutating the typed input."""
    if payload is None:
        return content or ""
    _validate_payload(payload)
    projected = copy.deepcopy(payload)
    if payload.get("projection_truncated"):
        projected["projection_note"] = "Typed result payload omitted from this active message."
    else:
        projected["content_blocks"] = [
            _visible_block(block) for block in projected["content_blocks"]
        ]
    projected["content"] = content or ""
    return json.dumps(
        {"tool_result": projected}, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    )


def compact_tool_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Name omitted active-context evidence without altering retained originals."""
    if payload is None:
        return None
    _validate_payload(payload)
    if payload.get("projection_truncated"):
        return copy.deepcopy(payload)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()
    ).hexdigest()
    return {
        "success": payload["success"],
        "projection_truncated": True,
        "payload_sha256": digest,
        "original_structured_content_present": payload.get("structured_content_present", False),
    }
