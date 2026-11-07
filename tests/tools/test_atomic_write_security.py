"""Exclusive temporary files preserve unrelated paths and complete-write visibility."""

import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from henchman.tools.security import atomic_write


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"Symlink creation unavailable: {exc}")


def test_planted_predictable_temp_symlink_never_changes_outside_file(tmp_path: Path) -> None:
    target = tmp_path / "result.txt"
    outside = tmp_path / "outside"
    outside.write_text("outside canary")
    planted = tmp_path / "result.txt.tmp"
    _symlink(planted, outside)

    atomic_write(target, "new result")

    assert outside.read_text() == "outside canary"
    assert target.read_text() == "new result"
    assert not target.is_symlink()
    assert planted.is_symlink()


def test_unrelated_predictable_temp_file_is_not_consumed_or_deleted(tmp_path: Path) -> None:
    target = tmp_path / "result.txt"
    planted = tmp_path / "result.txt.tmp"
    planted.write_text("unrelated work")
    atomic_write(target, "new result")
    assert planted.read_text() == "unrelated work"
    assert target.read_text() == "new result"


def test_destination_symlink_is_replaced_without_writing_its_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.write_text("outside canary")
    target = tmp_path / "result.txt"
    _symlink(target, outside)
    atomic_write(target, "new result")
    assert outside.read_text() == "outside canary"
    assert target.read_text() == "new result"
    assert not target.is_symlink()


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable modes")
def test_replacing_regular_file_preserves_ordinary_permission_bits(tmp_path: Path) -> None:
    target = tmp_path / "script.py"
    target.write_text("old")
    target.chmod(0o750)
    atomic_write(target, "new")
    assert stat.S_IMODE(target.stat().st_mode) == 0o750


@pytest.mark.skipif(os.name == "nt", reason="POSIX temporary-file permissions")
def test_new_atomic_file_is_private(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    atomic_write(target, "private content")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.parametrize("failure", ["replace", "fsync", "encoding", "unknown_encoding"])
def test_failed_write_preserves_destination_and_cleans_only_owned_temp(tmp_path: Path, monkeypatch, failure: str) -> None:
    target = tmp_path / "result.txt"
    target.write_text("original content")
    unrelated = tmp_path / "result.txt.tmp"
    unrelated.write_text("unrelated")

    def fail(*_args, **_kwargs):
        raise OSError("injected operation failure")

    if failure in {"replace", "fsync"}:
        monkeypatch.setattr(os, failure, fail)
    encoding = {"encoding": "ascii", "unknown_encoding": "not-an-encoding"}.get(failure, "utf-8")
    with pytest.raises((OSError, UnicodeEncodeError, LookupError)):
        atomic_write(target, "café", encoding=encoding)
    assert target.read_text() == "original content"
    assert unrelated.read_text() == "unrelated"
    assert set(tmp_path.iterdir()) == {target, unrelated}


def test_concurrent_atomic_writers_use_distinct_temps_and_complete_payloads(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "result.txt"
    target.write_text("original")
    barrier = Barrier(4)
    original_replace = os.replace
    observed: list[Path] = []

    def replace(source, destination, *args, **kwargs):
        observed.append(Path(source))
        barrier.wait(timeout=5)
        return original_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    payloads = [f"writer-{index}:" + str(index) * 100_000 for index in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda content: atomic_write(target, content), payloads))
    assert len(set(observed)) == 4
    assert all(path.parent == tmp_path for path in observed)
    assert target.read_text() in payloads
    assert list(tmp_path.iterdir()) == [target]
