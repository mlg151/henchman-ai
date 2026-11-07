"""Bounded framing over the pinned SDK's cross-platform process lifecycle.

The SDK 2.3 stdio reader accumulates an entire line before parsing. Keep its
process/tree cleanup policy, but bound bytes before decoding or JSON parsing.
The private lifecycle imports below are qualified against the exact SDK pin.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TextIO

import anyio
import anyio.lowlevel
from mcp.client._transport import TransportStreams
from mcp.client.stdio import (
    StdioServerParameters,
    _aclose_all,
    _create_platform_compatible_process,
    _drain_stdout,
    _get_executable_command,
    _stop_server_process,
    get_default_environment,
)
from mcp.shared.message import SessionMessage

from henchman.tools.contracts import MAX_VALUE_BYTES, SchemaContract, SchemaContractError
from mcp import types

MAX_STDIO_FRAME_BYTES = MAX_VALUE_BYTES
_FRAME_CONTRACT = SchemaContract(True)
_logger = logging.getLogger("mcp.client.stdio")


@dataclass
class StdioState:
    """A value-free terminal framing failure shared with the request adapter."""

    failure: SchemaContractError | None = None
    closed: bool = False


def _parse_frame(frame: bytes, encoding: str) -> SessionMessage | Exception:
    try:
        raw = json.loads(frame.decode(encoding, errors="strict"))
        _FRAME_CONTRACT.validate(raw)
        message = types.jsonrpc_message_adapter.validate_python(raw, by_name=False)
    except SchemaContractError as error:
        return SchemaContractError(f"mcp_wire_frame_{error.reason}")
    except RecursionError:
        return SchemaContractError("mcp_wire_frame_depth_limit")
    except ValueError:
        # Never hand the SDK a validator exception containing the rejected body.
        _logger.error("Failed to parse JSONRPC message from server: mcp_wire_frame_shape")
        return SchemaContractError("mcp_wire_frame_shape")
    return SessionMessage(message)


@asynccontextmanager
async def bounded_stdio_client(
    server: StdioServerParameters, *, errlog: TextIO, state: StdioState,
) -> AsyncIterator[TransportStreams]:
    """Run one stdio peer, with bounded frames and cancellation-safe shutdown."""
    command = await _get_executable_command(server.command)
    process = await _create_platform_compatible_process(
        command=command, args=server.args, env=get_default_environment() | (server.env or {}),
        errlog=errlog, cwd=server.cwd,
    )
    # No await between spawn and entering the task group: it owns every exit.
    sender, read_stream = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write_stream, receiver = anyio.create_memory_object_stream[SessionMessage](0)
    writer_done = anyio.Event()

    async def stdout_reader() -> None:
        assert process.stdout is not None
        buffer = bytearray()
        try:
            async with sender:
                try:
                    while True:
                        chunk = await process.stdout.receive(65536)
                        # A chunk can contain many short messages; retain only
                        # one bounded frame plus this bounded read at a time.
                        for index, fragment in enumerate(chunk.split(b"\n")):
                            if index:
                                parsed = _parse_frame(bytes(buffer), server.encoding)
                                if isinstance(parsed, SchemaContractError) and parsed.reason != "mcp_wire_frame_shape":
                                    state.failure = parsed
                                    return
                                await sender.send(parsed)
                                buffer.clear()
                            if len(buffer) + len(fragment) > MAX_STDIO_FRAME_BYTES:
                                state.failure = SchemaContractError("mcp_wire_frame_limit")
                                return
                            buffer.extend(fragment)
                except anyio.EndOfStream:
                    if buffer:
                        state.failure = SchemaContractError("mcp_wire_unterminated_frame")
        except (anyio.ClosedResourceError, anyio.BrokenResourceError, ConnectionError, OSError):
            pass
        finally:
            # Unblock pending requests before draining a pipe held by a server
            # or descendant. The shutdown helper closes that pipe explicitly.
            state.closed = True
            await sender.aclose()
            await _drain_stdout(process)

    async def stdin_writer() -> None:
        assert process.stdin is not None
        try:
            async with receiver:
                async for message in receiver:
                    payload = message.message.model_dump_json(by_alias=True, exclude_unset=True)
                    data = payload.encode(server.encoding, errors="strict")
                    if len(data) > MAX_STDIO_FRAME_BYTES:
                        state.failure = SchemaContractError("mcp_wire_frame_limit")
                        await sender.aclose()
                        return
                    await process.stdin.send(data + b"\n")
        except (anyio.ClosedResourceError, anyio.BrokenResourceError, OSError):
            await sender.aclose()
        finally:
            writer_done.set()

    async def shutdown() -> None:
        read_stream.close()
        write_stream.close()
        with anyio.move_on_after(0.5):
            await writer_done.wait()
        await _stop_server_process(process)
        await _aclose_all(read_stream, write_stream, sender, receiver)
        await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as group:
        group.start_soon(stdout_reader)
        group.start_soon(stdin_writer)
        try:
            yield read_stream, write_stream
        finally:
            with anyio.CancelScope(shield=True):
                await shutdown()
            group.cancel_scope.cancel()
    await anyio.lowlevel.cancel_shielded_checkpoint()
