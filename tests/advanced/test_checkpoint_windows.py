"""Windows checkpoint boundary tests; native cases require actual Win32/NTFS."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from henchman.advanced.checkpoints import CheckpointConflict, CheckpointService

native = pytest.mark.skipif(sys.platform != "win32", reason="Requires native Windows handles and NTFS")


@pytest.mark.parametrize("value", ["file:stream", "NUL", "aux.txt", "folder/COM1.txt", "file.", "file ", "bad?name", "LPT²", "CONOUT$", "a\x01b", "NUL .txt", "COM0", "bad\ud800"])
def test_windows_names_cannot_alias_streams_devices_or_trimmed_paths(value):
    from henchman.advanced.checkpoint_windows import validate_path

    with pytest.raises(ValueError, match="Windows"):
        validate_path(value)


def test_windows_names_keep_ordinary_unicode_and_spaces():
    from henchman.advanced.checkpoint_windows import validate_path

    validate_path("src/ordinary file-λ.py")


def _plan(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(b"before\r\n")
    service = CheckpointService(tmp_path)
    record = service.begin(["file.txt"], actor="windows test")
    path.write_bytes(b"after\n")
    service.complete(record.checkpoint_id)
    return service, service.preview(record.checkpoint_id, decision="reject")


@native
def test_native_round_trip_create_delete_rename_hunk_and_unrelated_dirty(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name in ("edit", "delete", "old", "dirty"):
        (tmp_path / name).write_bytes(b"first\r\nkeep\r\nlast\r\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    index = (tmp_path / ".git/index").read_bytes()
    (tmp_path / "dirty").write_bytes(b"unrelated")
    service = CheckpointService(tmp_path)
    record = service.begin(["edit", "delete", "create", "old", "new"], actor="windows")
    (tmp_path / "edit").write_bytes(b"FIRST\r\nkeep\r\nLAST\r\n")
    (tmp_path / "delete").unlink()
    (tmp_path / "create").write_bytes(b"created")
    (tmp_path / "old").rename(tmp_path / "new")
    service.complete(record.checkpoint_id)
    service.apply(service.preview(record.checkpoint_id, decision="reject", hunks={"edit": [0]}).plan_id)
    assert (tmp_path / "edit").read_bytes() == b"first\r\nkeep\r\nLAST\r\n"
    result = service.apply(service.preview(record.checkpoint_id, decision="reject").plan_id)
    assert result.changed_paths == ("create", "delete", "edit", "new", "old")
    for name in ("edit", "delete", "old"):
        assert (tmp_path / name).read_bytes() == b"first\r\nkeep\r\nlast\r\n"
    assert not (tmp_path / "create").exists() and not (tmp_path / "new").exists()
    assert (tmp_path / "dirty").read_bytes() == b"unrelated"
    assert (tmp_path / ".git/index").read_bytes() == index


@native
@pytest.mark.parametrize("stage", ["prepared", "private_source", "displaced", "staged", "linked", "published", "recorded", "done"])
def test_native_process_death_has_recoverable_journal_and_retained_original(tmp_path, stage):
    _, plan = _plan(tmp_path)
    code = """import os, sys
from pathlib import Path
from henchman.advanced.checkpoints import CheckpointService
CheckpointService(Path(sys.argv[1]), fault=lambda stage: os._exit(73) if stage == sys.argv[3] else None).apply(sys.argv[2])
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), plan.plan_id, stage], env=environment, timeout=20)
    assert result.returncode == 73
    service = CheckpointService(tmp_path)
    recovered = service.recover(plan.plan_id)
    assert recovered.changed_paths == ("file.txt",)
    assert (tmp_path / "file.txt").read_bytes() == b"before\r\n"
    originals = service.retained_originals(plan.plan_id)
    assert len(originals) == 1
    assert (tmp_path / originals[0]).read_bytes() == b"after\n"
    assert service.pending_restores() == ()


@native
@pytest.mark.parametrize("stage", ["before_displace", "before_publish"])
def test_native_boundary_user_write_is_never_replaced(tmp_path, stage):
    _, plan = _plan(tmp_path)
    path = tmp_path / "file.txt"

    def fault(boundary):
        if boundary == stage:
            path.write_bytes(b"user edit")

    with pytest.raises(CheckpointConflict):
        CheckpointService(tmp_path, fault=fault).apply(plan.plan_id)
    assert path.read_bytes() == b"user edit"


@native
def test_native_open_writer_blocks_restore_without_losing_bytes(tmp_path):
    service, plan = _plan(tmp_path)
    with (tmp_path / "file.txt").open("r+b") as writer:
        with pytest.raises(CheckpointConflict):
            service.apply(plan.plan_id)
        writer.seek(0)
        writer.write(b"late writer")
        writer.truncate()
    assert (tmp_path / "file.txt").read_bytes() == b"late writer"


