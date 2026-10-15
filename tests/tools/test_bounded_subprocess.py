"""Real subprocess coverage for bounded capture and owned-process cleanup."""

import asyncio
import math
import os
import sys
from contextlib import suppress
from pathlib import Path

import pytest

from henchman.tools import subprocess_utils


async def test_both_pipes_are_drained_with_bounded_capture(tmp_path: Path) -> None:
    result = await subprocess_utils.run_bounded_subprocess(
        [sys.executable, "-c", "import os; os.write(1, b'a'*2000000); os.write(2, b'b'*2000000)"],
        cwd=tmp_path, timeout=5, max_output_bytes=1024,
    )
    assert result.stdout == b"a" * 1024
    assert result.stderr == b"b" * 1024
    assert result.stdout_truncated and result.stderr_truncated
    assert result.returncode == 0


async def test_argv_cwd_utf8_and_nonzero_exit(tmp_path: Path) -> None:
    directory = tmp_path / "directory with spaces"
    directory.mkdir()
    argument = "literal $(touch injected) ; & | > 'quoted'"
    result = await subprocess_utils.run_bounded_subprocess(
        [sys.executable, "-c", "import os,sys; print(os.getcwd()); print(sys.argv[1]); "
         "print('café'); print('failure', file=sys.stderr); sys.exit(7)", argument],
        cwd=directory, timeout=5,
    )
    assert result.stdout.decode("utf-8").splitlines() == [str(directory), argument, "café"]
    assert result.stderr.decode("utf-8").strip() == "failure"
    assert result.returncode == 7
    assert not result.stdout_truncated and not result.stderr_truncated
    assert not (directory / "injected").exists()


@pytest.mark.parametrize("size,truncated", [(16, False), (17, True), (0, False)])
async def test_capture_limit_is_exact(tmp_path: Path, size: int, truncated: bool) -> None:
    result = await subprocess_utils.run_bounded_subprocess(
        [sys.executable, "-c", f"import os; os.write(1, b'x'*{size})"],
        cwd=tmp_path, timeout=5, max_output_bytes=16,
    )
    assert result.stdout == b"x" * min(size, 16)
    assert result.stdout_truncated is truncated
    assert result.stderr == b""
    assert result.stderr_truncated is False


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan, True])
async def test_invalid_timeout_rejected_before_spawn(tmp_path: Path, monkeypatch, timeout) -> None:
    async def forbidden(*_args, **_kwargs):
        pytest.fail("invalid arguments must not spawn a process")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(ValueError, match="timeout"):
        await subprocess_utils.run_bounded_subprocess(
            [sys.executable], cwd=tmp_path, timeout=timeout,
        )


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, 2**40])
async def test_invalid_capture_limit_rejected_before_spawn(tmp_path: Path, monkeypatch, limit) -> None:
    async def forbidden(*_args, **_kwargs):
        pytest.fail("invalid arguments must not spawn a process")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(ValueError, match="max_output_bytes"):
        await subprocess_utils.run_bounded_subprocess(
            [sys.executable], cwd=tmp_path, timeout=5, max_output_bytes=limit,
        )


@pytest.mark.parametrize("interrupt", ["timeout", "cancel", "repeated_cancel"])
async def test_interruption_reaps_process(tmp_path: Path, monkeypatch, interrupt: str) -> None:
    created = asyncio.Event()
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()
    processes = []
    real_create = asyncio.create_subprocess_exec
    real_stop = subprocess_utils._stop_subprocess

    async def create(*args, **kwargs):
        process = await real_create(*args, **kwargs)
        processes.append(process)
        created.set()
        return process

    async def stop(process, **kwargs):
        cleanup_started.set()
        await release_cleanup.wait()
        await real_stop(process, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(subprocess_utils, "_stop_subprocess", stop)
    task = asyncio.create_task(subprocess_utils.run_bounded_subprocess(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        cwd=tmp_path, timeout=0.05 if interrupt == "timeout" else 30,
    ))
    try:
        await asyncio.wait_for(created.wait(), 5)
        if interrupt != "timeout":
            task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), 5)
        if interrupt == "repeated_cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        release_cleanup.set()
        with pytest.raises(TimeoutError if interrupt == "timeout" else asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert processes[0].returncode is not None
    finally:
        release_cleanup.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for process in processes:
            if process.returncode is None:
                process.kill()
                await process.wait()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group cleanup")
async def test_descendant_holding_pipes_cannot_hang_timeout(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    pid_file = tmp_path / "descendant.pid"
    descendant = (
        "import os,pathlib,signal,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
        "path = pathlib.Path(sys.argv[2]); "
        "\nwhile True:\n path.write_text(str(time.monotonic_ns()))\n time.sleep(0.01)"
    )
    code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]])"
    )
    try:
        async with asyncio.timeout(8):
            with pytest.raises(TimeoutError):
                await subprocess_utils.run_bounded_subprocess(
                    [sys.executable, "-c", code, descendant, str(pid_file), str(heartbeat)],
                    cwd=tmp_path, timeout=0.5,
                )
        assert pid_file.exists()
        before = heartbeat.read_text()
        await asyncio.sleep(0.1)
        assert heartbeat.read_text() == before, "descendant survived interrupted cleanup"
    finally:
        if pid_file.exists():
            with suppress(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 9)


async def test_reader_failure_also_reaps_child(tmp_path: Path, monkeypatch) -> None:
    processes = []
    real_create = asyncio.create_subprocess_exec

    async def create(*args, **kwargs):
        process = await real_create(*args, **kwargs)
        processes.append(process)
        return process

    async def broken_reader(_reader, _limit):
        raise OSError("reader failed")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(subprocess_utils, "_read_bounded", broken_reader)
    try:
        with pytest.raises(ExceptionGroup, match="TaskGroup"):
            await subprocess_utils.run_bounded_subprocess(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=tmp_path, timeout=5,
            )
        assert processes[0].returncode is not None
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
                await process.wait()
