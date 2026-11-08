"""Opt-in POSIX protocol transport over the shared one-run runtime."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from collections.abc import Callable, Coroutine, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import click

from henchman.cli.core_init import CoreContext, create_core_context
from henchman.cli.headless_protocol import (
    MAX_CHUNK_BYTES,
    FrameDecoder,
    ProtocolError,
    Request,
    ServerEncoder,
)
from henchman.cli.headless_runtime import HeadlessRuntime, HeadlessRuntimeError, _joined
from henchman.entrypoint import protocol_pipes

if TYPE_CHECKING:
    from henchman.integrations.neovim import EditorSelection

_T = TypeVar("_T")


async def _owned(operation: Coroutine[Any, Any, _T]) -> _T:
    """Deliver owner cancellation once and join, retaining the caller reason."""
    task = asyncio.create_task(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError as primary:
        if not task.done():
            task.cancel()
        try:
            await _joined(task)
        except BaseException:
            primary.add_note("Headless transport owner settled after interruption")
        raise primary from None


class StdioError(RuntimeError):
    """Value-free pipe error; a partial write permanently retires output."""


class PipeChannel:
    """Nonblocking descriptors, one reader and one serialized frame writer."""

    def __init__(self, input_fd: int, output_fd: int, *, frame_timeout: float = 30.0) -> None:
        self.input_fd, self.output_fd = input_fd, output_fd
        self.frame_timeout = frame_timeout
        self._broken = False
        self._closed = False
        self._waiters: dict[bool, asyncio.Future[None]] = {}
        for fd in (input_fd, output_fd):
            os.set_inheritable(fd, False)
            os.set_blocking(fd, False)

    async def _ready(self, *, write: bool) -> None:
        if self._closed:
            raise StdioError("pipe_closed")
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[None] = loop.create_future()
        fd = self.output_fd if write else self.input_fd
        register = loop.add_writer if write else loop.add_reader
        remove = loop.remove_writer if write else loop.remove_reader
        def wake() -> None:
            if not ready.done():
                ready.set_result(None)
        self._waiters[write] = ready
        register(fd, wake)
        try:
            await ready
        finally:
            remove(fd)
            self._waiters.pop(write, None)

    async def read(self) -> bytes:
        while not self._closed:
            try:
                return os.read(self.input_fd, MAX_CHUNK_BYTES)
            except BlockingIOError:
                await self._ready(write=False)
            except OSError:
                raise StdioError("input_closed") from None
        raise StdioError("input_closed")

    async def write(self, frame: bytes) -> None:
        if self._broken or self._closed:
            raise StdioError("output_closed")
        try:
            async with asyncio.timeout(self.frame_timeout):
                remaining = memoryview(frame)
                while remaining:
                    try:
                        written = os.write(self.output_fd, remaining)
                        if written == 0:
                            raise StdioError("output_closed")
                        remaining = remaining[written:]
                    except BlockingIOError:
                        await self._ready(write=True)
        except TimeoutError:
            self._broken = True
            raise StdioError("output_timeout") from None
        except OSError:
            self._broken = True
            raise StdioError("output_closed") from None
        except BaseException:
            self._broken = True
            raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = self._broken = True
        for ready in self._waiters.values():
            if not ready.done():
                ready.set_exception(StdioError("pipe_closed"))
        for fd in (self.input_fd, self.output_fd):
            os.close(fd)


async def _read_requests(channel: PipeChannel, decoder: FrameDecoder) -> list[Request] | None:
    while True:
        chunk = await channel.read()
        if not chunk:
            decoder.finish()
            return None
        requests = decoder.feed(chunk)
        if requests:
            return requests


async def _cancel_join(task: asyncio.Task[Any] | None) -> None:
    if task is None:
        return
    if not task.done():
        task.cancel()
    await _joined(asyncio.create_task(_consume(task)))


async def _consume(task: asyncio.Task[Any]) -> None:
    await asyncio.gather(task, return_exceptions=True)


async def serve_context(
    context: CoreContext, channel: PipeChannel, *, decoder: FrameDecoder | None = None,
    initial: Sequence[Request] = (), interrupted: asyncio.Event | None = None,
    _on_bound: Callable[[], None] | None = None,
    selection: EditorSelection | None = None,
) -> int:
    """Join a single transport owner even when its caller is cancelled repeatedly."""
    try:
        return await _owned(_serve_context_owned(context, channel, decoder=decoder, initial=initial,
                            interrupted=interrupted, _on_bound=_on_bound, selection=selection))
    finally:
        if selection is not None:
            selection.close()


async def _serve_context_owned(
    context: CoreContext, channel: PipeChannel, *, decoder: FrameDecoder | None = None,
    initial: Sequence[Request] = (), interrupted: asyncio.Event | None = None,
    _on_bound: Callable[[], None] | None = None,
    selection: EditorSelection | None = None,
) -> int:
    """Observe delivery separately from the runtime's persisted result claim."""
    delivered: str | None = None
    delivery_failed = False
    input_error = False
    signal_stop = False
    async def emit(frame: bytes) -> None:
        nonlocal delivered, delivery_failed
        try:
            await channel.write(frame)
        except BaseException:
            delivery_failed = True
            raise
        # This records only fully written bytes, never grants run authority.
        value = json.loads(frame)
        if value["kind"] == "result":
            delivered = value["payload"]["status"]

    runtime = HeadlessRuntime(context, emit, close_resources=lambda: _close_context_clients(context),
                              before_bind=(lambda: selection.bind(context.tool_registry)) if selection is not None else None)
    if _on_bound is not None:
        _on_bound()
    decoder = decoder or FrameDecoder()
    reader: asyncio.Task[list[Request] | None] | None = None
    settlement = asyncio.create_task(runtime.wait_settled())
    drained: asyncio.Task[None] | None = None
    interrupt = asyncio.create_task(interrupted.wait()) if interrupted is not None else None
    try:
        for request in initial:
            runtime.receive(request)
        reader = asyncio.create_task(_read_requests(channel, decoder))
        while True:
            waiters = {task for task in (reader, drained or settlement, interrupt) if task is not None}
            done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if drained is not None and drained in done:
                await drained
                break
            if interrupt is not None and interrupt in done:
                signal_stop = True
                runtime.stop_input()
                await _cancel_join(reader)
                reader = None
                interrupt = None
            if reader is not None and reader in done:
                try:
                    requests = reader.result()
                    if requests is None:
                        # Loss of the input half is not proof the peer received
                        # or will receive a result. Preserve persisted evidence.
                        await runtime.aclose()
                        return 1
                    for request in requests:
                        runtime.receive(request)
                except ProtocolError as error:
                    input_error = True
                    runtime.stop_input(error)
                    reader = None
                except (StdioError, HeadlessRuntimeError):
                    await runtime.aclose()
                    return 1
                else:
                    reader = None if runtime.control.closing else asyncio.create_task(_read_requests(channel, decoder))
            if settlement in done and drained is None:
                drained = asyncio.create_task(runtime.wait())
        if delivery_failed:
            return 1
        if input_error:
            return 2
        if delivered is not None:
            return 0 if delivered == "completed" else 130 if delivered == "cancelled" else 1
        if runtime.failure is not None:
            return 2
        return 130 if signal_stop else 0 if runtime.control.closing else 1
    finally:
        await _cancel_join(reader)
        await _cancel_join(interrupt)
        await runtime.aclose()
        await _cancel_join(settlement)
        await _cancel_join(drained)