@native
def test_native_replaced_parent_and_hardlink_and_ads_are_unsupported(tmp_path):
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    os.link(outside, tmp_path / "hard")
    (tmp_path / "ads").write_bytes(b"main")
    Path(str(tmp_path / "ads") + ":secret").write_bytes(b"hidden")
    service = CheckpointService(tmp_path)
    record = service.begin(["hard", "ads"], actor="test")
    service.complete(record.checkpoint_id)
    assert {file.before.status for file in service.review(record.checkpoint_id).files} == {"unsupported"}
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir/file").write_bytes(b"before")
    record = service.begin(["dir/file"], actor="test")
    (tmp_path / "dir/file").write_bytes(b"after")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    (tmp_path / "dir").rename(tmp_path / "original-dir")
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir/file").write_bytes(b"after")
    with pytest.raises(CheckpointConflict):
        service.apply(plan.plan_id)
    assert (tmp_path / "dir/file").read_bytes() == b"after"


@native
def test_native_junction_parent_is_rejected_without_reading_external_content(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "file").write_bytes(b"private outside")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(tmp_path / "junction"), str(outside)], check=True, capture_output=True)
    service = CheckpointService(tmp_path)
    record = service.begin(["junction/file"], actor="test")
    service.complete(record.checkpoint_id)
    assert service.review(record.checkpoint_id).files[0].before.status == "unsupported"
    assert b"private outside" not in b"".join(path.read_bytes() for path in service._store.path.glob("*.json"))


@native
def test_native_journal_dacl_is_private_and_public_existing_store_is_denied(tmp_path):
    from henchman.advanced.checkpoint_windows import windows_api

    service, plan = _plan(tmp_path)
    service.apply(plan.plan_id)
    api = windows_api()
    for path in [service._store.path, *service._store.path.rglob("*")]:
        with api.open(path, directory=path.is_dir()) as handle:
            api.check_private(handle)
    public = tmp_path / "public-project"
    (public / ".henchman/tungsten/checkpoints").mkdir(parents=True)
    with pytest.raises(ValueError, match="private"):
        CheckpointService(public)


@native
def test_native_corrupt_staging_denies_recovery_and_case_aliases_denied(tmp_path):
    service, plan = _plan(tmp_path)
    with pytest.raises(ValueError, match="alias"):
        service.begin(["file.txt", "FILE.TXT"], actor="test")

    def fault(stage):
        if stage == "staged":
            raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        CheckpointService(tmp_path, fault=fault).apply(plan.plan_id)
    staged = service._store.path / "plans" / plan.plan_id / "0.new"
    staged.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="corrupt"):
        service.recover(plan.plan_id)
    assert not (tmp_path / "file.txt").exists()
    assert (service._store.path / "plans" / plan.plan_id / "0.old").read_bytes() == b"after\n"


@native
def test_native_private_source_interruption_is_disclosed_and_recoverable(tmp_path):
    from dataclasses import asdict

    from henchman.advanced.checkpoint_windows import windows_api
    from henchman.cli.commands.checkpoint import _review_payload

    service, plan = _plan(tmp_path)
    assert asdict(plan)["metadata_policy"] == "windows-private-acl-content-only"
    review = service.review(plan.checkpoint_id)
    assert _review_payload(review)["metadata_policy"] == "windows-private-acl-content-only"

    def fault(stage):
        if stage == "private_source":
            raise RuntimeError("before displacement")

    with pytest.raises(RuntimeError, match="before displacement"):
        CheckpointService(tmp_path, fault=fault).apply(plan.plan_id)
    assert (tmp_path / "file.txt").read_bytes() == b"after\n"
    api = windows_api()
    with api.open(tmp_path / "file.txt") as handle:
        api.check_private(handle, protected=True)
    assert service.pending_restores() == (plan.plan_id,)
    service.recover(plan.plan_id)
    assert (tmp_path / "file.txt").read_bytes() == b"before\r\n"


@native
def test_native_held_parent_prevents_rename_during_restore(tmp_path):
    directory = tmp_path / "source"
    directory.mkdir()
    path = directory / "file"
    path.write_bytes(b"before")
    service = CheckpointService(tmp_path)
    record = service.begin(["source/file"], actor="test")
    path.write_bytes(b"after")
    service.complete(record.checkpoint_id)
    plan = service.preview(record.checkpoint_id, decision="reject")
    observed = []

    def fault(stage):
        if stage == "before_displace":
            with pytest.raises(OSError) as error:
                directory.rename(tmp_path / "moved")
            observed.append(error.value.winerror)

    CheckpointService(tmp_path, fault=fault).apply(plan.plan_id)
    assert observed and path.read_bytes() == b"before"
    assert not (tmp_path / "moved").exists()


@native
def test_native_readonly_file_is_explicitly_nonrestorable(tmp_path):
    path = tmp_path / "readonly"
    path.write_bytes(b"do not change attributes")
    path.chmod(0o444)
    try:
        service = CheckpointService(tmp_path)
        record = service.begin(["readonly"], actor="test")
        service.complete(record.checkpoint_id)
        assert service.review(record.checkpoint_id).files[0].before.status == "unsupported"
        with pytest.raises(ValueError, match="non-restorable"):
            service.preview(record.checkpoint_id, decision="reject")
    finally:
        path.chmod(0o666)


