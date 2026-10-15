"""Real input parsing for standalone Escape and terminal escape sequences."""

import asyncio
from contextlib import suppress

import pytest
from prompt_toolkit.input import create_pipe_input

from henchman.cli.input import KeyMonitor


@pytest.fixture
def monitored_input(monkeypatch):
    with create_pipe_input() as pipe:
        monkeypatch.setattr("prompt_toolkit.input.create_input", lambda: pipe)
        yield KeyMonitor(), pipe


async def stop_monitor(monitor, task):
    monitor._stop_event.set()
    with suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)


@pytest.mark.asyncio
async def test_standalone_escape_stops_monitor_without_another_key(monitored_input):
    monitor, pipe = monitored_input
    task = asyncio.create_task(monitor.monitor())
    try:
        pipe.send_bytes(b"\x1b")
        await asyncio.wait_for(task, 2)
        assert monitor.stop_requested
        assert not monitor.exit_requested
        assert not monitor._in_raw_mode
    finally:
        await stop_monitor(monitor, task)


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", [b"[A", b"OP", b"[15~"])
async def test_split_arrow_and_function_keys_do_not_cancel(monitored_input, monkeypatch, suffix):
    monitor, pipe = monitored_input
    parsed_prefix = asyncio.Event()
    read_keys = pipe.read_keys

    def observe_read():
        keys = read_keys()
        parsed_prefix.set()
        return keys

    monkeypatch.setattr(pipe, "read_keys", observe_read)
    task = asyncio.create_task(monitor.monitor())
    try:
        pipe.send_bytes(b"\x1b")
        await asyncio.wait_for(parsed_prefix.wait(), 2)
        assert not monitor.stop_requested
        pipe.send_bytes(suffix + b"\x03")
        await asyncio.wait_for(task, 2)
        assert monitor.exit_requested
        assert not monitor.stop_requested
        assert not monitor._in_raw_mode
    finally:
        await stop_monitor(monitor, task)


@pytest.mark.asyncio
async def test_partial_sequence_activity_extends_escape_deadline(monitored_input, monkeypatch):
    """The timeout measures idle time, including fragments yielding no key yet."""
    monitor, pipe = monitored_input
    reads = asyncio.Queue()
    read_keys = pipe.read_keys

    def observe_read():
        keys = read_keys()
        reads.put_nowait(None)
        return keys

    monkeypatch.setattr(pipe, "read_keys", observe_read)
    task = asyncio.create_task(monitor.monitor())
    try:
        pipe.send_bytes(b"\x1b")
        await asyncio.wait_for(reads.get(), 2)
        # Each gap is below the 0.5s VT timeout, but the whole sequence exceeds it.
        await asyncio.sleep(0.3)
        pipe.send_bytes(b"[")
        await asyncio.wait_for(reads.get(), 2)
        await asyncio.sleep(0.3)
        assert not monitor.stop_requested
        pipe.send_bytes(b"A\x03")
        await asyncio.wait_for(task, 2)
        assert monitor.exit_requested
        assert not monitor.stop_requested
    finally:
        await stop_monitor(monitor, task)
