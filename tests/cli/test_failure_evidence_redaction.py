"""Exception display and formatted logs preserve diagnostics without credentials."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from henchman.cli.output_handler import OutputHandler
from henchman.cli.repl import Repl
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager
from henchman.providers.base import ToolCall


@pytest.fixture
def runtime(tmp_path: Path) -> SimpleNamespace:
    transcript = StringIO()
    renderer = UIRenderer(console=Console(file=transcript, width=1000, highlight=False))
    provider = SimpleNamespace(api_key="configured-canary")
    sessions = ReplSessionManager(
        SessionManager(data_dir=tmp_path / "sessions"), auto_save=False, provider=provider,
    )
    sessions.set_session(sessions.create_session("project"))
    sessions.session_manager.evidence_redactor.register_secret("chain-canary")
    output = OutputHandler(renderer, MagicMock(), sessions, provider)
    output.show_turn_status = MagicMock()
    agent = MagicMock()
    agent.identity.id = "leader"
    agent.unlimited_mode = True
    agent.messages = []
    executor = ToolExecutor(output, MagicMock(), provider)
    repl = Repl.__new__(Repl)
    repl.renderer = renderer
    repl.provider = provider
    repl.settings = None
    repl.session_manager = sessions
    repl.tool_executor = executor
    repl._interactive_loop_active = True
    repl._turn_worker = None
    repl._pending_inputs = deque()
    repl._pause_goal = MagicMock()
    return SimpleNamespace(
        output=output, agent=agent, executor=executor, repl=repl,
        transcript=transcript, sessions=sessions,
    )


async def _raise_chained() -> None:
    local_only = "unregistered-local-canary"
    try:
        raise ValueError("chain-canary")
    except ValueError as cause:
        assert local_only
        raise RuntimeError("configured-canary") from cause


async def _empty_stream() -> AsyncIterator[AgentEvent]:
    if False:
        yield AgentEvent(EventType.FINISHED, "stop")


def _assert_safe_logs(caplog: pytest.LogCaptureFixture, *diagnostics: str) -> str:
    assert caplog.records
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    rendered = "\n".join(formatter.format(record) for record in caplog.records)
    for secret in ("configured-canary", "chain-canary", "unregistered-local-canary"):
        assert secret not in rendered
    assert "[REDACTED]" in rendered
    assert all(record.exc_info is None for record in caplog.records)
    for diagnostic in diagnostics:
        assert diagnostic in rendered
    return rendered


async def test_mcp_connection_error_is_redacted_without_mutating_exception(runtime: SimpleNamespace) -> None:
    error = RuntimeError("connect configured-canary")
    runtime.repl.mcp_manager = SimpleNamespace(clients={}, connect_all=AsyncMock(side_effect=error))

    await runtime.repl.initialize_mcp()

    assert "configured-canary" not in runtime.transcript.getvalue()
    assert "Failed to connect to MCP servers: RuntimeError: connect [REDACTED]" in runtime.transcript.getvalue()
    assert str(error) == "connect configured-canary"


async def test_turn_worker_error_redacts_rendering_and_formatted_traceback(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    task = asyncio.create_task(_raise_chained())
    runtime.repl._turn_worker = task
    with pytest.raises(RuntimeError) as raised:
        await task

    runtime.repl._turn_worker_finished(task)

    _assert_safe_logs(caplog, "Interactive turn failed", "RuntimeError", "ValueError", "_raise_chained", "direct cause")
    assert "configured-canary" not in runtime.transcript.getvalue()
    assert "RuntimeError: [REDACTED]" in runtime.transcript.getvalue()
    assert task.exception() is raised.value
    assert str(raised.value) == "configured-canary"
    assert runtime.repl._turn_worker is None
    runtime.repl._pause_goal.assert_called_once_with()


async def test_agent_error_redacts_rendering_and_logs_preserving_diagnostic_chain(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    async def failing_process(*_args: object) -> None:
        await _raise_chained()

    runtime.executor.process_agent_stream = failing_process
    await runtime.repl._run_agent_with_monitor(_empty_stream(), runtime.agent, [], None)

    _assert_safe_logs(caplog, "Agent execution failed", "RuntimeError", "ValueError", "failing_process", "direct cause")
    assert "configured-canary" not in runtime.transcript.getvalue()
    assert "RuntimeError: [REDACTED]" in runtime.transcript.getvalue()
    runtime.repl._pause_goal.assert_called_once_with()
    assert runtime.repl.current_monitor is None


async def test_legacy_event_error_redacts_structured_credentials_and_preserves_content(runtime: SimpleNamespace) -> None:
    data = {"password": "event-only-canary", "message": "echo event-only-canary configured-canary"}
    await runtime.repl._handle_agent_event(AgentEvent(EventType.ERROR, data))
    collector: list[str] = []
    await runtime.repl._handle_agent_event(AgentEvent(EventType.CONTENT, "configured-canary"), collector)

    assert "event-only-canary" not in runtime.transcript.getvalue()
    assert "configured-canary" not in runtime.transcript.getvalue()
    assert "[REDACTED]" in runtime.transcript.getvalue()
    assert data["password"] == "event-only-canary"
    assert collector == ["configured-canary"]


@pytest.mark.parametrize("nested", [False, True])
async def test_legacy_event_redacts_exception_objects_before_rendering(runtime: SimpleNamespace, nested: bool) -> None:
    error = RuntimeError("configured-canary")
    data = {"detail": error} if nested else error

    await runtime.repl._handle_agent_event(AgentEvent(EventType.ERROR, data))

    assert "configured-canary" not in runtime.transcript.getvalue()
    assert "[REDACTED]" in runtime.transcript.getvalue()
    assert str(error) == "configured-canary"


async def test_background_error_logs_safe_traceback_and_task_retains_original_error(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    task = runtime.output._safe_create_task(_raise_chained())
    with pytest.raises(RuntimeError) as raised:
        await task
    await asyncio.sleep(0)

    _assert_safe_logs(caplog, "Background task failed", "RuntimeError", "ValueError", "_raise_chained", "direct cause")
    assert task.exception() is raised.value
    assert str(raised.value) == "configured-canary"


async def test_cancelled_background_task_and_turn_worker_do_not_log_failure(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    task = runtime.output._safe_create_task(asyncio.Event().wait())
    runtime.repl._turn_worker = task
    task.cancel("configured-canary")
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    runtime.repl._turn_worker_finished(task)

    assert not caplog.records
    assert not runtime.transcript.getvalue()
    runtime.repl._pause_goal.assert_not_called()
    assert runtime.repl._turn_worker is None


async def test_parallel_failure_logs_safe_names_and_base_exception_traceback(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    call = ToolCall("configured-canary", "configured-canary", {})
    runtime.executor._split_tools_by_confirmation_requirement = MagicMock(return_value=([call], []))
    original = GeneratorExit("chain-canary configured-canary")

    async def failed_tool(*_args: object, **_kwargs: object) -> None:
        raise original

    runtime.executor._execute_and_record_tool_call = failed_tool
    runtime.agent.continue_with_tool_results = _empty_stream
    await runtime.executor.execute_tool_calls([call], runtime.agent)

    _assert_safe_logs(caplog, "Parallel tool call [REDACTED] ([REDACTED]) failed", "GeneratorExit", "failed_tool")
    runtime.agent.submit_tool_result.assert_called_once()
    assert runtime.agent.submit_tool_result.call_args.args[0] == "configured-canary"
    assert str(original) == "chain-canary configured-canary"


@pytest.mark.parametrize("primary_type", [RuntimeError, asyncio.CancelledError])
async def test_interrupted_stream_cleanup_logs_safely_and_preserves_primary_error(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture, primary_type: type[BaseException],
) -> None:
    primary = primary_type("configured-canary")
    cleanup = RuntimeError("chain-canary")

    class FailingStream:
        def __aiter__(self) -> FailingStream:
            return self

        async def __anext__(self) -> AgentEvent:
            raise primary

        async def aclose(self) -> None:
            raise cleanup

    with pytest.raises(primary_type) as raised:
        await runtime.executor.process_agent_stream(FailingStream(), runtime.agent)

    _assert_safe_logs(caplog, "Agent stream cleanup failed after interruption", "RuntimeError", "aclose", primary_type.__name__)
    assert raised.value is primary
    assert str(cleanup) == "chain-canary"


async def test_uninterrupted_stream_cleanup_failure_still_propagates(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    cleanup = RuntimeError("configured-canary")

    class FailingClose:
        def __aiter__(self) -> FailingClose:
            return self

        async def __anext__(self) -> AgentEvent:
            raise StopAsyncIteration

        async def aclose(self) -> None:
            raise cleanup

    with pytest.raises(RuntimeError) as raised:
        await runtime.executor.process_agent_stream(FailingClose(), runtime.agent)

    assert raised.value is cleanup
    assert not caplog.records


async def test_monitored_agent_cancellation_propagates_without_failure_output(
    runtime: SimpleNamespace, caplog: pytest.LogCaptureFixture,
) -> None:
    cancellation = asyncio.CancelledError("configured-canary")
    runtime.executor.process_agent_stream = AsyncMock(side_effect=cancellation)

    with pytest.raises(asyncio.CancelledError) as raised:
        await runtime.repl._run_agent_with_monitor(_empty_stream(), runtime.agent, [], None)

    assert raised.value is cancellation
    assert not caplog.records
    assert "configured-canary" not in runtime.transcript.getvalue()
    assert runtime.repl.current_monitor is None
