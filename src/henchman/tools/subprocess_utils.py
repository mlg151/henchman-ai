"""Bounded execution and cleanup for Python verification subprocesses."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import signal
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

logger = logging.getLogger(__name__)

_STOP_TIMEOUT = 2.0
_MAX_CAPTURE_BYTES = 16 * 1024 * 1024
_ResultT = TypeVar("_ResultT")


def _close_output_pipes(process: asyncio.subprocess.Process) -> None:
    """Release local pipe handles even when a descendant keeps its end open."""
    transport = getattr(process, "_transport", None)
    if transport is not None:
        for descriptor in (1, 2):
            pipe = transport.get_pipe_transport(descriptor)
            if pipe is not None:
                pipe.close()


async def _stop_subprocess(
    process: asyncio.subprocess.Process, *, owned_process_group: bool = False,
) -> None:
    """Terminate, escalate to kill, and reap within bounded waits."""
    if owned_process_group:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
    elif process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=_STOP_TIMEOUT)
    except TimeoutError:
        with suppress(ProcessLookupError):
            if owned_process_group:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        # Descendants can keep the parent's output pipes open after it exits.
        # Closing our readers prevents that from blocking the final reap.
        _close_output_pipes(process)
        await asyncio.wait_for(process.wait(), timeout=_STOP_TIMEOUT)
    finally:
        if owned_process_group:
            # A reaped parent can leave descendants alive with inherited pipes.
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)


async def run_python_subprocess(
    command: list[str],
    *,
    timeout: float | None,
) -> tuple[bytes, bytes, int | None]:
    """Capture UTF-8 Python output and stop/reap on timeout or cancellation."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    # Keep draining pipes during cleanup, including when the caller cancels.
    communication = asyncio.create_task(process.communicate())
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), timeout=timeout)
    except (TimeoutError, asyncio.CancelledError) as error:
        interruption: BaseException = error
        if communication.cancelled():
            try:
                communication.result()
            except asyncio.CancelledError as original:
                interruption = original
        interruption = await _cleanup_interrupted(process, communication, interruption)
        raise interruption from None
    return stdout, stderr, process.returncode


async def _cleanup_interrupted(
    process: asyncio.subprocess.Process,
    communication: asyncio.Task[_ResultT],
    interruption: BaseException,
    *,
    owned_process_group: bool = False,
) -> BaseException:
    """Finish child and reader cleanup even if cancellation is repeated."""
    async def stop_and_close() -> None:
        try:
            if owned_process_group:
                await _stop_subprocess(process, owned_process_group=True)
            else:
                await _stop_subprocess(process)
        finally:
            communication.cancel()
            await asyncio.gather(communication, return_exceptions=True)

    cleanup = asyncio.create_task(stop_and_close())
    while True:
        try:
            await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError as cancelled:
            if cleanup.cancelled():
                logger.warning("Verification subprocess cleanup was cancelled")
                break
            if not isinstance(interruption, asyncio.CancelledError):
                interruption = cancelled
        except Exception:
            logger.warning("Failed to stop verification subprocess", exc_info=True)
            break
    return interruption


@dataclass(frozen=True)
class BoundedProcessResult:
    """Exit status and separately bounded stdout/stderr byte prefixes."""

    stdout: bytes
    stderr: bytes
    returncode: int | None
    stdout_truncated: bool
    stderr_truncated: bool


async def _read_bounded(reader: asyncio.StreamReader, limit: int) -> tuple[bytes, bool]:
    """Retain a prefix while draining all later bytes to prevent pipe deadlocks."""
    output = bytearray()
    truncated = False
    while chunk := await reader.read(65536):
        remaining = limit - len(output)
        output.extend(chunk[:remaining])
        truncated = truncated or len(chunk) > remaining
    return bytes(output), truncated


async def _capture_bounded(
    process: asyncio.subprocess.Process, limit: int,
) -> BoundedProcessResult:
    assert process.stdout is not None and process.stderr is not None
    # TaskGroup owns both readers and the wait task on every exit path.
    async with asyncio.TaskGroup() as group:
        stdout = group.create_task(_read_bounded(process.stdout, limit))
        stderr = group.create_task(_read_bounded(process.stderr, limit))
        group.create_task(process.wait())
    out, out_truncated = stdout.result()
    err, err_truncated = stderr.result()
    return BoundedProcessResult(out, err, process.returncode, out_truncated, err_truncated)


async def run_bounded_subprocess(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    max_output_bytes: int = 65536,
) -> BoundedProcessResult:
    """Run argv with bounded capture and cleanup; this is not a process sandbox.

    Each output prefix is limited to a configurable 1 byte through 16 MiB.
    Timeout and cancellation propagate after cleanup. POSIX children share an
    owned session for cleanup; on Windows cleanup targets the direct child.
    """
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if type(max_output_bytes) is not int or not 1 <= max_output_bytes <= _MAX_CAPTURE_BYTES:
        raise ValueError(f"max_output_bytes must be an integer from 1 to {_MAX_CAPTURE_BYTES}")
    owned_process_group = os.name == "posix"
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        start_new_session=owned_process_group,
    )
    communication = asyncio.create_task(_capture_bounded(process, max_output_bytes))
    try:
        return await asyncio.wait_for(asyncio.shield(communication), timeout=timeout)
    except BaseException as error:
        interruption = await _cleanup_interrupted(
            process, communication, error, owned_process_group=owned_process_group,
        )
        raise interruption from None
    finally:
        _close_output_pipes(process)
