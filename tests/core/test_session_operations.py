"""Durable journal authority survives missing or rolled-back transcript references."""

import asyncio
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from henchman.config.schema import Settings
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.runtime_operations import use_operation_call
from henchman.core.session_data import Session, session_from_dict
from henchman.core.session_models import SessionMessage
from henchman.core.session_operations import SessionRunOperations
from henchman.providers.base import ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class EffectTool(Tool):
    name = "effect"
    description = "Count an effect"
    parameters = {"type": "object", "properties": {"value": {"type": "string"}}}
    kind = ToolKind.EXECUTE

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failure: BaseException | None = None

    async def execute(self, **params: object) -> ToolResult:
        self.calls.append(str(params["value"]))
        if self.failure is not None:
            raise self.failure
        return ToolResult("effect observed")


def setup(tmp_path: Path, *, durable: bool = True, session: Session | None = None):
    session = session or Session("session", "project", "today", "today")
    call = ToolCall("call", "effect", {"value": "original"})
    if not session.messages:
        session.messages.append(SessionMessage("assistant", tool_calls=[asdict(call)]))
    saved = []
    settings = Settings.model_validate({"operations": {"persistence": "durable" if durable else "process"}})
    runtime = SessionRunOperations(settings, lambda: session, lambda current: saved.append(current.to_dict()), tmp_path / "ops.db")
    registry = ToolRegistry()
    tool = EffectTool()
    registry.register(tool)
    registry.set_confirmation_handler(lambda _request: approve())
    return session, call, saved, runtime, registry, tool


async def approve() -> bool:
    return True


async def test_completed_result_reconciles_after_restart_without_repeating_effect(tmp_path: Path) -> None:
    session, call, saved, runtime, registry, tool = setup(tmp_path)
    run = runtime.begin()
    invocation = run.bind_call(call, agent_id="tech_lead", assistant_index=0)
    with use_operation_call(invocation):
        result = await registry.execute(call.name, call.arguments)
    assert result.content == "effect observed" and tool.calls == ["original"]
    # Intent/correlation is saved before dispatch; completion is authoritative in
    # the journal even when the process exits before saving a tool result.
    restored_session = session_from_dict(saved[-1])
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    resumed = restored.begin()
    assert restored_session.messages[-1].role == "tool"
    assert restored_session.messages[-1].tool_call_id == "call"
    assert restored_session.messages[-1].content == "effect observed"
    with use_operation_call(resumed.bind_call(call, agent_id="tech_lead", assistant_index=0)):
        replay = await registry.execute(call.name, call.arguments)
    assert replay.content == "effect observed" and tool.calls == ["original"]
    assert len(restored_session.operations.observed_ids) == 1


async def test_recovery_registers_current_actor_key_before_saving_reconciled_evidence(tmp_path, monkeypatch):
    from types import SimpleNamespace

    secret = "recovered-actor-credential-canary"
    session, call, saved, runtime, registry, tool = setup(tmp_path)

    async def result(**_params):
        return ToolResult(secret)

    monkeypatch.setattr(tool, "execute", result)
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    with use_operation_call(invocation):
        await registry.execute(call.name, call.arguments)
    restored_session = session_from_dict(saved[-1])
    _, _, recovered_saves, restored, _, _ = setup(tmp_path, session=restored_session)
    actor = SimpleNamespace(provider=SimpleNamespace(api_key=secret))
    restored.begin(agent=actor)
    assert recovered_saves
    assert secret not in str(recovered_saves)
    assert recovered_saves[-1]["messages"][-1]["content"] == "[REDACTED]"


@pytest.mark.parametrize("downgrade", [False, True])
async def test_backup_without_reference_cannot_hide_completed_effect(tmp_path: Path, downgrade: bool) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    backup = deepcopy(session)
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        await registry.execute(call.name, call.arguments)
    _, _, _, restored, _, _ = setup(tmp_path, durable=not downgrade, session=backup)
    with pytest.raises(OperationRecoveryError, match="transcript_behind_journal"):
        restored.begin()
    assert tool.calls == ["original"] and backup.operations is None


