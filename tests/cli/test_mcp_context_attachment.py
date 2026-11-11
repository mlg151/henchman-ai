"""Explicit attachment consumes one reviewed preview without starting a model turn."""

import asyncio
import re
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.mcp import McpCommand
from henchman.cli.session_manager import ReplSessionManager
from henchman.config.schema import Settings
from henchman.core.agent import Agent
from henchman.core.session import SessionManager
from henchman.mcp.manager import McpManager
from henchman.providers.base import ModelProvider
from tests.mcp.context_fixture import context_peer


def runtime(tmp_path, manager, *, textual=False):
    provider = MagicMock(spec=ModelProvider)
    provider.default_model = "offline"
    provider.api_key = "preview_id"
    agent = Agent(provider)
    sessions = ReplSessionManager(SessionManager(tmp_path / "sessions"))
    session = sessions.session_manager.create_session("project")
    sessions.set_session(session)
    state = SimpleNamespace(agent=agent, provider=provider, settings=Settings(), mcp_manager=manager,
                            session_manager=sessions, is_processing=False)
    if textual:
        state.core_context = SimpleNamespace(agent=agent, session_manager=sessions, mcp_manager=manager)
    shown = StringIO()
    ctx = CommandContext(Console(file=shown, width=240), repl=state, agent=agent, session=session,
                         mcp_manager=manager)
    return state, ctx, shown


async def preview(ctx, shown):
    ctx.args = ["read", "source", "custom://fixture/readme"]
    await McpCommand().execute(ctx)
    match = re.search(r"/mcp attach ([a-f0-9]{32})", shown.getvalue())
    assert match, shown.getvalue()
    return match.group(1)


@pytest.mark.parametrize("textual", [False, True])
async def test_explicit_attachment_is_local_user_data_saved_once(tmp_path, textual):
    async with context_peer(tmp_path, "streamable_http") as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager, textual=textual)
        try:
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            before = len(peer.requests())
            # Own command worker is allowed; this is not a provider execution.
            state.current_agent_task = asyncio.current_task()
            state.is_processing = True
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert len(ctx.session.messages) == 1 and len(ctx.agent.messages) == 1
            message = ctx.agent.messages[-1]
            assert message.role == "user" and "Untrusted MCP context" in message.content
            assert message.context_attachments[0]["preview_id"] == identity
            restored = state.session_manager.session_manager.load(ctx.session.id)
            assert restored.messages[0].context_attachments == message.context_attachments
            await McpCommand().execute(ctx)
            assert len(ctx.session.messages) == 1 and len(peer.requests()) == before
            state.provider.chat_completion_stream.assert_not_called()
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("blocked", ["worker", "tool", "delegation", "goal", "session", "agent"])
async def test_active_or_changed_target_refuses_without_consuming(tmp_path, blocked):
    from henchman.core.goals import GoalService
    from henchman.providers.base import Message, ToolCall

    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        blocker = None
        try:
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            if blocked == "worker":
                blocker = asyncio.create_task(asyncio.Event().wait())
                state.current_agent_task = blocker
            elif blocked == "tool":
                state.agent.messages.append(Message("assistant", tool_calls=[ToolCall("call", "pending", {})]))
            elif blocked == "delegation":
                state.orchestrator = SimpleNamespace(subagents=SimpleNamespace(has_running_work=lambda: True))
            elif blocked == "goal":
                GoalService().start(ctx.session, "active")
            elif blocked == "session":
                state.session_manager.set_session(state.session_manager.session_manager.create_session("project"))
            else:
                state.agent = Agent(state.provider)
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert ctx.session.messages == []
            assert "attachment failed" in shown.getvalue().lower()
            state.provider.chat_completion_stream.assert_not_called()
        finally:
            if blocker:
                blocker.cancel()
                await asyncio.gather(blocker, return_exceptions=True)
            await manager.disconnect_all()


