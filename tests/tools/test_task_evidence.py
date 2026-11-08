"""Background evidence reaches disk only after bounded runtime projection."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from henchman.advanced.tasks import TaskRecord, TaskService


def _settings(project: Path, secret: str) -> None:
    path = project / ".henchman" / "settings.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"providers": {"options": {"test": {"api_key": secret}}}}))


async def _output_contains(service: TaskService, task_id: str, text: str) -> None:
    async with asyncio.timeout(5):
        while text not in service.tail_output(task_id, lines=0):
            await asyncio.sleep(0.01)


@pytest.mark.anyio
@pytest.mark.parametrize("stdio_encoding", ["utf-8", "cp1252"])
async def test_active_output_and_index_project_config_env_metadata_before_disk(
    tmp_path: Path, stdio_encoding: str,
) -> None:
    configured, explicit, metadata = "configured-task-canary", "env-task-canary", "meta-task-canary"
    unknown_header = "unknown-header-task-canary"
    _settings(tmp_path, configured)
    service = TaskService(tmp_path)
    code = (
        "import os,sys,time; "
        "print('raw execution:',sys.argv[1]==os.environ['ACCESS_TOKEN'],flush=True); "
        "print('stdio:',sys.stdout.encoding,flush=True); "
        f"os.write(1,{configured[:11]!r}.encode()); time.sleep(.05); "
        f"os.write(1,{(configured[11:] + chr(10))!r}.encode()); "
        "os.write(2,b'Authoriz'); time.sleep(.05); "
        f"os.write(2,{('ation: ' + unknown_header + chr(10))!r}.encode()); "
        f"print(os.environ['ACCESS_TOKEN'],{metadata!r},flush=True); "
        f"os.write(1,{('café 世界' + chr(10)).encode('utf-8')!r}); "
        "print('ready',flush=True); time.sleep(30)"
    )
    record = await service.start_task(
        argv=[sys.executable, "-u", "-c", code, explicit], title=f"task {configured}",
        env={**os.environ, "ACCESS_TOKEN": explicit, "PYTHONIOENCODING": stdio_encoding},
        metadata={"access_token": metadata, "note": f"echo {metadata}"},
    )
    try:
        await _output_contains(service, record.task_id, "ready")
        assert service.get_task(record.task_id).status == "running"
        output = record.output_path.read_text(encoding="utf-8")
        assert "raw execution: True" in output
        assert f"stdio: {stdio_encoding}" in output
        assert "café 世界" in output
        assert "[REDACTED]" in output
        index = service._index_path.read_text()
        for secret in (configured, explicit, metadata):
            assert secret not in output
            assert secret not in index
            assert secret not in repr(record)
        assert unknown_header not in output
        assert "Authorization: [REDACTED]" in output
        persisted = json.loads(index)["records"][0]
        assert persisted["task_id"] == record.task_id
        assert persisted["output_path"] == record.output_path.name
    finally:
        await service.stop_task(record.task_id)
    assert not service._runtime.processes
    assert not service._runtime.monitors


@pytest.mark.anyio
async def test_rotated_policy_retains_old_secrets_and_update_projects_evidence(tmp_path: Path) -> None:
    old, new, updated = "old-task-credential", "new-task-credential", "update-task-credential"
    _settings(tmp_path, old)
    service = TaskService(tmp_path)
    _settings(tmp_path, new)
    refreshed = TaskService(tmp_path)
    record = await refreshed.start_task(
        argv=[sys.executable, "-c", f"print({old!r}, {new!r})"],
    )
    await refreshed.wait_for_task(record.task_id, timeout=5)
    result = service.update_task(record.task_id, title=updated,
                                 metadata={"api_key": updated, "echo": old})
    evidence = service._index_path.read_text() + service.tail_output(record.task_id) + repr(result)
    assert all(secret not in evidence for secret in (old, new, updated))


@pytest.mark.anyio
async def test_short_secret_preserves_task_lookup_paths_and_private_files(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", "print('data')"],
                                      metadata={"token": "a"})
    final = await service.wait_for_task(record.task_id, timeout=5)
    persisted = json.loads(service._index_path.read_text())["records"][0]
    assert persisted["task_id"] == record.task_id
    assert persisted["status"] == "completed"
    assert final.output_path == record.output_path
    assert persisted["output_path"] == record.output_path.name
    assert final.output_path.name == f"{record.task_id}.log"
    assert "d[REDACTED]t[REDACTED]" in service.tail_output(record.task_id)
    if os.name == "posix":
        assert stat.S_IMODE(record.output_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(service._index_path.stat().st_mode) == 0o600


@pytest.mark.anyio
async def test_large_output_is_bounded_without_blocking_child(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    record = await service.start_task(
        argv=[sys.executable, "-c", "import sys; sys.stdout.write('x' * (3 * 1024 * 1024))"],
    )
    final = await service.wait_for_task(record.task_id, timeout=10)
    assert final.status == "completed"
    assert record.output_path.stat().st_size <= 1024 * 1024
    assert "output truncated" in service.tail_output(record.task_id, lines=0).lower()
    assert final.metadata["output_truncated"] == "true"


@pytest.mark.anyio
async def test_credential_in_project_path_is_not_persisted_or_used_as_redacted_path(tmp_path: Path) -> None:
    secret = "project-path-task-canary"
    project = tmp_path / secret
    project.mkdir()
    _settings(project, secret)
    service = TaskService(project)
    record = await service.start_task(argv=[sys.executable, "-c", "print('kept')"])
    await service.wait_for_task(record.task_id, timeout=5)
    assert secret not in service._index_path.read_text()
    assert record.output_path.parent == project / ".henchman" / "tasks"
    TaskService._runtimes.pop(service._storage_dir)
    resumed = TaskService(project)
    assert resumed.get_task(record.task_id).output_path == record.output_path
    assert resumed.tail_output(record.task_id) == "kept"


@pytest.mark.anyio
async def test_cancel_flushes_incomplete_credential_without_raw_prefix(tmp_path: Path) -> None:
    secret = "unfinished-task-credential"
    service = TaskService(tmp_path)
    record = await service.start_task(
        argv=[sys.executable, "-u", "-c",
              f"import time; print('ready',flush=True); print({secret[:13]!r},end='',flush=True); time.sleep(30)"],
        env={**os.environ, "ACCESS_TOKEN": secret},
    )
    await _output_contains(service, record.task_id, "ready")
    await asyncio.sleep(0.05)
    monitor = service._runtime.monitors[record.task_id]
    monitor.cancel()
    with pytest.raises(asyncio.CancelledError):
        await monitor
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "stopped"
    assert secret[:13] not in final.output_path.read_text()
    assert "[REDACTED]" in final.output_path.read_text()
    assert not service._runtime.processes


@pytest.mark.anyio
async def test_output_write_failure_terminates_reaps_and_redacts_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.advanced.task_output import TaskOutput

    secret = "write-failure-task-canary"
    service = TaskService(tmp_path)

    def fail_write(_self: TaskOutput, _text: str) -> None:
        raise OSError(f"Authorization: unknown-error-header\ncannot save {secret}")

    monkeypatch.setattr(TaskOutput, "_write", fail_write)
    record = await service.start_task(
        argv=[sys.executable, "-u", "-c", "import time; print('hello',flush=True); time.sleep(30)"],
        env={**os.environ, "ACCESS_TOKEN": secret},
    )
    process = service._runtime.processes[record.task_id]
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "failed"
    assert process.returncode is not None
    assert secret not in repr(final)
    assert "unknown-error-header" not in repr(final)
    assert "[REDACTED]" in final.metadata["error"]
    assert not service._runtime.processes
    assert not service._runtime.monitors
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


@pytest.mark.anyio
async def test_index_replace_failure_is_atomic_private_and_prevents_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from henchman.advanced import tasks

    secret = "index-failure-task-canary"
    service = TaskService(tmp_path)
    before = service._index_path.read_bytes()
    created = []
    spawn = asyncio.create_subprocess_exec

    async def tracked_spawn(*args: object, **kwargs: object):
        process = await spawn(*args, **kwargs)
        created.append(process)
        return process

    def fail_replace(source: object, _target: object, **_kwargs: object) -> None:
        temporary = service._storage_dir / str(source)
        assert secret not in temporary.read_text()
        if os.name == "posix":
            assert stat.S_IMODE(temporary.stat().st_mode) == 0o600
        raise OSError(f"replace refused {secret}")

    monkeypatch.setattr(tasks.os, "replace", fail_replace)
    monkeypatch.setattr(tasks.asyncio, "create_subprocess_exec", tracked_spawn)
    with pytest.raises(OSError) as caught:
        await service.start_task(
            argv=[sys.executable, "-c", "import time; time.sleep(30)"], title=secret,
            env={**os.environ, "ACCESS_TOKEN": secret},
        )
    assert secret not in str(caught.value)
    assert created == []
    assert service._index_path.read_bytes() == before
    assert not list(service._storage_dir.glob("*.tmp"))
    assert not service._runtime.processes
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


@pytest.mark.anyio
async def test_spawn_failure_closes_capture_and_redacts_exception(tmp_path: Path) -> None:
    secret = "missing-executable-task-canary"
    service = TaskService(tmp_path)
    with pytest.raises(OSError) as caught:
        await service.start_task(argv=[str(tmp_path / secret)], metadata={"token": secret})
    assert secret not in str(caught.value)
    assert not service._runtime.processes
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


@pytest.mark.anyio
@pytest.mark.skipif(os.name != "posix", reason="Escaped process session uses POSIX")
async def test_descendant_retained_writer_does_not_delay_completion(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    code = (
        "import subprocess,sys; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'],start_new_session=True); "
        "print(p.pid,flush=True)"
    )
    record = await service.start_task(argv=[sys.executable, "-u", "-c", code])
    try:
        final = await service.wait_for_task(record.task_id, timeout=1)
        assert final.status == "completed"
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]
    finally:
        output = service.tail_output(record.task_id).strip()
        if output.isdigit():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(output), 9)


@pytest.mark.anyio
async def test_split_utf8_and_failed_traceback_are_projected_before_disk(tmp_path: Path) -> None:
    secret = "traceback-task-canary"
    service = TaskService(tmp_path)
    code = (
        "import os,time; os.write(1,b'caf\\xc3'); time.sleep(.05); "
        "os.write(1,b'\\xa9 \\xe4\\xb8'); time.sleep(.05); os.write(1,b'\\x96\\xe7\\x95\\x8c\\n'); "
        f"raise ValueError({secret!r})"
    )
    record = await service.start_task(argv=[sys.executable, "-c", code], metadata={"token": secret})
    final = await service.wait_for_task(record.task_id, timeout=5)
    evidence = record.output_path.read_text(encoding="utf-8")
    assert final.status == "failed"
    assert "café 世界" in evidence
    assert "Traceback" in evidence
    assert "ValueError: [REDACTED]" in evidence
    assert secret not in evidence


@pytest.mark.anyio
async def test_cancel_during_spawn_reaps_process_and_awaits_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation cannot lose ownership between process creation and return."""
    from henchman.advanced import tasks

    service = TaskService(tmp_path)
    created = []
    spawned = asyncio.Event()
    release = asyncio.Event()
    native_spawn = asyncio.create_subprocess_exec

    async def delayed_spawn(*args: object, **kwargs: object):
        process = await native_spawn(*args, **kwargs)
        created.append(process)
        spawned.set()
        await release.wait()
        return process

    monkeypatch.setattr(tasks.asyncio, "create_subprocess_exec", delayed_spawn)
    launch = asyncio.create_task(service.start_task(
        argv=[sys.executable, "-c", "import time; time.sleep(30)"],
    ))
    try:
        await asyncio.wait_for(spawned.wait(), timeout=5)
        launch.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await launch
        assert created[0].returncode is not None
        assert not service._runtime.processes
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]
    finally:
        release.set()
        if created and created[0].returncode is None:
            created[0].kill()
            await created[0].wait()


