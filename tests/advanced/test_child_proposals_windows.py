"""Native NTFS proposal publication and interrupted recovery."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from henchman.advanced.checkpoint_models import CheckpointConflict
from henchman.advanced.child_proposals import ChildProposalService

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="native Windows publication backend")


def test_windows_proposal_publishes_after_review_and_preserves_other_files(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("before", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("user", encoding="utf-8")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file.txt", "new.txt"])
    service.stage(proposal, "file.txt", "after")
    service.stage(proposal, "new.txt", "new")
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == "before"
    assert not (tmp_path / "new.txt").exists()
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    assert service.apply(plan).changed_paths == ("file.txt", "new.txt")
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == "after"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "new"
    assert (tmp_path / "unrelated.txt").read_text(encoding="utf-8") == "user"
    assert (tmp_path / service.retained_originals(plan)[0]).read_text(encoding="utf-8") == "before"


def test_windows_proposal_refuses_an_intervening_user_edit(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("before", encoding="utf-8")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file.txt"])
    service.stage(proposal, "file.txt", "agent")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    path.write_text("user", encoding="utf-8")
    with pytest.raises(CheckpointConflict):
        service.apply(plan)
    assert path.read_text(encoding="utf-8") == "user"


@pytest.mark.parametrize("stage", ["prepared", "private_source", "displaced", "staged", "linked", "published", "recorded"])
def test_windows_proposal_recovers_after_process_exit(tmp_path: Path, stage: str) -> None:
    path = tmp_path / "file.txt"
    path.write_text("before", encoding="utf-8")
    service = ChildProposalService(tmp_path)
    proposal = service.begin(["file.txt"])
    service.stage(proposal, "file.txt", "after")
    service.seal(proposal)
    plan = service.prepare(proposal, revision=service.review(proposal).revision)
    code = """import os, sys
from pathlib import Path
from henchman.advanced.child_proposals import ChildProposalService
def fault(stage):
    if stage == sys.argv[3]:
        os._exit(73)
ChildProposalService(Path(sys.argv[1]), fault=fault).apply(sys.argv[2])
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), plan, stage], check=False, timeout=30)
    assert result.returncode == 73
    resumed = ChildProposalService(tmp_path)
    assert resumed.pending() == (plan,)
    assert resumed.recover(plan).changed_paths == ("file.txt",)
    assert path.read_text(encoding="utf-8") == "after"
