"""Compaction retains operation correlation without granting replay authority."""

from copy import deepcopy
from dataclasses import asdict, replace

import pytest

from henchman.config.schema import Settings
from henchman.core.operation_bindings import OperationConversation
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.runtime_operations import use_operation_call
from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_context import SessionContextService
from henchman.core.session_operations import SessionRunOperations
from henchman.providers.base import ToolCall
from henchman.tools.registry import ToolRegistry
from tests.core.test_session_operations import EffectTool, approve


def setup(tmp_path):
    manager = SessionManager(tmp_path / "sessions")
    session = manager.create_session("project")
    settings = Settings(operations={"persistence": "durable"})
    runtime = SessionRunOperations(settings, lambda: session, manager.save, tmp_path / "ops.db")
    registry = ToolRegistry()
    tool = EffectTool()
    registry.register(tool)
    registry.set_confirmation_handler(lambda _request: approve())
    return manager, session, settings, runtime, registry, tool


async def completed_turn(session, runtime, registry, label):
    call = ToolCall(label, "effect", {"value": label})
    session.messages.extend([SessionMessage("user", label), SessionMessage("assistant", tool_calls=[asdict(call)])])
    run = runtime.begin()
    invocation = run.bind_call(call, agent_id="engineer", assistant_index=len(session.messages) - 1)
    with use_operation_call(invocation):
        await registry.execute(call.name, call.arguments)
    runtime.finish(run, failed=False)
    session.messages.append(SessionMessage("assistant", "Done"))


@pytest.mark.parametrize("preserve_turns", [0, 1])
async def test_completed_operations_survive_atomic_save_load_after_compaction(tmp_path, preserve_turns):
    manager, session, settings, runtime, registry, tool = setup(tmp_path)
    await completed_turn(session, runtime, registry, "first")
    await completed_turn(session, runtime, registry, "second")
    original = deepcopy(session.messages)
    before = session.operations
    manager.save(session)
    service = SessionContextService(manager)
    assert service.compact_session(session, preserve_turns=preserve_turns).changed
    manager.save(session)
    restored = manager.load(session.id)
    assert service.restore_compacted_messages(restored) == original
    resumed = SessionRunOperations(settings, lambda: restored, manager.save, tmp_path / "ops.db")
    resumed.begin()
    assert [record.state for record in resumed.report().records] == ["completed", "completed"]
    assert tool.calls == ["first", "second"]
    assert [(item.operation_id, item.context) for item in restored.operations.bindings] == [
        (item.operation_id, item.context) for item in before.bindings
    ]
    assert restored.operations.reference == before.reference
    assert restored.operations.observed_ids == before.observed_ids
    await completed_turn(restored, resumed, registry, "third")
    assert tool.calls == ["first", "second", "third"]
    assert len(resumed.report().records) == 3


async def test_repeated_compaction_preserves_archives_and_current_primary_offsets(tmp_path):
    manager, session, settings, runtime, registry, tool = setup(tmp_path)
    await completed_turn(session, runtime, registry, "first")
    await completed_turn(session, runtime, registry, "second")
    service = SessionContextService(manager)
    service.compact_session(session, preserve_turns=1)
    first_archives = deepcopy(session.operations.conversations)
    await completed_turn(session, runtime, registry, "third")
    service.compact_session(session, preserve_turns=1)
    assert session.operations.conversations[:len(first_archives)] == first_archives
    manager.save(session)
    restored = manager.load(session.id)
    resumed = SessionRunOperations(settings, lambda: restored, manager.save, tmp_path / "ops.db")
    resumed.begin()
    assert len(resumed.report().records) == 3
    assert tool.calls == ["first", "second", "third"]
    assert session.messages[session.operations.bindings[-1].assistant_index].tool_calls[0]["id"] == "third"


@pytest.mark.parametrize("state", ["queued", "started", "outcome_unknown"])
async def test_unreconciled_operation_refuses_compaction_without_mutating_recovery(tmp_path, state):
    manager, session, _, runtime, _, _ = setup(tmp_path)
    call = ToolCall("pending", "effect", {"value": "uncertain"})
    session.messages = [SessionMessage("user", "first"), SessionMessage("assistant", tool_calls=[asdict(call)])]
    run = runtime.begin()
    invocation = run.bind_call(call, agent_id="engineer", assistant_index=1)
    record = runtime.prepare(invocation, call.name, call.arguments, "effectful")
    if state != "queued":
        run.journal.start(record.operation_id)
    if state == "outcome_unknown":
        run.journal.cancel(record.operation_id)
    session.messages.append(SessionMessage("user", "later evidence"))
    before = deepcopy(session.to_dict())
    with pytest.raises(OperationRecoveryError, match="unreconciled_operation_compaction"):
        SessionContextService(manager).compact_session(session, preserve_turns=1)
    assert session.to_dict() == before
    assert run.journal.report().records[0].state == state


@pytest.mark.parametrize("damage", ["index", "missing_result", "malformed_call"])
async def test_compaction_cannot_hide_corrupt_binding_or_mutate_specialist_evidence(tmp_path, damage):
    manager, session, _, runtime, registry, _ = setup(tmp_path)
    await completed_turn(session, runtime, registry, "first")
    await completed_turn(session, runtime, registry, "second")
    state = session.operations
    specialist = OperationConversation("specialist", (SessionMessage("assistant", "retained"),))
    session.operations = replace(state, conversations=(specialist,))
    if damage == "index":
        session.operations = replace(session.operations, bindings=(
            replace(state.bindings[0], assistant_index=0), *state.bindings[1:],
        ))
    elif damage == "missing_result":
        session.messages[2].tool_call_id = "other"
    else:
        session.messages[1].tool_calls = ["corrupt"]
    before = deepcopy(session.to_dict())
    with pytest.raises(OperationRecoveryError, match="invalid_compaction_correlation"):
        SessionContextService(manager).compact_session(session, preserve_turns=1)
    assert session.to_dict() == before