@native
def test_native_storage_junction_is_rejected_before_writing_external_directory(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-external-storage")
    outside.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(tmp_path / ".henchman"), str(outside)], check=True, capture_output=True)
    with pytest.raises((ValueError, OSError)):
        CheckpointService(tmp_path)
    assert list(outside.iterdir()) == []


@native
def test_native_file_symlink_is_nonrestorable(tmp_path):
    target = tmp_path / "target"
    target.write_bytes(b"target bytes")
    try:
        (tmp_path / "symlink").symlink_to(target)
    except OSError as error:
        if error.winerror == 1314:
            pytest.skip("Host lacks the native symlink privilege; junction rejection is tested separately")
        raise
    service = CheckpointService(tmp_path)
    record = service.begin(["symlink"], actor="test")
    service.complete(record.checkpoint_id)
    assert service.review(record.checkpoint_id).files[0].before.status == "unsupported"


@native
def test_native_acl_widening_is_denied_before_content_capture(tmp_path):
    service, _ = _plan(tmp_path)
    subprocess.run(["icacls", str(service._store.path), "/grant", "*S-1-1-0:(OI)(CI)F"], check=True, capture_output=True)
    with pytest.raises(ValueError, match="private"):
        service.begin(["file.txt"], actor="test")


@native
def test_native_secrets_and_bounded_content_do_not_enter_history(tmp_path):
    from henchman.utils.evidence_redaction import EvidenceRedactor

    policy = EvidenceRedactor(["windows-private-content-canary"])
    samples = {"secret": b"windows-private-content-canary", "binary": b"a\0b", "large": b"a" * 101,
               ".env": b"excluded-canary"}
    for name, value in samples.items():
        (tmp_path / name).write_bytes(value)
    service = CheckpointService(tmp_path, redactor=policy, max_file_bytes=100)
    record = service.begin(list(samples), actor="test")
    service.complete(record.checkpoint_id)
    assert {file.path: file.before.status for file in service.review(record.checkpoint_id).files} == {
        "secret": "secret", "binary": "binary", "large": "oversized", ".env": "excluded",
    }
    evidence = b"".join(path.read_bytes() for path in service._store.path.glob("*.json"))
    assert samples["secret"] not in evidence and samples[".env"] not in evidence


@native
def test_native_cross_process_capture_serializes_private_records(tmp_path):
    (tmp_path / "file").write_bytes(b"original")
    code = """import sys
from pathlib import Path
from henchman.advanced.checkpoints import CheckpointService
CheckpointService(Path(sys.argv[1])).begin(['file'], actor=sys.argv[2])
"""
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    processes = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path), f"process-{index}"], env=environment)
                 for index in range(3)]
    assert [process.wait(timeout=30) for process in processes] == [0, 0, 0]
    assert len(CheckpointService(tmp_path).list_checkpoints()) == 3


def test_directory_guard_requests_data_access_for_windows_share_enforcement(tmp_path, monkeypatch):
    """Attribute-only opens do not establish the intended delete-sharing guard."""
    import ctypes
    from contextlib import nullcontext
    from types import SimpleNamespace

    from henchman.advanced import checkpoint_windows

    accesses = []
    closed = []

    def create_file(_path, access, share, *_args):
        accesses.append((access, share))
        return 123

    api = object.__new__(checkpoint_windows.WindowsApi)
    api.kernel = SimpleNamespace(CreateFileW=create_file, CloseHandle=closed.append)
    api.private_security = lambda: nullcontext(ctypes.c_void_p())
    api.info = lambda _handle: SimpleNamespace(attributes=0x10, links=1)
    api.check_name = lambda _handle, _path: None
    monkeypatch.setattr(checkpoint_windows, "_last_error", lambda: 0)
    with api.open(tmp_path, directory=True):
        access, share = accesses[0]
        assert access & 0x1  # FILE_LIST_DIRECTORY / FILE_READ_DATA
        assert share & 0x2  # FILE_SHARE_WRITE: replacing children needs parent write access
        assert not share & 0x4  # FILE_SHARE_DELETE
    assert closed == [123]


@native
def test_native_directory_guard_allows_child_replacement_but_denies_parent_rename(tmp_path):
    from henchman.advanced.checkpoint_windows import windows_api

    directory = tmp_path / "held"
    directory.mkdir()
    target = directory / "target"
    target.write_bytes(b"old")
    with windows_api().open(directory, directory=True):
        temporary = directory / "new"
        temporary.write_bytes(b"complete new bytes")
        os.replace(temporary, target)
        assert target.read_bytes() == b"complete new bytes"
        with pytest.raises(OSError):
            directory.rename(tmp_path / "moved")
    assert directory.exists() and not (tmp_path / "moved").exists()
