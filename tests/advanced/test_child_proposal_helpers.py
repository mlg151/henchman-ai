"""Private child proposals never mutate or approve the working tree."""

from __future__ import annotations

import asyncio

import pytest

from henchman.advanced.checkpoint_store import CheckpointStore


@pytest.mark.parametrize("namespace", ["", "../outside", "other", None, True])
def test_unknown_storage_namespace_refuses_before_creating_directories(tmp_path, namespace):
    with pytest.raises(ValueError, match="namespace"):
        CheckpointStore(tmp_path, 1024, namespace=namespace)
    assert list(tmp_path.iterdir()) == []


def test_proposal_storage_namespace_preserves_checkpoint_default(tmp_path):
    default = CheckpointStore(tmp_path, 1024 * 1024)
    proposals = CheckpointStore(tmp_path, 1024 * 1024, namespace="proposals")
    assert default.path == tmp_path / ".henchman/tungsten/checkpoints"
    assert proposals.path == tmp_path / ".henchman/tungsten/proposals"
    with proposals.lock:
        proposals.write(proposals.path / "proposal.json", {"version": 1, "kind": "child-proposal"})
    from henchman.advanced.checkpoints import CheckpointService
    assert CheckpointService(tmp_path).list_checkpoints() == ()


async def test_formatter_rechecks_admission_after_expansion_before_spawn(tmp_path, monkeypatch):
    from henchman.tools import formatting
    path = tmp_path / "a.py"
    path.write_text("value=1\n")
    entered, release = asyncio.Event(), asyncio.Event()
    original = formatting.asyncio.to_thread
    revoked = False
    calls = []

    async def paused(function, *args, **kwargs):
        result = await original(function, *args, **kwargs)
        entered.set()
        await release.wait()
        return result

    def guard(paths):
        assert paths == (path,)
        if revoked:
            raise PermissionError("authority retired")

    async def forbidden(*args, **_kwargs):
        calls.append(args)
        raise AssertionError("formatter process must not start")

    monkeypatch.setattr(formatting.asyncio, "to_thread", paused)
    monkeypatch.setattr(formatting, "run_bounded_subprocess", forbidden)
    worker = asyncio.create_task(formatting.format_python_files([path], cwd=tmp_path, authorize=guard))
    await entered.wait()
    revoked = True
    release.set()
    with pytest.raises(PermissionError, match="authority retired"):
        await worker
    assert calls == []


async def test_formatter_rechecks_actual_expanded_targets_and_after_settlement(tmp_path, monkeypatch):
    from henchman.tools import formatting
    from henchman.tools.subprocess_utils import BoundedProcessResult
    path = tmp_path / "a.py"
    path.write_text("value=1\n")
    phases = []
    settled = False

    def guard(paths):
        assert paths == (path,)
        phases.append(settled)
        if settled:
            raise PermissionError("revoked during formatting")

    async def complete(*_args, **_kwargs):
        nonlocal settled
        settled = True
        return BoundedProcessResult(b"", b"", 0, False, False)

    monkeypatch.setattr(formatting, "run_bounded_subprocess", complete)
    with pytest.raises(PermissionError, match="revoked during formatting"):
        await formatting.format_python_files([path], cwd=tmp_path, authorize=guard)
    assert phases[-1] is True
    assert phases.count(False) >= 2


async def test_formatter_refuses_a_target_discovered_inside_a_directory(tmp_path, monkeypatch):
    from henchman.tools import formatting

    source = tmp_path / "a.py"
    source.write_text("value=1\n")
    calls = []

    def guard(paths):
        if paths != (tmp_path,):
            raise PermissionError("expanded target is outside the held scope")

    async def forbidden(*args, **_kwargs):
        calls.append(args)
        raise AssertionError("formatter must not start")

    monkeypatch.setattr(formatting, "run_bounded_subprocess", forbidden)
    with pytest.raises(PermissionError, match="expanded target"):
        await formatting.format_python_files([tmp_path], cwd=tmp_path, authorize=guard)
    assert calls == []


async def test_formatter_failure_remains_primary_when_admission_changes(tmp_path, monkeypatch):
    from henchman.tools import formatting
    from henchman.tools.subprocess_utils import BoundedProcessResult

    source = tmp_path / "a.py"
    source.write_text("value=1\n")
    settled = False

    def guard(_paths):
        if settled:
            raise PermissionError("revoked")

    async def fail(*_args, **_kwargs):
        nonlocal settled
        settled = True
        return BoundedProcessResult(b"", b"formatter error", 1, False, False)

    monkeypatch.setattr(formatting, "run_bounded_subprocess", fail)
    with pytest.raises(formatting.FormattingError, match="formatter error"):
        await formatting.format_python_files([source], cwd=tmp_path, authorize=guard)