async def test_compaction_preserves_typed_opaque_and_specialist_evidence(tmp_path):
    from henchman.providers.anthropic import AnthropicProvider
    from henchman.providers.continuation import ContinuationEnvelope
    from henchman.tools.base import ToolResult

    manager, session, settings, runtime, registry, tool = setup(tmp_path)

    async def typed_output(**params):
        tool.calls.append(params["value"])
        return ToolResult("Observed", content_blocks=({"type": "text", "text": "Observed"},),
                          structured_content_present=True, structured_content=None, metadata={"source": "fixture"})

    tool.execute = typed_output
    await completed_turn(session, runtime, registry, "first")
    provider = AnthropicProvider(api_key="offline-test", model="model-a")
    try:
        blocks = [{"type": "thinking", "thinking": "Inspect", "signature": "opaque-signature"},
                  {"type": "tool_use", "id": "first", "name": "effect", "input": {"value": "first"}}]
        session.messages[1].continuation = ContinuationEnvelope.create(provider, blocks).to_dict()
        specialist = OperationConversation("specialist", (SessionMessage("assistant", "separate history"),))
        session.operations = replace(session.operations, conversations=(specialist,))
        original = deepcopy(session.messages)
        session.messages.extend([SessionMessage("user", "later"), SessionMessage("assistant", "No tools")])
        SessionContextService(manager).compact_session(session, preserve_turns=1)
        assert session.operations.conversations[0] == specialist
        assert session.operations.conversations[1].messages == tuple(original)
        manager.save(session)
        restored = manager.load(session.id)
        resumed = SessionRunOperations(settings, lambda: restored, manager.save, tmp_path / "ops.db")
        resumed.begin()
        archived = restored.operations.conversations[1].messages
        assert archived[1].continuation == original[1].continuation
        assert archived[2].tool_result["structured_content_present"] is True
        assert archived[2].tool_result["structured_content"] is None
        # Retention summaries and operation evidence must not share mutable data.
        restored.turn_summaries[0].retained_messages[1].tool_calls[0]["arguments"]["value"] = "edited evidence"
        assert archived[1].tool_calls[0]["arguments"]["value"] == "first"
        assert tool.calls == ["first"]
    finally:
        await provider._client.close()


async def test_compaction_and_resume_keep_consumed_budget_without_new_dispatch(tmp_path):
    from henchman.core.run_budget import RequestEstimate
    from henchman.core.session_run_accounting import SessionRunAccounting
    from henchman.providers.usage import UsageReport
    from tests.agents.test_agent_budget_scope import AccountingProvider

    manager, session, settings, runtime, registry, tool = setup(tmp_path)
    settings.usage.persistence = "durable"
    accounting = SessionRunAccounting(settings, lambda: session, manager.save, tmp_path / "ops.db")
    scope = accounting.begin(AccountingProvider())
    request = scope.ledger.reserve(RequestEstimate(10, 2))
    scope.ledger.start(request.request_id)
    scope.ledger.reconcile(request.request_id, UsageReport(prompt_tokens=10, completion_tokens=2, source="reported"), final=True)
    await completed_turn(session, runtime, registry, "first")
    await completed_turn(session, runtime, registry, "second")
    before = scope.ledger.snapshot()
    SessionContextService(manager).compact_session(session, preserve_turns=1)
    manager.save(session)
    restored = manager.load(session.id)
    resumed = SessionRunOperations(settings, lambda: restored, manager.save, tmp_path / "ops.db")
    resumed.begin()
    recovered_accounting = SessionRunAccounting(settings, lambda: restored, manager.save, tmp_path / "ops.db")
    recovered = recovered_accounting.begin(AccountingProvider())
    assert recovered.ledger.run_id == scope.ledger.run_id
    after = recovered.ledger.snapshot()
    assert after.consumed_requests == before.consumed_requests == 1
    assert after.records == before.records
    assert tool.calls == ["first", "second"]


@pytest.mark.parametrize("preserve_turns", [0, 1])
async def test_system_prefix_stays_first_across_repeated_compaction_and_reload(tmp_path, preserve_turns):
    manager, session, settings, runtime, registry, tool = setup(tmp_path)
    session.messages.append(SessionMessage("system", "Original instructions"))
    expected = deepcopy(session.messages)
    service = SessionContextService(manager)
    for label in ("first", "second", "third"):
        start = len(session.messages)
        call = ToolCall("reused-call-id", "effect", {"value": label})
        session.messages.extend([SessionMessage("user", label), SessionMessage("assistant", tool_calls=[asdict(call)])])
        run = runtime.begin()
        invocation = run.bind_call(call, agent_id="engineer", assistant_index=len(session.messages) - 1)
        with use_operation_call(invocation):
            await registry.execute(call.name, call.arguments)
        runtime.finish(run, failed=False)
        session.messages.append(SessionMessage("assistant", "Done"))
        expected.extend(deepcopy(session.messages[start:]))
        service.compact_session(session, preserve_turns=preserve_turns)
        manager.save(session)
        session = manager.load(session.id)
        runtime = SessionRunOperations(settings, lambda current=session: current, manager.save, tmp_path / "ops.db")
        runtime.begin()
        assert service.restore_compacted_messages(session) == expected
        assert session.messages[0] == expected[0]
    assert tool.calls == ["first", "second", "third"]
    assert len({binding.operation_id for binding in session.operations.bindings}) == 3
    assert all(record.state == "completed" for record in runtime.report().records)