@pytest.mark.anyio
async def test_repeated_monitor_cancellation_finishes_owned_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TaskService(tmp_path)
    terminating = asyncio.Event()
    release = asyncio.Event()
    terminate = service._terminate_process

    async def delayed_terminate(process):
        terminating.set()
        await release.wait()
        await terminate(process)

    monkeypatch.setattr(service, "_terminate_process", delayed_terminate)
    record = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
    process = service._runtime.processes[record.task_id]
    monitor = service._runtime.monitors[record.task_id]
    monitor.cancel()
    await asyncio.wait_for(terminating.wait(), timeout=5)
    monitor.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await monitor
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "stopped"
    assert process.returncode is not None
    assert not service._runtime.monitors
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


@pytest.mark.anyio
async def test_loaded_index_cannot_redirect_log_read_to_an_external_path(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", "print('owned')"])
    await service.wait_for_task(record.task_id, timeout=5)
    external = tmp_path / "outside.txt"
    external.write_text("not owned")
    # Legacy absolute paths are migrated as evidence, never followed. A changed
    # versioned index would instead fail its integrity check before reading.
    payload = json.loads(service._index_path.read_text())["records"]
    payload[0]["output_path"] = str(external)
    service._index_path.write_text(json.dumps(payload))
    service._index_path.with_suffix(".lock").unlink()
    TaskService._runtimes.pop(service._storage_dir)
    resumed = TaskService(tmp_path)
    assert resumed.tail_output(record.task_id) == "owned"
    assert resumed.get_task(record.task_id).output_path == record.output_path


@pytest.mark.anyio
async def test_log_read_failure_projects_path_credentials_before_raising(tmp_path: Path) -> None:
    secret = "read-path-task-canary"
    project = tmp_path / secret
    project.mkdir()
    _settings(project, secret)
    service = TaskService(project)
    record = await service.start_task(argv=[sys.executable, "-c", "print('kept')"])
    await service.wait_for_task(record.task_id, timeout=5)
    record.output_path.unlink()
    record.output_path.mkdir()
    with pytest.raises(OSError) as caught:
        service.tail_output(record.task_id)
    assert secret not in str(caught.value)


def _legacy_task(project: Path, content: bytes) -> tuple[Path, Path, str]:
    service = TaskService(project)
    task_id = "task-012345abcdef"
    path = service._storage_dir / f"{task_id}.log"
    record = TaskRecord(task_id=task_id, title="legacy", argv=("legacy",), cwd=str(project),
                        status="completed", created_at="2026-01-01T00:00:00+00:00",
                        started_at="2026-01-01T00:00:00+00:00", finished_at="2026-01-01T00:01:00+00:00",
                        output_path=path, pid=None, return_code=0, metadata={})
    service._index_path.write_text(json.dumps([record.to_dict()]))
    service._index_path.with_suffix(".lock").unlink()
    path.write_bytes(content)
    TaskService._runtimes.pop(service._storage_dir)
    return service._index_path, path, task_id


def test_legacy_log_is_projected_privately_on_load_and_remains_bounded(tmp_path: Path) -> None:
    secret = "legacy-log-task-canary"
    _settings(tmp_path, secret)
    _, path, task_id = _legacy_task(
        tmp_path, (secret + "\nAuthorization: opaque-legacy-header\n").encode() + b"x" * (2 * 1024 * 1024),
    )
    service = TaskService(tmp_path)
    content = path.read_bytes()
    assert secret.encode() not in content
    assert b"opaque-legacy-header" not in content
    assert b"[REDACTED]" in content
    assert b"output truncated" in content.lower()
    assert len(content) <= 1024 * 1024
    assert service.get_task(task_id).metadata["output_truncated"] == "true"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_newly_known_legacy_value_is_migrated_on_read(tmp_path: Path) -> None:
    secret = "late-log-task-canary"
    _, path, task_id = _legacy_task(tmp_path, (secret + "\nkept\n").encode())
    service = TaskService(tmp_path)
    _settings(tmp_path, secret)
    assert secret not in service.tail_output(task_id, lines=0)
    assert secret.encode() not in path.read_bytes()
    assert "kept" in path.read_text()


@pytest.mark.parametrize("raw", [b"{broken", b"", b"null", b'[{}]', b'[{"task_id":"../escape"}]'])
def test_corrupt_index_is_reported_without_overwriting(tmp_path: Path, raw: bytes) -> None:
    service = TaskService(tmp_path)
    service._index_path.write_bytes(raw)
    TaskService._runtimes.pop(service._storage_dir)
    with pytest.raises(ValueError, match="index"):
        TaskService(tmp_path)
    assert service._index_path.read_bytes() == raw


def test_corrupt_log_is_retained_with_explicit_safe_migration_error(tmp_path: Path) -> None:
    secret = "corrupt-log-task-canary"
    _settings(tmp_path, secret)
    original = secret.encode() + b"\xff\xfe"
    _, path, task_id = _legacy_task(tmp_path, original)
    service = TaskService(tmp_path)
    assert path.read_bytes() == original
    record = service.get_task(task_id)
    assert "migration" in record.metadata["error"].lower()
    assert secret not in repr(record)
    with pytest.raises(OSError, match="migration"):
        service.tail_output(task_id)
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.tmp"))


def test_legacy_log_symlink_is_never_followed(tmp_path: Path) -> None:
    _, path, task_id = _legacy_task(tmp_path, b"owned")
    target = tmp_path / "outside.log"
    target.write_bytes(b"Authorization: external-canary\n")
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks is unavailable")
    service = TaskService(tmp_path)
    with pytest.raises(OSError, match="migration"):
        service.tail_output(task_id)
    assert path.is_symlink()
    assert target.read_bytes() == b"Authorization: external-canary\n"
    assert "external-canary" not in repr(service.get_task(task_id))


def test_index_symlink_is_never_followed_or_replaced(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    target = tmp_path / "outside.json"
    target.write_bytes(b"[]")
    service._index_path.unlink()
    try:
        service._index_path.symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks is unavailable")
    TaskService._runtimes.pop(service._storage_dir)
    with pytest.raises(OSError):
        TaskService(tmp_path)
    assert service._index_path.is_symlink()
    assert target.read_bytes() == b"[]"


@pytest.mark.anyio
async def test_live_capture_is_not_replaced_by_reload_or_read(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    release = tmp_path / "release"
    code = ("import time,pathlib; print('first',flush=True); "
            f"p=pathlib.Path({str(release)!r}); "
            "exec('while not p.exists(): time.sleep(.01)'); print('second',flush=True)")
    record = await service.start_task(argv=[sys.executable, "-u", "-c", code])
    try:
        await _output_contains(service, record.task_id, "first")
        original = record.output_path.stat()
        other = TaskService(tmp_path)
        assert "first" in other.tail_output(record.task_id)
        assert os.path.samestat(original, record.output_path.stat())
        release.touch()
        await service.wait_for_task(record.task_id, timeout=5)
        assert "second" in record.output_path.read_text()
    finally:
        await service.stop_task(record.task_id)


def test_failed_legacy_replace_retains_original_and_reports_safe_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "legacy-replace-task-canary"
    _settings(tmp_path, secret)
    _, path, task_id = _legacy_task(tmp_path, secret.encode())
    replace = os.replace

    def fail_log_replace(source, destination, **kwargs):
        if str(destination).endswith(".log"):
            raise OSError(f"Authorization: opaque-replace-header\n{secret}")
        return replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", fail_log_replace)
    service = TaskService(tmp_path)
    assert path.read_bytes() == secret.encode()
    error = service.get_task(task_id).metadata["error"]
    assert "migration" in error.lower()
    assert secret not in error
    assert "opaque-replace-header" not in error
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.anyio
@pytest.mark.parametrize("fault", ["short_write", "zero_write", "close_error", "reader_close_error"])
async def test_capture_short_writes_and_cleanup_faults_settle_owned_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str,
) -> None:
    from henchman.advanced.task_output import TaskOutput

    service = TaskService(tmp_path)
    initialize = TaskOutput.__init__
    close_fd = os.close
    readers = set()
    captures: list[TaskOutput] = []

    class OutputProxy:
        def __init__(self, output):
            self.output = output

        def write(self, data):
            if fault == "zero_write":
                return 0
            return self.output.write(data[:3] if fault == "short_write" else data)

        def close(self):
            self.output.close()
            if fault == "close_error":
                raise OSError("Authorization: close-failure-canary")

    def wrapped_initialize(self, path, policy):
        initialize(self, path, policy)
        self._output = OutputProxy(self._output)
        readers.add(self._reader)
        captures.append(self)

    def wrapped_close(fd):
        close_fd(fd)
        if fault == "reader_close_error" and fd in readers:
            readers.remove(fd)
            raise OSError("Authorization: reader-close-canary")

    monkeypatch.setattr(TaskOutput, "__init__", wrapped_initialize)
    monkeypatch.setattr(os, "close", wrapped_close)
    record = await service.start_task(argv=[sys.executable, "-u", "-c", "print('complete evidence')"])
    process = service._runtime.processes[record.task_id]
    try:
        if fault != "short_write":
            # Allow native interpreter startup before measuring fault cleanup.
            # The old single five-second wait conflated those separate phases.
            await asyncio.wait_for(asyncio.shield(captures[0].failure), timeout=15)
        final = await service.wait_for_task(record.task_id, timeout=15 if fault == "short_write" else 5)
    finally:
        await service.stop_task(record.task_id)
    assert process.returncode is not None
    if fault == "short_write":
        assert final.status == "completed"
        assert record.output_path.read_text() == "complete evidence\n"
    else:
        assert final.status == "failed", (
            f"status={final.status!r}, metadata={final.metadata!r}, "
            f"returncode={process.returncode!r}, capture_error={captures[0].error!r}"
        )
        assert "capture" in final.metadata["error"]
        assert "close-failure-canary" not in repr(final)
        assert "reader-close-canary" not in repr(final)
    assert not service._runtime.monitors
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


def test_oversized_legacy_input_is_preserved_with_explicit_limit(tmp_path: Path) -> None:
    _, path, task_id = _legacy_task(tmp_path, b"retained evidence")
    with path.open("ab") as output:
        output.truncate(17 * 1024 * 1024)
    service = TaskService(tmp_path)
    assert path.stat().st_size == 17 * 1024 * 1024
    assert "16 MiB" in service.get_task(task_id).metadata["error"]
    with pytest.raises(OSError, match="16 MiB"):
        service.tail_output(task_id)


def test_storage_directory_symlink_is_not_followed(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    before = service._index_path.read_bytes()
    moved = tmp_path / "external-tasks"
    service._storage_dir.rename(moved)
    try:
        service._storage_dir.symlink_to(moved, target_is_directory=True)
    except OSError:
        moved.rename(service._storage_dir)
        pytest.skip("Creating directory symlinks is unavailable")
    TaskService._runtimes.pop(service._storage_dir)
    with pytest.raises(OSError):
        TaskService(tmp_path)
    assert (moved / "index.json").read_bytes() == before


@pytest.mark.anyio
async def test_timeout_diagnostic_does_not_follow_replaced_log_symlink(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    record = await service.start_task(
        argv=[sys.executable, "-u", "-c", "import time; print('started',flush=True); time.sleep(30)"],
        timeout=0.3,
    )
    target = tmp_path / "external.log"
    target.write_text("unchanged")
    try:
        await _output_contains(service, record.task_id, "started")
        try:
            record.output_path.unlink()
            record.output_path.symlink_to(target)
        except OSError:
            pytest.skip("Replacing an open file with a symlink is unavailable")
        final = await service.wait_for_task(record.task_id, timeout=5)
        assert final.status == "failed"
        assert target.read_text() == "unchanged"
        assert "timeout" in final.metadata["error"].lower()
    finally:
        await service.stop_task(record.task_id)


@pytest.mark.anyio
async def test_corrupt_index_before_launch_prevents_process_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TaskService(tmp_path)
    corrupt = b'{"broken": "corrupt-index-canary"'
    service._index_path.write_bytes(corrupt)
    native_spawn = asyncio.create_subprocess_exec
    created = []

    async def tracked_spawn(*args, **kwargs):
        process = await native_spawn(*args, **kwargs)
        created.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", tracked_spawn)
    try:
        with pytest.raises(OSError, match="index") as caught:
            await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        assert "corrupt-index-canary" not in str(caught.value)
        assert created == []
        assert service._index_path.read_bytes() == corrupt
        assert not service._runtime.processes
        assert not service._runtime.monitors
        assert not service._runtime.waiters
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]
    finally:
        if created and created[0].returncode is None:
            created[0].kill()
            await created[0].wait()


@pytest.mark.anyio
async def test_corrupt_index_during_execution_still_settles_final_waiter(tmp_path: Path) -> None:
    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(.15)"])
    process = service._runtime.processes[record.task_id]
    corrupt = b'{"broken": "corrupt-index-canary"'
    service._index_path.write_bytes(corrupt)
    final = await service.wait_for_task(record.task_id, timeout=5)
    assert final.status == "failed"
    assert final.pid is None
    assert process.returncode is not None
    assert "persist" in final.metadata["error"].lower()
    assert "corrupt-index-canary" not in repr(final)
    assert service._index_path.read_bytes() == corrupt
    assert not service._runtime.processes
    assert not service._runtime.monitors
    assert not service._runtime.waiters
