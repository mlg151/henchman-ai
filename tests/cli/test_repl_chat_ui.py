"""Regression tests for the prompt-toolkit chat turn presentation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.events import AgentEvent, EventType


class _RecordingRenderer:
    """Record the user-visible lifecycle of a chat turn."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str | None]] = []

    def start_thinking(self, detail: str | None = None) -> None:
        self.events.append(("thinking-started", detail))

    def stop_thinking(self) -> None:
        self.events.append(("thinking-stopped", None))

    def info(self, message: str) -> None:
        self.events.append(("permanent-info", message))

    def warning(self, message: str) -> None:
        self.events.append(("warning", message))

    def error(self, message: str) -> None:
        self.events.append(("error", message))


def _empty_stream() -> AsyncIterator[Any]:
    async def stream() -> AsyncIterator[Any]:
        return
        yield  # pragma: no cover

    return stream()


@pytest.mark.anyio
async def test_chat_turn_uses_transient_status_until_first_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal turn must not leave mode or token metadata in the transcript."""
    import henchman.cli.repl as repl_module

    renderer = _RecordingRenderer()
    repl = Repl.__new__(Repl)
    repl.renderer = renderer
    repl.tool_executor = SimpleNamespace()
    repl.running = True

    async def event_stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.AGENT_STARTED, {"agent": "tech_lead"})
        yield AgentEvent(EventType.CONTENT, "Hello")

    async def run_monitored_task(
        stream: AsyncIterator[AgentEvent],
        *_args: object,
    ) -> tuple[bool, bool]:
        assert renderer.events == [("thinking-started", None)]
        async for event in stream:
            if event.type == EventType.AGENT_STARTED:
                renderer.events.append(("non-visible-event", None))
                assert renderer.events == [
                    ("thinking-started", None),
                    ("non-visible-event", None),
                ]
            else:
                renderer.events.append(("response-activity", None))
        return False, False

    async def cleanup_monitor(*_args: object) -> None:
        return None

    monkeypatch.setattr(repl_module, "_run_monitored_task", run_monitored_task)
    monkeypatch.setattr(repl_module, "_cleanup_monitor", cleanup_monitor)
    monkeypatch.setattr(
        "henchman.cli.input.KeyMonitor",
        lambda: SimpleNamespace(monitor=lambda: _idle_monitor()),
    )

    await repl._run_agent_with_monitor(event_stream(), object(), [], None)

    assert renderer.events == [
        ("thinking-started", None),
        ("non-visible-event", None),
        ("thinking-stopped", None),
        ("response-activity", None),
    ]


async def _idle_monitor() -> None:
    """Provide a monitor coroutine whose lifecycle is controlled by the test."""
    return None


@pytest.mark.anyio
async def test_chat_turn_clears_transient_status_when_execution_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure before the first event must still remove the spinner."""
    import henchman.cli.repl as repl_module

    renderer = _RecordingRenderer()
    repl = Repl.__new__(Repl)
    repl.renderer = renderer
    repl.tool_executor = SimpleNamespace()
    repl.running = True

    async def fail_before_activity(*_args: object) -> tuple[bool, bool]:
        raise RuntimeError("provider unavailable")

    async def cleanup_monitor(*_args: object) -> None:
        return None

    monkeypatch.setattr(repl_module, "_run_monitored_task", fail_before_activity)
    monkeypatch.setattr(repl_module, "_cleanup_monitor", cleanup_monitor)
    monkeypatch.setattr(
        "henchman.cli.input.KeyMonitor",
        lambda: SimpleNamespace(monitor=lambda: _idle_monitor()),
    )

    await repl._run_agent_with_monitor(_empty_stream(), object(), [], None)

    assert renderer.events == [
        ("thinking-started", None),
        ("thinking-stopped", None),
        ("error", "Error: provider unavailable"),
    ]


@pytest.mark.parametrize(
    ("monitor_result", "warning", "remains_running"),
    [
        ((True, False), "\n[Exit requested by Ctrl+C]", False),
        ((False, True), "\n[Interrupted by Esc]", True),
    ],
)
@pytest.mark.anyio
async def test_interruption_clears_status_before_warning(
    monkeypatch: pytest.MonkeyPatch,
    monitor_result: tuple[bool, bool],
    warning: str,
    remains_running: bool,
) -> None:
    """Exit and stop requests must clear transient UI before reporting."""
    import henchman.cli.repl as repl_module

    renderer = _RecordingRenderer()
    repl = Repl.__new__(Repl)
    repl.renderer = renderer
    repl.tool_executor = SimpleNamespace()
    repl.running = True

    async def interrupted(*_args: object) -> tuple[bool, bool]:
        return monitor_result

    async def cleanup_monitor(*_args: object) -> None:
        return None

    monkeypatch.setattr(repl_module, "_run_monitored_task", interrupted)
    monkeypatch.setattr(repl_module, "_cleanup_monitor", cleanup_monitor)
    monkeypatch.setattr(
        "henchman.cli.input.KeyMonitor",
        lambda: SimpleNamespace(monitor=lambda: _idle_monitor()),
    )

    await repl._run_agent_with_monitor(_empty_stream(), object(), [], None)

    assert renderer.events == [
        ("thinking-started", None),
        ("thinking-stopped", None),
        ("warning", warning),
    ]
    assert repl.running is remains_running


@pytest.mark.anyio
async def test_normal_chat_turn_does_not_build_a_persistent_status_line() -> None:
    """Chat startup must leave mode and token metadata to the bottom toolbar."""
    repl = Repl.__new__(Repl)
    repl.agent = SimpleNamespace(_turn_number=0)
    repl.config = ReplConfig()
    repl.session_manager = ReplSessionManager(auto_save=False)

    class _Orchestrator:
        def run(self, _message: str) -> AsyncIterator[Any]:
            return _empty_stream()

    class _ObsoleteStatusBuilder:
        def get_rich_status_message(self, _agent: object) -> str:
            raise AssertionError("persistent chat status must not be built")

    repl.orchestrator = _Orchestrator()
    repl.output_handler = _ObsoleteStatusBuilder()
    captured: list[str | None] = []

    async def run_with_monitor(
        _stream: AsyncIterator[Any],
        _agent: object,
        _content: list[str],
        detail: str | None,
    ) -> None:
        captured.append(detail)

    repl._run_agent_with_monitor = run_with_monitor  # type: ignore[method-assign]

    await repl._run_agent("hello")

    assert captured == [None]


@pytest.mark.anyio
async def test_direct_agent_turn_uses_plain_role_as_transient_detail() -> None:
    """Direct turns must not pass Rich markup into the status lifecycle."""
    repl = Repl.__new__(Repl)
    direct_agent = SimpleNamespace(_turn_number=0)
    repl.session_manager = ReplSessionManager(auto_save=False)
    repl.orchestrator = SimpleNamespace(
        run_direct=lambda _role, _message: _empty_stream(),
        pool=SimpleNamespace(get_agent=lambda _role: direct_agent),
    )
    captured: list[str | None] = []

    async def run_with_monitor(
        _stream: AsyncIterator[Any],
        _agent: object,
        _content: list[str],
        detail: str | None,
    ) -> None:
        captured.append(detail)

    repl._run_agent_with_monitor = run_with_monitor  # type: ignore[method-assign]

    await repl._run_agent_direct("explorer", "inspect this")

    assert captured == ["@explorer"]
