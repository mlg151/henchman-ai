"""Migration compares pathname and descriptor snapshots within their own domains."""

import contextlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from henchman.advanced import task_output
from henchman.utils.evidence_redaction import EvidenceRedactor


def _metadata(info, **overrides):
    values = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
    return SimpleNamespace(**(values | overrides))


def test_migration_accepts_unchanged_file_with_distinct_fstat_ctime(tmp_path, monkeypatch):
    """CPython Windows path ctime is birthtime; fstat ctime can be ChangeTime."""
    path = tmp_path / "evidence.log"
    path.write_bytes(b"known-credential\nkeep\n")
    identity = path.stat()
    native_fstat = os.fstat

    def descriptor_stat(descriptor):
        info = native_fstat(descriptor)
        if os.path.samestat(info, identity):
            return _metadata(info, st_ctime_ns=info.st_ctime_ns + 1_000_000_000)
        return info

    monkeypatch.setattr(os, "fstat", descriptor_stat)
    assert task_output.migrate_evidence(path, EvidenceRedactor(["known-credential"])) is False
    assert path.read_bytes() == b"[REDACTED]\nkeep\n"
    assert not list(tmp_path.glob("*.tmp"))


def test_descriptor_change_is_rejected_even_when_path_times_are_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "evidence.log"
    original = b"known-credential\nkeep\n"
    path.write_bytes(original)
    identity = path.stat()
    native_fstat = os.fstat
    writes = 0
    bounded_write = task_output._bounded_write

    def descriptor_stat(descriptor):
        info = native_fstat(descriptor)
        if os.path.samestat(info, identity):
            return _metadata(info, st_ctime_ns=info.st_ctime_ns + writes + 1_000_000_000)
        return info

    def project_write(*args):
        nonlocal writes
        writes += 1
        return bounded_write(*args)

    monkeypatch.setattr(os, "fstat", descriptor_stat)
    monkeypatch.setattr(task_output, "_bounded_write", project_write)
    with pytest.raises(OSError, match="changed during migration"):
        task_output.migrate_evidence(path, EvidenceRedactor(["known-credential"]))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("change", ["replacement", "modified_time", "hardlink"])
def test_path_change_after_reader_closes_is_rejected(tmp_path, monkeypatch, change):
    path = tmp_path / "evidence.log"
    original = b"known-credential\nkeep\n"
    path.write_bytes(original)
    before = path.stat()
    atomic = task_output.atomic_evidence

    @contextlib.contextmanager
    def competing_write(*args, **kwargs):
        with atomic(*args, **kwargs) as output:
            yield output
            if change == "replacement":
                replacement = tmp_path / "replacement.log"
                replacement.write_bytes(original)
                os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
                os.replace(replacement, path)
            elif change == "hardlink":
                os.link(path, tmp_path / "alias.log")
            else:
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))

    monkeypatch.setattr(task_output, "atomic_evidence", competing_write)
    with pytest.raises(OSError, match="changed during migration|without links"):
        task_output.migrate_evidence(path, EvidenceRedactor(["known-credential"]))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_migration_rejects_path_replacement_before_baseline_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "evidence.log"
    path.write_bytes(b"known-credential\n")
    native_stat = task_output._stat_entry
    calls = 0
    other = tmp_path / "other.log"
    other.write_bytes(b"user evidence")

    def replaced_snapshot(target: Path, directory_fd):
        nonlocal calls
        info = native_stat(target, directory_fd)
        if target == path:
            calls += 1
            if calls > 1:
                return other.stat()
        return info

    monkeypatch.setattr(task_output, "_stat_entry", replaced_snapshot)
    with pytest.raises(OSError, match="changed"):
        task_output.migrate_evidence(path, EvidenceRedactor(["known-credential"]))
    assert path.read_bytes() == b"known-credential\n"
    assert other.read_bytes() == b"user evidence"


def test_disappearance_after_open_remains_a_migration_failure(tmp_path, monkeypatch):
    path = tmp_path / "evidence.log"
    path.write_bytes(b"retained evidence")
    native_stat = task_output._stat_entry
    calls = 0

    def disappeared_snapshot(target, directory_fd):
        nonlocal calls
        if target == path:
            calls += 1
            if calls > 1:
                raise FileNotFoundError("disappeared after open")
        return native_stat(target, directory_fd)

    monkeypatch.setattr(task_output, "_stat_entry", disappeared_snapshot)
    with pytest.raises(OSError, match="disappeared") as caught:
        task_output.migrate_evidence(path, EvidenceRedactor())
    # TaskService treats an initially absent optional log differently from an
    # opened input disappearing mid-migration; preserve that distinction.
    assert not isinstance(caught.value, FileNotFoundError)
    assert path.read_bytes() == b"retained evidence"
