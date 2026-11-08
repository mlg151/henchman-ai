"""Parent review must contain every proposed byte or fail without a preview."""

from __future__ import annotations

import json

import pytest

from henchman.advanced.checkpoint_models import FileState, ReviewFile
from henchman.advanced.child_proposals import ChildProposalReview
from henchman.agents.proposal_review import render_parent_review


def _review(before: FileState, after: FileState) -> ChildProposalReview:
    return ChildProposalReview("proposal", 4, (ReviewFile("src/test.py", before, after, (), "pending"),))


def test_review_renders_full_exact_contents_and_file_absence() -> None:
    before = FileState("text", "π\r\n".encode(), 0o640)
    after = FileState("missing")
    rendered = json.loads(render_parent_review(_review(before, after)))
    assert rendered == {
        "proposal_id": "proposal", "revision": 4,
        "files": [{"path": "src/test.py", "before": {"status": "text", "mode": 0o640, "content": "π\r\n"},
                   "after": {"status": "missing", "mode": None, "content": None}}],
    }


def test_review_refuses_an_incomplete_preview() -> None:
    before = FileState("text", b"old", 0o600)
    after = FileState("text", b"new " * 13_000, 0o600)
    with pytest.raises(ValueError, match="too large"):
        render_parent_review(_review(before, after))


def test_review_counts_escaped_output_not_only_input_bytes() -> None:
    content = ("\N{SNOWMAN}" * 3000).encode()
    with pytest.raises(ValueError, match="too large"):
        render_parent_review(_review(FileState("text", content, 0o600), FileState("text", content, 0o600)))


def test_review_refuses_unsupported_file_content() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        render_parent_review(_review(FileState("binary"), FileState("missing")))
