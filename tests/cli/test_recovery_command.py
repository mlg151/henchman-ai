"""Recovery authority is exercised only by explicit user commands."""

from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.recovery import RecoveryCommand
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.runtime_operations import use_operation_call
from tests.core.test_session_operations import setup


def context(session, runtime, registry, args):
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=140)
    ctx = CommandContext(console=console, args=args, session=session, tool_registry=registry,
                         repl=SimpleNamespace(orchestrator=SimpleNamespace(operation_runtime=runtime)))
    return ctx, output


async def unknown(tmp_path):
    session, call, saved, runtime, registry, tool = setup(tmp_path)
    tool.failure = ConnectionError("effect occurred before response loss")
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(OperationRecoveryError):
        await registry.execute(call.name, call.arguments)
    record = runtime.report().records[0]
    return session, call, saved, runtime, registry, tool, record


async def test_empty_status_does_not_create_a_durable_store(tmp_path):
    session, _, _, runtime, registry, _ = setup(tmp_path)
    ctx, output = context(session, runtime, registry, [])
    await RecoveryCommand().execute(ctx)
    assert "No operation history" in output.getvalue()
    assert not (tmp_path / "ops.db").exists()


async def test_status_shows_stable_id_revision_and_unknown_without_arguments(tmp_path):
    session, _, _, runtime, registry, _, record = await unknown(tmp_path)
    ctx, output = context(session, runtime, registry, ["status"])
    await RecoveryCommand().execute(ctx)
    text = output.getvalue()
    assert record.operation_id in text and str(record.revision) in text and "outcome_unknown" in text
    assert "original" not in text


async def test_explicit_abandon_retains_uncertainty_and_unblocks_intact_transcript(tmp_path):
    session, _, _, runtime, registry, _, record = await unknown(tmp_path)
    ctx, output = context(session, runtime, registry, ["abandon", record.operation_id, str(record.revision), "I inspected external state"])
    await RecoveryCommand().execute(ctx)
    resolved = runtime.report().records[0]
    assert resolved.state == "outcome_unknown" and resolved.resolution == "abandoned"
    runtime.begin()
    assert "outcome remains unknown" in session.messages[-1].content
    assert "abandoned" in output.getvalue()


async def test_stale_user_revision_cannot_resolve_a_changed_attempt(tmp_path):
    session, _, _, runtime, registry, _, record = await unknown(tmp_path)
    ctx, output = context(session, runtime, registry, ["abandon", record.operation_id, str(record.revision - 1), "stale action"])
    await RecoveryCommand().execute(ctx)
    assert runtime.report().records[0].resolution is None
    assert "stale_revision" in output.getvalue()


async def test_retry_uses_one_new_attempt_and_current_approval(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    tool.failure = None
    approvals = []
    async def approve_again(_request):
        approvals.append(True)
        return True
    registry.clear_grants()
    registry.set_confirmation_handler(approve_again)
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert tool.calls == ["original", "original"] and approvals == [True]
    records = runtime.report().records
    assert len(records) == 2 and records[1].retry_of == record.operation_id
    assert records[0].state == "outcome_unknown" and records[1].state == "completed"
    runtime.begin()
    assert session.messages[-1].content == "effect observed"
    await RecoveryCommand().execute(ctx)
    assert tool.calls == ["original", "original"]


async def test_retry_denied_by_current_policy_creates_no_new_attempt(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    registry.clear_grants()
    async def deny(_request):
        return False
    registry.set_confirmation_handler(deny)
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert len(runtime.report().records) == 1 and tool.calls == ["original"]
    assert "denied" in output.getvalue().lower()


async def test_redacted_saved_arguments_are_not_replayed_as_real_inputs(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    session.messages[0].tool_calls[0]["arguments"]["value"] = "[REDACTED]"
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert "saved_retry_input_unavailable" in output.getvalue()
    assert tool.calls == ["original"] and len(runtime.report().records) == 1


async def test_retry_saves_exact_approved_request_despite_mutation_during_confirmation(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    tool.failure = None
    registry.clear_grants()
    async def approve_changed(_request):
        session.messages[0].tool_calls[0]["arguments"]["value"] = "changed while awaiting"
        return True
    registry.set_confirmation_handler(approve_changed)
    ctx, _ = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert tool.calls == ["original", "original"]
    assert session.messages[0].tool_calls[0]["arguments"] == {"value": "original"}


async def test_resolution_during_retry_approval_prevents_new_attempt(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    registry.clear_grants()
    async def approve_stale(_request):
        runtime.resolve_user(record.operation_id, record.revision, decision="abandon", note="User inspected state")
        return True
    registry.set_confirmation_handler(approve_stale)
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert "stale_revision" in output.getvalue()
    assert len(runtime.report().records) == 1 and tool.calls == ["original"]


async def test_retry_save_failure_preserves_queued_authority_without_dispatch(tmp_path):
    session, _, _, runtime, registry, tool, record = await unknown(tmp_path)
    original = session.to_dict()
    def fail_save(_session):
        raise OSError("disk full")
    runtime.save = fail_save
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert "session_save_failed" in output.getvalue()
    assert tool.calls == ["original"]
    assert session.to_dict() == original
    assert runtime.report().records[-1].state == "queued"
    with pytest.raises(OperationRecoveryError, match="transcript_behind_journal"):
        runtime.begin()


async def test_status_redacts_before_cut_and_renders_names_as_literal_text(tmp_path):
    from dataclasses import replace

    from henchman.core.operation_recovery import OperationResult, RecoveryReport
    session, _, _, runtime, registry, _, record = await unknown(tmp_path)
    secret = "display-secret-crossing-preview-boundary"
    session.evidence_redactor.register_secret(secret)
    session.evidence_redactor.register_secret(record.operation_id)
    rendered = replace(record, state="completed", tool_name="[bold]effect[/bold]", context=replace(record.context, agent_id=secret),
                       result=OperationResult("x" * 495 + secret + "y" * 30, True))
    runtime.recovery_report = lambda: RecoveryReport((rendered,), ())
    ctx, output = context(session, runtime, registry, ["status"])
    await RecoveryCommand().execute(ctx)
    text = output.getvalue()
    assert secret not in text and "displ" not in text
    assert record.operation_id not in text
    assert "[bold]effect[/bold]" in text
    assert "[preview truncated]" in text


async def test_orchestration_only_retry_refuses_before_consuming_authority(tmp_path):
    from dataclasses import asdict

    from henchman.core.session_models import SessionMessage
    from henchman.providers.base import ToolCall
    from henchman.tools.builtins.delegate import DelegateTaskTool
    session, _, _, runtime, registry, _ = setup(tmp_path)
    call = ToolCall("delegation", "delegate_task", {"agent": "engineer", "task": "perform task"})
    session.messages = [SessionMessage("assistant", tool_calls=[asdict(call)])]
    registry.register(DelegateTaskTool())
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    invocation.prepare(call.name, call.arguments, "effectful")
    assert invocation.start() is not None
    invocation.cancel()
    record = runtime.report().records[0]
    ctx, output = context(session, runtime, registry, ["retry", record.operation_id, str(record.revision)])
    await RecoveryCommand().execute(ctx)
    assert "resolve or abandon" in output.getvalue()
    assert "new task" in output.getvalue()
    assert runtime.report().records == (record,)