async def test_unknown_effect_blocks_resume_and_is_not_wrapped_as_tool_failure(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    tool.failure = RuntimeError("connection ended after effect")
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(OperationRecoveryError, match="outcome_unknown"):
        await registry.execute(call.name, call.arguments)
    restored_session = session_from_dict(session.to_dict())
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
        restored.begin()
    assert tool.calls == ["original"]


async def test_failed_intent_save_prevents_dispatch_and_leaves_authority(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    run = runtime.begin()
    def fail(_session: Session) -> None:
        raise OSError("disk unavailable")
    runtime.save = fail
    with use_operation_call(run.bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(OperationRecoveryError, match="session_save_failed"):
        await registry.execute(call.name, call.arguments)
    assert not tool.calls
    assert runtime.report().records[0].state == "queued"


async def test_current_approval_denial_creates_no_attempt(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    async def deny(_request: object) -> bool:
        return False
    registry.set_confirmation_handler(deny)
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        result = await registry.execute(call.name, call.arguments)
    assert not result.success and not tool.calls
    assert runtime.report().records == ()


async def test_session_operation_identities_survive_short_credential_redaction(tmp_path: Path) -> None:
    session, call, _, runtime, registry, _ = setup(tmp_path)
    session.evidence_redactor.register_secret("call")
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        await registry.execute(call.name, call.arguments)
    restored = session_from_dict(session.to_dict())
    assert restored.operations.bindings[0].context.tool_call_id == "call"
    assert restored.operations.reference.session_id == "session"


async def test_cached_result_does_not_repeat_formatter_mutations(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    class Formatter:
        mutations = 0
        async def run(self, _tool, _params, execute):
            result = await execute()
            self.mutations += 1
            return result
    formatter = Formatter()
    registry._formatter = formatter
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    for _ in range(2):
        with use_operation_call(invocation):
            await registry.execute(call.name, call.arguments)
    assert tool.calls == ["original"]
    assert formatter.mutations == 1


async def test_network_failure_has_one_attempt_and_cancellation_remains_unknown(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    tool.kind = ToolKind.NETWORK
    tool.failure = ConnectionError("after request dispatch")
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(OperationRecoveryError):
        await registry.execute(call.name, call.arguments)
    assert tool.calls == ["original"]
    assert runtime.report().records[0].state == "outcome_unknown"


async def test_cancelled_dispatch_preserves_cancellation_and_unknown_record(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    tool.failure = asyncio.CancelledError()
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(asyncio.CancelledError):
        await registry.execute(call.name, call.arguments)
    assert runtime.report().records[0].state == "outcome_unknown"


async def test_model_budget_control_preserved_after_nested_tool_dispatch(tmp_path: Path) -> None:
    from henchman.core.run_budget import BudgetExceeded
    _, call, _, runtime, registry, tool = setup(tmp_path)
    tool.failure = BudgetExceeded("request_limit")
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(BudgetExceeded):
        await registry.execute(call.name, call.arguments)
    assert runtime.report().records[0].state == "outcome_unknown"


async def test_secret_straddling_output_cap_is_redacted_before_persistence(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    secret = "boundary-secret-credential-which-must-never-be-split"
    session.evidence_redactor.register_secret(secret)
    async def output(**_params):
        return ToolResult("a" * 49995 + secret + "x" * 20000)
    tool.execute = output
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        result = await registry.execute(call.name, call.arguments)
    record = runtime.report().records[0]
    assert record.result.content_truncated
    assert record.result.content_sha256 is not None
    assert "boundary" not in record.result.content and "boundary" not in result.content
    assert "boundary" not in (tmp_path / "ops.db").read_bytes().decode("utf-8", errors="ignore")


async def test_oversized_successful_output_and_saved_full_response_reconcile(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    full = "large-result-" * 10000
    async def output(**_params):
        return ToolResult(full)
    tool.execute = output
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        result = await registry.execute(call.name, call.arguments)
    session.messages.append(SessionMessage("tool", content=full, tool_call_id="call"))
    restored_session = session_from_dict(session.to_dict())
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    restored.begin()
    assert len(restored_session.operations.observed_ids) == 1
    assert runtime.report().records[0].result.content == result.content


async def test_conflicting_full_output_is_detected_beyond_visible_truncation(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    full = "large-result-" * 10000
    async def output(**_params):
        return ToolResult(full)
    tool.execute = output
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        await registry.execute(call.name, call.arguments)
    session.messages.append(SessionMessage("tool", content=full[:-1] + "!", tool_call_id="call"))
    with pytest.raises(OperationRecoveryError, match="conflicting_saved_result"):
        runtime.begin()


@pytest.mark.parametrize("damage", ["assistant", "result", "content"])
async def test_observed_ids_cannot_hide_missing_or_conflicting_transcript(tmp_path: Path, damage: str) -> None:
    session, call, _, runtime, registry, _ = setup(tmp_path)
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        await registry.execute(call.name, call.arguments)
    runtime.begin()  # reconcile the committed result and mark its evidence observed
    restored_session = session_from_dict(session.to_dict())
    if damage == "assistant":
        restored_session.messages[0] = SessionMessage("assistant", content="different reply")
    elif damage == "result":
        restored_session.messages.pop()
    else:
        restored_session.messages[-1].content = "forged successful result"
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    with pytest.raises(OperationRecoveryError):
        restored.begin()


def test_unselected_process_session_uses_only_runtime_owned_memory(tmp_path: Path) -> None:
    saved = []
    runtime = SessionRunOperations(Settings(), lambda: None, saved.append, tmp_path / "ops.db")
    first = runtime.begin()
    second = runtime.begin()
    assert first.session is second.session
    assert first.journal is second.journal
    assert first.session.operations.persistence == "process"
    assert not saved and not (tmp_path / "ops.db").exists()


def test_unselected_durable_session_still_fails_closed(tmp_path: Path) -> None:
    settings = Settings.model_validate({"operations": {"persistence": "durable"}})
    runtime = SessionRunOperations(settings, lambda: None, lambda _: None, tmp_path / "ops.db")
    with pytest.raises(OperationRecoveryError, match="operation_session_required"):
        runtime.begin()
    assert not (tmp_path / "ops.db").exists()


async def test_typed_result_replay_preserves_explicit_null_and_detached_projected_metadata(tmp_path: Path) -> None:
    session, call, _, runtime, registry, tool = setup(tmp_path)
    session.evidence_redactor.register_secret("typed-credential")
    blocks = ({"type": "text", "text": "typed-credential"},)
    metadata = {"trace": "typed-credential", "nested": {"stable": "original"}}
    async def output(**_params):
        return ToolResult("answer", content_blocks=blocks, structured_content=None,
                          structured_content_present=True, metadata=metadata)
    tool.execute = output
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    with use_operation_call(invocation):
        first = await registry.execute(call.name, call.arguments)
    assert first.structured_content_present and first.structured_content is None
    assert first.content_blocks == ({"type": "text", "text": "[REDACTED]"},)
    metadata["nested"]["stable"] = "caller changed"
    first.metadata["nested"]["stable"] = "consumer changed"
    with use_operation_call(invocation):
        replay = await registry.execute(call.name, call.arguments)
    assert replay.structured_content_present and replay.structured_content is None
    assert replay.metadata["trace"] == "[REDACTED]"
    assert replay.metadata["nested"] == {"stable": "original"}
    assert replay.metadata["henchman.checkpoint"]["status"] == "unavailable"
    assert "typed-credential" not in str(runtime.report())
    restored_session = session_from_dict(session.to_dict())
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    restored.begin()
    payload = restored_session.messages[-1].tool_result
    assert payload["structured_content_present"] is True and payload["structured_content"] is None
    assert payload["metadata"]["nested"]["stable"] == "original"
    payload["metadata"]["nested"]["stable"] = "forged"
    with pytest.raises(OperationRecoveryError, match="conflicting_saved_result"):
        restored.begin()


async def test_oversized_typed_payload_has_visible_unavailable_provenance(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    async def output(**_params):
        return ToolResult("answer", structured_content={"large": "x" * 100000}, structured_content_present=True)
    tool.execute = output
    with use_operation_call(runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)):
        result = await registry.execute(call.name, call.arguments)
    record = runtime.report().records[0]
    assert record.result.payload_truncated and record.result.payload_sha256
    assert "typed tool evidence unavailable" in result.content
    assert result.metadata["operation_evidence"]["structured_content_was_present"] is True
    assert result.structured_content_present is False


async def test_known_live_attempt_does_not_turn_into_a_recovery_barrier(tmp_path: Path) -> None:
    _, call, _, runtime, registry, tool = setup(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    async def wait(**_params):
        entered.set()
        await release.wait()
        return ToolResult("observed completion")
    tool.execute = wait
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    with use_operation_call(invocation):
        task = asyncio.create_task(registry.execute(call.name, call.arguments))
    await entered.wait()
    try:
        runtime.begin()
        assert runtime.report().records[0].state == "started"
    finally:
        release.set()
        await task
    runtime.begin()
    assert runtime.report().records[0].state == "completed"
