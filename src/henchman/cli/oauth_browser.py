"""Explicit owned browser handoff; no URL is passed on the helper's argv."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from henchman.cli.oauth_browser_child import browser_environment, valid_authorization_url
from henchman.mcp.oauth import OAuthError

READY_TIMEOUT_SECONDS = 5.0
LAUNCH_TIMEOUT_SECONDS = 10.0
STOP_TIMEOUT_SECONDS = 2.0
MAX_CONTROL_BYTES = 64
_CLEANUP_NOTE = "Browser launcher cleanup could not confirm exit."
_HANDOFF_NOTE = "The authorization page may have opened; no automatic retry."


class BrowserLaunchError(OAuthError):
    """Value-free launcher diagnostic; never permission to retry automatically."""


def _child_command() -> tuple[str, ...]:
    return (str(Path(sys.executable).resolve()), "-I", str(Path(__file__).with_name("oauth_browser_child.py").resolve()))


def _authorize(authorize: Callable[[], object]) -> None:
    try:
        if not callable(authorize) or authorize() is not None:
            raise ValueError
    except Exception:
        raise BrowserLaunchError("Browser launch requires current explicit caller authority") from None


async def _check_controls(deadline: float) -> None:
    """Deliver queued cancellation, without suspending an authorized live handoff."""
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        # Preserve the original queued cancellation reason. If an adapter already
        # swallowed it, its outstanding cancellation still cannot authorize work.
        await asyncio.sleep(0)
        raise asyncio.CancelledError("Browser launch was cancelled")
    if asyncio.get_running_loop().time() >= deadline:
        raise BrowserLaunchError("Browser launcher exceeded its deadline")


async def _remaining_output(reader: asyncio.StreamReader) -> bytes:
    value = bytearray()
    while chunk := await reader.read(MAX_CONTROL_BYTES + 1):
        if len(value) + len(chunk) > MAX_CONTROL_BYTES:
            raise BrowserLaunchError("Browser launcher control output exceeds its bound")
        value.extend(chunk)
    return bytes(value)


def _close_pipes(process: asyncio.subprocess.Process) -> None:
    if process.stdin is not None:
        process.stdin.close()
    # Closing our reader also bounds settlement if an invalid helper's child
    # retains a writer. The supported launcher redirects these descriptors.
    transport = getattr(process, "_transport", None)
    if transport is not None:
        pipe = transport.get_pipe_transport(1)
        if pipe is not None:
            pipe.close()


async def _cleanup(
    spawn: asyncio.Task[asyncio.subprocess.Process], process: asyncio.subprocess.Process | None,
    reader: asyncio.Task[bytes] | None,
) -> None:
    try:
        if process is None:
            if spawn.done() and not spawn.cancelled() and spawn.exception() is not None:
                return  # Native spawn failed before returning an owned process.
            try:
                process = await asyncio.wait_for(asyncio.shield(spawn), STOP_TIMEOUT_SECONDS)
            except TimeoutError:
                spawn.cancel()
                try:
                    process = await asyncio.wait_for(spawn, STOP_TIMEOUT_SECONDS)
                except asyncio.CancelledError:
                    return
        _close_pipes(process)
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            except OSError:
                with suppress(ProcessLookupError):
                    process.kill()
            try:
                await asyncio.wait_for(process.wait(), STOP_TIMEOUT_SECONDS)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await asyncio.wait_for(process.wait(), STOP_TIMEOUT_SECONDS)
    finally:
        if reader is not None:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


async def _settle(
    spawn: asyncio.Task[asyncio.subprocess.Process], process: asyncio.subprocess.Process | None,
    reader: asyncio.Task[bytes] | None, primary: BaseException | None,
) -> BaseException | None:
    cleanup = asyncio.create_task(_cleanup(spawn, process, reader), name="henchman-oauth-browser-cleanup")
    try:
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                if primary is None or isinstance(primary, Exception):
                    primary = error
            except Exception:
                break
        cleanup.result()
    except BaseException:
        if primary is None:
            primary = BrowserLaunchError("Browser launcher cleanup could not confirm exit")
        else:
            primary.add_note(_CLEANUP_NOTE)
    return primary


async def open_oauth_browser(url: str, *, authorize: Callable[[], None]) -> None:
    """Hand one URL to an owned desktop launcher under current caller authority.

    Success means the launcher accepted the handoff, not that authentication
    completed. Cancellation after stdin handoff cannot revoke an opened page.
    """
    if not valid_authorization_url(url):
        raise BrowserLaunchError("Browser authorization URL is invalid or exceeds its bound")
    ready_deadline = asyncio.get_running_loop().time() + READY_TIMEOUT_SECONDS
    _authorize(authorize)
    await _check_controls(ready_deadline)
    spawn = asyncio.create_task(asyncio.create_subprocess_exec(
        *_child_command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=MAX_CONTROL_BYTES + 1,
        env=browser_environment(os.environ), cwd=Path.home(),
        start_new_session=sys.platform != "win32", creationflags=0x08000000 if sys.platform == "win32" else 0,
    ), name="henchman-oauth-browser-spawn")
    process, reader = None, None
    primary: BaseException | None = None
    handed_off = False
    try:
        async with asyncio.timeout_at(ready_deadline):
            process = await asyncio.shield(spawn)
            assert process.stdout is not None and process.stdin is not None
            status = await process.stdout.readline()
            if status == b"UNAVAILABLE\n":
                raise BrowserLaunchError("A supported desktop browser launcher is unavailable")
            if status != b"READY\n":
                raise BrowserLaunchError("Browser launcher did not become ready")
            await _check_controls(ready_deadline)
        reader = asyncio.create_task(_remaining_output(process.stdout), name="henchman-oauth-browser-output")
        launch_deadline = asyncio.get_running_loop().time() + LAUNCH_TIMEOUT_SECONDS
        async with asyncio.timeout_at(launch_deadline):
            _authorize(authorize)
            await _check_controls(launch_deadline)
            handed_off = True
            process.stdin.write((url + "\n").encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()
            # The owned child must consume EOF and exit. Joining its output and
            # process below also settles stdin without cancelling asyncio's shared
            # protocol-close future through StreamWriter.wait_closed().
            output = await asyncio.shield(reader)
            code = await process.wait()
            if output or code != 0:
                raise BrowserLaunchError("Browser launcher did not confirm a successful handoff")
            _authorize(authorize)
            await _check_controls(launch_deadline)
    except BaseException as error:
        primary = error
    primary = await _settle(spawn, process, reader, primary)
    if primary is not None:
        if handed_off:
            primary.add_note(_HANDOFF_NOTE)
        if not isinstance(primary, Exception):
            raise primary
        message = str(primary) if isinstance(primary, BrowserLaunchError) else "Browser launcher failed or exceeded its deadline"
        safe = BrowserLaunchError(message)
        for note in getattr(primary, "__notes__", ()):
            if note in (_CLEANUP_NOTE, _HANDOFF_NOTE):
                safe.add_note(note)
        raise safe from None
