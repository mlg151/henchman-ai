"""Controller checks retain separate evidence under the ordinary effect journal."""

from copy import deepcopy

import pytest

from henchman.core.operation_recovery import OperationRecoveryError, project_operation_result
from henchman.core.runtime_operations import use_operation_call
from henchman.core.session_data import session_from_dict
from tests.core.test_session_operations import setup


@pytest.mark.parametrize("durable", [False, True])
async def test_controller_result_reconciles_without_inventing_primary_messages(tmp_path, durable):
    session, _, saved, runtime, registry, tool = setup(tmp_path, durable=durable)
    primary = deepcopy(session.messages)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    with use_operation_call(invocation):
        await registry.execute("effect", {"value": "controller"})
    run.settle_controller_call(invocation)
    assert session.messages == primary
    conversation, = session.operations.conversations
    assert conversation.id.startswith(f"{run.run_id}:controller:")
    assert conversation.messages[0].agent_role == "runtime_controller"
    assert "not a provider response" in conversation.messages[0].content
    assert [message.role for message in conversation.messages] == ["assistant", "tool"]
    assert len(session.operations.observed_ids) == 1
    assert tool.calls == ["controller"]
    if durable:
        restored_session = session_from_dict(saved[-1])
        _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
        restored.begin()
        assert restored_session.messages == primary
        assert restored_session.operations == session.operations


@pytest.mark.parametrize("fault", ["before_queue_commit", "after_queue_commit", "binding_save", "after_start"])
async def test_controller_fault_retains_authority_and_never_dispatches_twice(tmp_path, monkeypatch, fault):
    session, _, saved, runtime, registry, tool = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    if fault == "binding_save":
        def fail(_session):
            raise OSError("binding unavailable")
        monkeypatch.setattr(runtime, "save", fail)
    else:
        def checkpoint(stage):
            if stage == {"before_queue_commit": "queue:before_commit", "after_queue_commit": "queue:after_commit", "after_start": "start:after_commit"}[fault]:
                raise OSError("interrupted transaction acknowledgement")
        monkeypatch.setattr(run.journal._store, "_checkpoint", checkpoint)
    with use_operation_call(invocation), pytest.raises(OperationRecoveryError) as failure:
        await registry.execute("effect", {"value": "controller"})
    run.settle_controller_call(invocation, primary=failure.value)
    assert tool.calls == []
    records = run.journal.report().records
    if fault == "before_queue_commit":
        assert records == () and session.operations.conversations == ()
    else:
        assert len(records) == 1 and len(session.operations.conversations) == 1
        if fault == "after_start":
            assert records[0].state == "outcome_unknown"
        else:
            assert records[0].state == "queued"
        with pytest.raises(OperationRecoveryError):
            run.require_ready()
        assert not session.operations.observed_ids


@pytest.mark.parametrize("state", ["started", "outcome_unknown"])
def test_readiness_allows_only_the_exact_active_owned_invocation(tmp_path, state):
    session, _, _, runtime, _, _ = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    invocation.prepare("effect", {"value": "controller"}, "effectful")
    assert invocation.start() is not None
    if state == "outcome_unknown":
        invocation.cancel()
    before = run.journal.report()
    with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
        run.require_ready()
    with use_operation_call(invocation):
        if state == "started":
            run.require_ready()
        else:
            with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
                run.require_ready()
    assert run.journal.report() == before
    assert not session.operations.observed_ids


def test_readiness_cannot_exempt_another_started_operation(tmp_path):
    _, _, _, runtime, _, _ = setup(tmp_path)
    run = runtime.begin()
    first = run.controller_call("effect", {"value": "first"})
    second = run.controller_call("effect", {"value": "second"})
    first.prepare("effect", {"value": "first"}, "effectful")
    second.prepare("effect", {"value": "second"}, "effectful")
    first.start()
    second.start()
    before = run.journal.report()
    with use_operation_call(first), pytest.raises(OperationRecoveryError, match="unresolved_operation"):
        run.require_ready()
    assert run.journal.report() == before


@pytest.mark.parametrize("change", ["object", "identity"])
def test_controller_admission_and_settlement_require_held_session(tmp_path, monkeypatch, change):
    session, _, _, runtime, _, _ = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    invocation.prepare("effect", {"value": "controller"}, "effectful")
    permit = invocation.start()
    invocation.complete(permit, project_operation_result("done", True, redactor=session.evidence_redactor))
    if change == "object":
        monkeypatch.setattr(runtime, "current", lambda: deepcopy(session))
    else:
        session.id = "changed"
    with pytest.raises(OperationRecoveryError, match="session_authority_changed"):
        run.controller_call("effect", {"value": "another"})
    with pytest.raises(OperationRecoveryError, match="session_authority_changed"):
        run.settle_controller_call(invocation)
    assert len(run.journal.report().records) == 1
    assert not session.operations.observed_ids


async def test_late_denial_discards_only_never_queued_controller_evidence(tmp_path):
    session, _, saved, runtime, registry, tool = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    before = len(saved)
    registry.set_plan_mode(enabled=True)
    with use_operation_call(invocation):
        result = await registry.execute("effect", {"value": "controller"})
    run.settle_controller_call(invocation)
    assert not result.success and tool.calls == []
    assert run.journal.report().records == ()
    assert session.operations.conversations == () and len(saved) == before


async def test_result_save_failure_recovers_committed_controller_result_without_reexecution(tmp_path, monkeypatch):
    session, _, saved, runtime, registry, tool = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    with use_operation_call(invocation):
        await registry.execute("effect", {"value": "controller"})
    def fail(_session):
        raise OSError("cannot save observation")
    monkeypatch.setattr(runtime, "save", fail)
    with pytest.raises(OperationRecoveryError, match="session_save_failed"):
        run.settle_controller_call(invocation)
    assert not session.operations.observed_ids
    assert run.journal.report().records[0].state == "completed"
    restored_session = session_from_dict(saved[-1])
    _, _, _, restored, _, _ = setup(tmp_path, session=restored_session)
    restored.begin()
    assert len(restored_session.operations.observed_ids) == 1
    assert restored_session.operations.conversations[0].messages[-1].content == "effect observed"
    assert tool.calls == ["controller"]


def test_cancelled_controller_retains_primary_when_settlement_storage_fails(tmp_path, monkeypatch):
    import asyncio

    session, _, _, runtime, _, _ = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    invocation.prepare("effect", {"value": "controller"}, "effectful")
    invocation.start()
    invocation.cancel()
    def fail():
        raise OSError("storage unavailable")
    monkeypatch.setattr(run.journal, "report", fail)
    primary = asyncio.CancelledError("owned cancellation")
    run.settle_controller_call(invocation, primary=primary)
    assert str(primary) == "owned cancellation"
    assert "OSError" in primary.__notes__[0]
    assert len(session.operations.conversations) == 1


def test_readiness_does_not_reconcile_completed_unobserved_evidence(tmp_path):
    session, _, saved, runtime, _, _ = setup(tmp_path)
    run = runtime.begin()
    invocation = run.controller_call("effect", {"value": "controller"})
    invocation.prepare("effect", {"value": "controller"}, "effectful")
    permit = invocation.start()
    invocation.complete(permit, project_operation_result("done", True, redactor=session.evidence_redactor))
    before, saved_count = session.to_dict(), len(saved)
    run.require_ready()
    assert session.to_dict() == before and len(saved) == saved_count
    assert not session.operations.observed_ids