async def _release_context(context: CoreContext) -> None:
    try:
        await context.orchestrator.aclose()
    finally:
        try:
            if context.mcp_manager is not None:
                await context.mcp_manager.disconnect_all()
        finally:
            await _close_context_clients(context)


async def _close_clients(providers: Sequence[object]) -> None:
    """Close SDK clients of actual providers owned by this stdio construction."""
    from henchman.providers.anthropic import AnthropicProvider
    from henchman.providers.openai_compat import OpenAICompatibleProvider

    seen: set[int] = set()
    failure: BaseException | None = None
    for provider in providers:
        if not isinstance(provider, (OpenAICompatibleProvider, AnthropicProvider)):
            continue
        client = provider._client
        if id(client) in seen:
            continue
        seen.add(id(client))
        try:
            await client.close()
        except BaseException as error:
            failure = failure or error
    if failure is not None:
        raise failure


async def _close_context_clients(context: CoreContext) -> None:
    await _close_clients([context.provider, *(agent.provider for agent in context.orchestrator.pool._agents.values())])


class _StartupResources:
    """Track resources created before the runtime can own their cleanup."""

    def __init__(self) -> None:
        self.context: CoreContext | None = None
        self.provider: object | None = None
        self.closed = False
        self.failure: BaseException | None = None

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.context is not None:
                await _release_context(self.context)
            elif self.provider is not None:
                await _close_clients([self.provider])
        except BaseException as error:
            self.failure = error
            raise


async def _build_context(resources: _StartupResources) -> CoreContext:
    # Reuse settings/provider/instructions without constructing an interactive UI.
    from henchman.cli.app import _prepare_runtime_context

    try:
        prepared = _prepare_runtime_context(on_provider=lambda provider: setattr(resources, "provider", provider))
        context = create_core_context(prepared.provider, system_prompt=prepared.system_prompt,
            environment_context=prepared.env_block, settings=prepared.settings,
            instruction_snapshot=prepared.instruction_snapshot, settings_state=prepared.settings_state)
        resources.context = context
        if context.mcp_manager is not None:
            await context.mcp_manager.connect_all()
            context.mcp_manager.bind_registry(context.tool_registry)
        return context
    except BaseException as primary:
        try:
            await _joined(asyncio.create_task(resources.close()))
        except BaseException:
            primary.add_note("Headless startup resource cleanup also failed")
        raise


async def run_stdio(channel: PipeChannel, *, interrupted: asyncio.Event | None = None,
                    selection: EditorSelection | None = None) -> int:
    """Own startup until context transfer, including repeated caller cancellation."""
    try:
        return await _owned(_run_stdio_owned(channel, interrupted=interrupted, selection=selection))
    finally:
        if selection is not None:
            selection.close()


