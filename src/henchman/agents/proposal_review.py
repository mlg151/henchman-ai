"""Render a complete bounded proposal for a parent to inspect before approval."""

from __future__ import annotations

import json
import secrets

from henchman.advanced.checkpoint_models import FileState, ReviewResult
from henchman.advanced.child_proposals import ChildProposalReview
from henchman.agents.proposal_runtime import ProposalCoordinator, ProposalHandle

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


class ParentProposalReview:
    """Hold a complete preview and one explicit acknowledgement for its parent."""

    def __init__(self, runtime: ProposalCoordinator, handle: ProposalHandle) -> None:
        self._runtime = runtime
        self._handle = handle
        self._review: ChildProposalReview | None = None
        self._token: str | None = None
        self._preview: str | None = None
        self._closed = False

    def preview(self) -> str:
        """Return the full review and acknowledgement token to the live parent."""
        if self._closed:
            raise ValueError("Parent review is already resolved")
        review = self._runtime.review(self._handle)
        if self._review is not None:
            if review is not self._review or self._preview is None:
                raise ValueError("Parent review changed")
            return self._preview
        record = json.loads(render_parent_review(review))
        token = secrets.token_hex(16)
        preview = json.dumps({"review": record, "review_token": token}, ensure_ascii=True, separators=(",", ":"))
        self._review, self._token, self._preview = review, token, preview
        return preview

    def publish(self, token: str) -> ReviewResult:
        """Publish only after the parent acknowledges the complete held preview."""
        if (self._closed or self._review is None or self._token is None or not isinstance(token, str)
                or not token.isascii() or not secrets.compare_digest(token, self._token)):
            raise ValueError("A current parent review acknowledgement is required")
        result = self._runtime.publish(self._handle, self._review)
        self._closed = True
        self._token = None
        return result
