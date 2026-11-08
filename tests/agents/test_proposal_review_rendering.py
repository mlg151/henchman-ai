"""Parent review must contain every proposed byte or fail without a preview."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from henchman.advanced.checkpoint_models import FileState, ReviewFile
from henchman.advanced.child_proposals import ChildProposalReview
from henchman.agents.proposal_review import ParentProposalReview, render_parent_review
from henchman.agents.proposal_runtime import ProposalCoordinator
from henchman.agents.workspace_ownership import WorkspaceBinding, WorkspaceOwnershipError
from henchman.providers.base import Message
from henchman.utils.compaction import _truncate_tool_message_content


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


async def test_parent_must_request_complete_preview_and_acknowledge_it(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    session, actor, child = object(), object(), object()
    runtime = ProposalCoordinator(tmp_path, session=session, generation=0, parent=actor, paths=["file"],
                                  current_binding=lambda: WorkspaceBinding(tmp_path, session, 0))
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)

    content = "after" + ("x" * 1000) + "END_OF_REVIEW_CONTENT"

    async def run() -> None:
        runtime.workspace(handle, child).stage("file", content)

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    parent = ParentProposalReview(runtime, handle)
    with pytest.raises(ValueError, match="review"):
        parent.publish("not-reviewed")
    preview_text = parent.preview()
    preview = json.loads(preview_text)
    assert preview["review"]["files"][0]["after"]["content"] == content
    assert json.loads(parent.preview()) == preview
    tail = preview_text.index("END_OF_REVIEW_CONTENT")
    tokens_to_trim = (len(preview_text) - tail + 3) // 4
    compacted = _truncate_tool_message_content(Message("tool", preview_text), tokens_to_trim)
    assert "END_OF_REVIEW_CONTENT" not in (compacted.content or "")
    assert preview["review_token"] not in (compacted.content or "")
    with pytest.raises(ValueError, match="review"):
        parent.publish("wrong-token")
    with pytest.raises(ValueError, match="review"):
        parent.publish("\N{SNOWMAN}")

    async def wrong_worker() -> None:
        with pytest.raises(WorkspaceOwnershipError, match="wrong_worker"):
            parent.publish(preview["review_token"])

    await asyncio.create_task(wrong_worker())
    assert path.read_text() == "before"
    assert parent.publish(preview["review_token"]).changed_paths == ("file",)
    assert path.read_text() == content
    with pytest.raises(ValueError, match="review"):
        parent.publish(preview["review_token"])
    await runtime.close()


async def test_oversized_preview_cannot_issue_publication_acknowledgement(tmp_path: Path) -> None:
    path = tmp_path / "file"
    path.write_text("before")
    session, actor, child = object(), object(), object()
    runtime = ProposalCoordinator(tmp_path, session=session, generation=0, parent=actor, paths=["file"],
                                  current_binding=lambda: WorkspaceBinding(tmp_path, session, 0))
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)

    async def run() -> None:
        runtime.workspace(handle, child).stage("file", "after" * 7000)

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    parent = ParentProposalReview(runtime, handle)
    with pytest.raises(ValueError, match="too large"):
        parent.preview()
    with pytest.raises(ValueError, match="review"):
        parent.publish("unissued")
    runtime.discard(handle)
    assert path.read_text() == "before"
    await runtime.close()