async def _run_stdio_owned(channel: PipeChannel, *, interrupted: asyncio.Event | None,
                           selection: EditorSelection | None = None) -> int:
    decoder = FrameDecoder()
    resources = _StartupResources()
    interrupt = asyncio.create_task(interrupted.wait()) if interrupted is not None else None
    reader: asyncio.Task[list[Request] | None] | None = asyncio.create_task(_read_requests(channel, decoder))
    startup: asyncio.Task[CoreContext] | None = None
    transferred = False

    async def drive() -> int:
        nonlocal reader, startup, transferred
        first_waiters: set[asyncio.Task[Any]] = {task for task in (reader, interrupt) if task is not None}
        done, _ = await asyncio.wait(first_waiters, return_when=asyncio.FIRST_COMPLETED)
        if interrupt is not None and interrupt in done:
            return 130
        assert reader is not None
        first = reader.result()
        reader = None
        if first is None:
            return 1
        # Match the shared control's pre-binding shutdown without creating a
        # session/provider just to close it. No other pipelined action is valid
        # before the initialization response establishes connection authority.
        if (len(first) in {1, 2} and first[-1].method == "shutdown"
            and first[-1].connection_id is None
            and (len(first) == 1 or (first[0].method == "initialize" and first[-1].id > first[0].id))):
            return 0
        if len(first) != 1 or first[0].method != "initialize":
            raise ProtocolError("not_initialized")
        startup = asyncio.create_task(_build_context(resources))
        reader = asyncio.create_task(_read_requests(channel, decoder))
        while True:
            waiters: set[asyncio.Task[Any]] = {task for task in (startup, reader, interrupt) if task is not None}
            done, _ = await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
            if interrupt is not None and interrupt in done:
                return 130
            if reader is not None and reader in done:
                more = reader.result()
                reader = None
                if more is None:
                    return 1
                if len(more) == 1 and more[0].method == "shutdown" and more[0].connection_id is None and more[0].id > first[0].id:
                    return 0
                raise ProtocolError("not_initialized")
            if startup in done:
                context = startup.result()
                resources.context = context
                await _cancel_join(reader)
                reader = None
                def bound() -> None:
                    nonlocal transferred
                    transferred = True
                return await serve_context(context, channel, decoder=decoder, initial=first, interrupted=interrupted,
                                           _on_bound=bound, selection=selection)

    code = 1
    try:
        try:
            code = await drive()
        except Exception as error:
            if transferred:
                code = 1
            else:
                # No runtime encoder has existed in this branch. Exit after it.
                error_code = error.code if isinstance(error, ProtocolError) else "startup_failed"
                try:
                    await channel.write(ServerEncoder().encode(kind="error", request_id=None,
                        session_id=None, run_id=None, payload={"code": error_code, "message": "Headless startup failed."}))
                    code = 2
                except (StdioError, OSError):
                    code = 1
    finally:
        await _cancel_join(reader)
        await _cancel_join(interrupt)
        if not transferred:
            await _cancel_join(startup)
            if startup is not None and not startup.cancelled():
                if startup.exception() is None:
                    resources.context = startup.result()
                else:
                    code = 1 if code in {0, 130} else code
            try:
                await _joined(asyncio.create_task(resources.close()))
            except BaseException:
                code = 1
            if resources.failure is not None:
                code = 1
    return code


async def _run_with_signals(channel: PipeChannel, *, selection: EditorSelection | None = None) -> int:
    interrupted = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in previous:
        loop.add_signal_handler(sig, interrupted.set)
    try:
        return await run_stdio(channel, interrupted=interrupted, selection=selection)
    finally:
        for sig, handler in previous.items():
            loop.remove_signal_handler(sig)
            signal.signal(sig, handler)


@click.command(name="headless", help="Run the opt-in v1 editor protocol over POSIX stdin/stdout pipes.")
@click.option("--protocol-version", required=True, type=click.Choice(["1"]))
@click.option("--project", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--editor-path", "editor_paths", multiple=True,
              help="Opt into the Neovim pilot's explicit saved-file selection; repeat for each file.")
def headless_command(protocol_version: str, project: Path, editor_paths: tuple[str, ...]) -> None:
    """Keep diagnostics on stderr and leave existing chat JSON modes unchanged."""
    del protocol_version
    try:
        pipes = protocol_pipes()
    except RuntimeError as error:
        raise click.UsageError(str(error)) from None
    os.chdir(project.resolve())
    selection = None
    if editor_paths:
        from henchman.integrations.neovim import EditorSelection

        try:
            selection = EditorSelection(Path.cwd(), editor_paths)
        except ValueError as error:
            raise click.UsageError(str(error)) from None
    # The bootstrap owns its originals; this layer owns only these duplicates.
    channel = PipeChannel(os.dup(pipes.input_fd), os.dup(pipes.output_fd))
    try:
        code = asyncio.run(_run_with_signals(channel, selection=selection))
    finally:
        channel.close()
    raise SystemExit(code)
