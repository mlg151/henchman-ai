"""Accepted input identities follow actual runs and effects without replay grants."""

import asyncio

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.core.runtime_operations import use_operation_call
from henchman.core.runtime_workflow import correlate_workflow, use_workflow_input
from henchman.core.session_operations import SessionRunOperations
from henchman.core.workflow_state import WorkflowError
from tests.agents.test_agent_budget_scope import AccountingProvider
from tests.core.test_session_operations import setup as operation_setup
from tests.core.test_session_workflow import controller


@pytest.mark.parametrize("direct", [False, True])
async def test_public_runs_record_actual_run_ids_before_provider_dispatch(tmp_path, direct):
    workflow, session, settings = controller(tmp_path)
    workflow.submit("one request")
    dispatch = workflow.next_input()
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider, settings=settings)
    orchestrator.operation_runtime = SessionRunOperations(settings, lambda: session, lambda _session: None, tmp_path / "ops.db")
    with use_workflow_input(workflow, dispatch):
        stream = orchestrator.run_direct("explorer", dispatch.text) if direct else orchestrator.run(dispatch.text)
        _ = [event async for event in stream]
    item = workflow.report().state.inputs[0]
    assert item.budget_run_ids == (orchestrator.last_budget_scope.ledger.run_id,)
    assert len(item.operation_run_ids) == 1
    assert provider.calls == 1
    workflow.finish(dispatch, outcome="success")


async def test_failed_workflow_correlation_prevents_provider_dispatch(tmp_path):
    workflow, session, settings = controller(tmp_path)
    workflow.submit("one request")
    dispatch = workflow.next_input()
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider, settings=settings)
    orchestrator.operation_runtime = SessionRunOperations(settings, lambda: session, lambda _session: None, tmp_path / "ops.db")
    workflow.save_session = lambda _session: (_ for _ in ()).throw(OSError("full"))
    with use_workflow_input(workflow, dispatch), pytest.raises(WorkflowError, match="session_save_failed"):
        _ = [event async for event in orchestrator.run(dispatch.text)]
    assert provider.calls == 0
    assert not orchestrator._public_run_active


async def test_operation_correlation_precedes_effect_and_survives_late_child(tmp_path):
    session, call, _, operations, registry, tool = operation_setup(tmp_path)
    workflow, _, _ = controller(tmp_path, session=session)
    workflow.submit("one request")
    dispatch = workflow.next_input()
    run = operations.begin()
    invocation = run.bind_call(call, agent_id="tech_lead", assistant_index=0)
    released = asyncio.Event()

    async def child():
        await released.wait()
        with use_operation_call(invocation):
            return await registry.execute(call.name, call.arguments)

    with use_workflow_input(workflow, dispatch):
        task = asyncio.create_task(child())
    workflow.finish(dispatch, outcome="success")
    released.set()
    assert (await task).success
    item = workflow.report().state.inputs[0]
    assert item.operation_ids == (invocation.binding.operation_id,)
    assert item.operation_run_ids == (run.run_id,)
    assert item.state == "completed" and tool.calls == ["original"]
    assert workflow.next_input() is None
    # Parent task context was reset and cannot accidentally attribute unrelated work.
    correlate_workflow(session, operation_id="unrelated")
    assert workflow.report().state.inputs[0].operation_ids == item.operation_ids


async def test_failed_operation_correlation_leaves_queued_effect_undispatched(tmp_path):
    session, call, _, operations, registry, tool = operation_setup(tmp_path)
    workflow, _, _ = controller(tmp_path, session=session)
    workflow.submit("one request")
    dispatch = workflow.next_input()
    run = operations.begin()
    workflow.save_session = lambda _session: (_ for _ in ()).throw(OSError("full"))
    with use_workflow_input(workflow, dispatch), use_operation_call(run.bind_call(call, agent_id="tech_lead", assistant_index=0)), pytest.raises(WorkflowError):
        await registry.execute(call.name, call.arguments)
    assert not tool.calls
    assert operations.report().records[0].state == "queued"