async def test_session_switch_during_retrieval_does_not_bind_new_session(tmp_path):
    async with context_peer(tmp_path) as peer:
        peer.state["delays"]["resources/read"] = .1
        peer.publish()
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        try:
            await manager.connect_server("source")
            ctx.args = ["read", "source", "custom://fixture/readme"]
            request = asyncio.create_task(McpCommand().execute(ctx))
            async with asyncio.timeout(3):
                while not any(item["method"] == "resources/read" for item in peer.requests()):
                    await asyncio.sleep(.005)
            current = state.session_manager.session_manager.create_session("project")
            state.session_manager.set_session(current)
            await request
            assert "/mcp attach" not in shown.getvalue()
            assert current.messages == ctx.session.messages == []
            identity, = manager._context_previews
            with pytest.raises(ValueError):
                manager.commit_context_preview(identity, current, state.agent, lambda _value: pytest.fail("wrong binding"))
        finally:
            await manager.disconnect_all()


async def test_external_session_save_conflict_does_not_attach_or_consume_handle(tmp_path):
    from henchman.core.session import SessionMessage

    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        try:
            state.session_manager.session_manager.save(ctx.session)
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            other = SessionManager(tmp_path / "sessions")
            changed = other.load(ctx.session.id)
            changed.messages.append(SessionMessage("user", "other writer"))
            other.save(changed)
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert ctx.session.messages == ctx.agent.messages == []
            assert identity in manager._context_previews
            assert other.load(ctx.session.id).messages[0].content == "other writer"
            assert "changed on disk" in shown.getvalue()
        finally:
            await manager.disconnect_all()


async def test_postcommit_acknowledgment_loss_cannot_duplicate_attachment(tmp_path, monkeypatch):
    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        core = state.session_manager.session_manager
        original = core.save
        try:
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            def committed_without_ack(candidate):
                original(candidate)
                raise OSError("acknowledgment lost")
            monkeypatch.setattr(core, "save", committed_without_ack)
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert ctx.session.messages == ctx.agent.messages == []
            assert len(core.load(ctx.session.id).messages) == 1
            monkeypatch.setattr(core, "save", original)
            await McpCommand().execute(ctx)
            assert len(core.load(ctx.session.id).messages) == 1
            assert ctx.session.messages == ctx.agent.messages == []
            assert "changed on disk" in shown.getvalue()
            assert sum(item["method"] == "resources/read" for item in peer.requests()) == 1
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("condition", ["active", "blocked", "failure"])
async def test_workflow_recovery_blocks_attachment_without_recovery_side_effects(tmp_path, condition):
    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        controller = MagicMock()
        controller.has_active_dispatch.return_value = condition == "active"
        controller.report.return_value = SimpleNamespace(blocking_input_ids=("old",) if condition == "blocked" else (),
                                                       failure_reason="missing" if condition == "failure" else None)
        try:
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            ctx.session._workflow_runtime = controller
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert ctx.session.messages == [] and identity in manager._context_previews
            controller.attach.assert_not_called()
            controller.begin.assert_not_called()
            assert "Resolve workflow recovery" in shown.getvalue()
        finally:
            await manager.disconnect_all()


@pytest.mark.parametrize("operation_state", ["started", "outcome_unknown", "uninitialized_store"])
async def test_specialist_operation_uncertainty_blocks_without_implicit_recovery(tmp_path, monkeypatch, operation_state):
    from henchman.ops.operation_store import OperationStore

    async with context_peer(tmp_path) as peer:
        manager = McpManager({"source": peer.config})
        state, ctx, shown = runtime(tmp_path, manager)
        journal = SimpleNamespace(report=MagicMock(return_value=SimpleNamespace(
            records=(SimpleNamespace(state=operation_state, resolution=None),))), recover=MagicMock())
        key = (ctx.session.project_hash, ctx.session.id)
        operations = SimpleNamespace(_inflight={}, path=None, _active={key: (ctx.session, journal)})
        state.orchestrator = SimpleNamespace(operation_runtime=operations)
        if operation_state == "uninitialized_store":
            operations.path = tmp_path / "unopened.sqlite"
            operations._active.clear()
            monkeypatch.setattr(OperationStore, "existing_reference", lambda *_args: object())
        try:
            await manager.connect_server("source")
            identity = await preview(ctx, shown)
            ctx.args = ["attach", identity]
            await McpCommand().execute(ctx)
            assert ctx.session.messages == [] and identity in manager._context_previews
            assert "operation recovery" in shown.getvalue().lower()
            journal.recover.assert_not_called()
            assert not (tmp_path / "unopened.sqlite").exists()
        finally:
            await manager.disconnect_all()
