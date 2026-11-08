"""Render a complete bounded proposal for a parent to inspect before approval."""

from __future__ import annotations

import json

from henchman.advanced.checkpoint_models import FileState
from henchman.advanced.child_proposals import ChildProposalReview

# Leave room below the registry's 50,000-character output limit for a caller's
# attribution and review instructions; an abbreviated preview must not approve.
_MAX_REVIEW_BYTES = 32_768


def _state(state: FileState) -> dict[str, object]:
    if state.status == "missing" and state.content is None and state.mode is None:
        return {"status": "missing", "mode": None, "content": None}
    if state.status != "text" or state.content is None or type(state.mode) is not int:
        raise ValueError("Proposal contains unsupported review content")
    try:
        content = state.content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Proposal contains unsupported review content") from error
    return {"status": "text", "mode": state.mode, "content": content}


def render_parent_review(review: ChildProposalReview) -> str:
    """Return every before/after value, or refuse rather than truncate the review.

    This representation is evidence, not an approval token. The coordinator
    retains the exact review object and must separately authorize publication.
    """
    files: list[dict[str, object]] = []
    raw_size = 0
    for item in review.files:
        raw_size += len(item.path.encode("utf-8"))
        raw_size += sum(len(state.content) for state in (item.before, item.after) if state.content is not None)
        if raw_size > _MAX_REVIEW_BYTES:
            raise ValueError("Proposal is too large for a complete parent review")
        files.append({"path": item.path, "before": _state(item.before), "after": _state(item.after)})
    record = {"proposal_id": review.proposal_id, "revision": review.revision, "files": files}
    chunks: list[str] = []
    size = 0
    for chunk in json.JSONEncoder(ensure_ascii=True, separators=(",", ":")).iterencode(record):
        size += len(chunk)  # ASCII output: characters and encoded bytes are identical.
        if size > _MAX_REVIEW_BYTES:
            raise ValueError("Proposal is too large for a complete parent review")
        chunks.append(chunk)
    return "".join(chunks)
