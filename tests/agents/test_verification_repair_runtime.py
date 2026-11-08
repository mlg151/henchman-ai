"""Public repair holds current runtime and formatter authority at real boundaries."""

import asyncio
import sys

import pytest
from tests.e2e.test_bounded_repair import make_runtime

from henchman.config.schema import Settings
from henchman.core.run_budget import BudgetExceeded
from henchman.tools.access_policy import ToolAccessPolicy
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.repair_scope import RepairControlError, current_repair


async def test_actual_verification_dispatch_has_started_controller_operation(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks
    from henchman.core.runtime_operations import current_operation_call, current_operation_run

    orch, provider, _service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [])
    (tmp_path / "target.py").write_text("def add(a, b):\n    return a + b\n")
    actual = acceptance_checks.run_bounded_subprocess
    observed = []

    async def inspect(*args, **kwargs):
        run, invocation = current_operation_run(), current_operation_call()
        observed.append((run, invocation))
        assert run is not None and invocation is not None
        assert invocation.run is run
        record = next(item for item in run.journal.report().records if item.operation_id == invocation.binding.operation_id)
        assert record.state == "started"
        assert record.context.agent_id == "runtime:verification"
        assert run.runtime._inflight[record.operation_id] is invocation
        assert invocation.binding.conversation_id.startswith(f"{run.run_id}:controller:")
        return await actual(*args, **kwargs)

    monkeypatch.setattr(acceptance_checks, "run_bounded_subprocess", inspect)
    try:
        report = await orch.repair_direct("engineer", "Verify", request)
        assert report.status == "scoped_pass"
        assert len(observed) == 1 and calls == []
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("change", ["settings_binding", "project_binding", "session_project", "missing_tool", "restricted"])
async def test_stale_or_restricted_verifier_refuses_before_model_or_checks(tmp_path, monkeypatch, change):
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [])
    tool = orch.tool_registry.get("verify_plan_execution")
    if change == "settings_binding":
        tool._plan_service._settings = Settings()
    elif change == "project_binding":
        tool._plan_service._project_root = tmp_path / "elsewhere"
    elif change == "missing_tool":
        orch.settings.agents.agents["engineer"].tools = ["read_file", "edit_file"]
    elif change == "session_project":
        from henchman.core.session_helpers import compute_project_hash
        from henchman.core.session_operations import SessionRunOperations

        orch.operation_runtime = SessionRunOperations.for_process(orch.settings)
        orch.operation_runtime.current_session.project_hash = compute_project_hash(tmp_path / "other")
    else:
        orch.tool_registry.set_access_policy(ToolAccessPolicy.from_settings(
            orch.settings.tools.model_copy(update={"network_access": "disabled"}), project_root=tmp_path,
        ))
    try:
        with pytest.raises(RepairControlError):
            await orch.repair_direct("engineer", "Repair", request)
        assert calls == []
        assert service.get_plan(request.plan_id).last_verification is None
        assert not orch._public_run_active and not orch.pool._execution_claims
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("call", [
    ("protected", "edit_file", {"path": "criteria.py", "old_str": "[5, -2]", "new_str": "[-1, -6]"}),
    ("criteria", "verify_plan_execution", {"action": "create", "steps": ["weaken criteria"]}),
])
async def test_model_cannot_change_criteria_or_enter_controller_verification(tmp_path, monkeypatch, call):
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [call])
    criteria = (tmp_path / "criteria.py").read_bytes()
    try:
        with pytest.raises(RepairControlError):
            await orch.repair_direct("engineer", "Repair", request)
        assert len(calls) == 1
        assert (tmp_path / "criteria.py").read_bytes() == criteria
        assert len(service.list_plans()) == 1
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()


async def test_zero_request_budget_stops_the_first_model_attempt_without_reset(tmp_path, monkeypatch):
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [])
    orch.settings.usage.limits.max_requests = 0
    try:
        with pytest.raises(BudgetExceeded):
            await orch.repair_direct("engineer", "Repair", request)
        assert calls == []
        assert orch.last_budget_scope.ledger.snapshot().consumed_requests == 0
        report = service.get_plan(request.plan_id).last_repair
        assert report["repairs_started"] == 1 and report["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("change", ["replacement", "symlink", "outside", "grant", "settings", "policy", "tool", "method", "peer", "owner"])
async def test_formatter_rechecks_owned_post_edit_target_and_live_authority(tmp_path, monkeypatch, change):
    from henchman.tools import formatting

    call = ("edit", "edit_file", {"path": "target.py", "old_str": "a - b", "new_str": "a + b"})
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [call])
    outside = tmp_path.parent / f"outside-{tmp_path.name}.py"
    outside.write_text("answer=  987\n")
    original = formatting.format_python_files
    entered, release = asyncio.Event(), asyncio.Event()

    async def paused(paths, *, cwd):
        entered.set()
        await release.wait()
        if change == "outside":
            paths[:] = [outside]
        if change == "owner":
            return await asyncio.create_task(original(paths, cwd=cwd))
        return await original(paths, cwd=cwd)

    monkeypatch.setattr(formatting, "format_python_files", paused)
    task = asyncio.create_task(orch.repair_direct("engineer", "Repair", request))
    ready = asyncio.create_task(entered.wait())
    peer_claim = None
    try:
        # Exercise the authority race after the approved edit has completed.
        # Verification and admission can exceed ten seconds under coverage;
        # report an early task failure instead of hiding it as an event timeout.
        done, _ = await asyncio.wait(
            {task, ready}, return_when=asyncio.FIRST_COMPLETED,
            timeout=request.timeout_seconds + 10,
        )
        if task in done:
            report = await task
            pytest.fail(f"Repair ended before formatter observation: {report.status}/{report.reason}")
        assert ready in done, "Repair did not reach the formatter within its bounded run deadline"
        target = tmp_path / "target.py"
        assert "a + b" in target.read_text(), "The approved body must finish before the race"
        if change == "replacement":
            replacement = tmp_path / "replacement.py"
            replacement.write_text("answer=  321\n")
            replacement.replace(target)
        elif change == "symlink":
            target.unlink()
            try:
                target.symlink_to(outside)
            except OSError:
                pytest.skip("This platform cannot create the symlink fixture")
        elif change == "grant":
            orch.tool_registry.clear_grants()
        elif change == "settings":
            orch.settings.tools.auto_approve_read = False
        elif change == "policy":
            orch.tool_registry.set_plan_mode(enabled=True)
        elif change == "tool":
            orch.tool_registry.unregister("edit_file")
            orch.tool_registry.register(EditFileTool())
        elif change == "method":
            async def changed(**_kwargs):
                pytest.fail("A replacement implementation must not execute")

            monkeypatch.setattr(orch.tool_registry.get("edit_file"), "execute", changed)
        elif change == "peer":
            peer_claim = orch.pool.claim_agent(orch.pool.get_agent("explorer"), owner=object())
            peer_claim.__enter__()
        release.set()
        with pytest.raises(RepairControlError):
            await task
        assert len(calls) == 1
        assert outside.read_text() == "answer=  987\n"
        if change == "replacement":
            assert target.read_text() == "answer=  321\n"
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
        assert not orch._public_run_active
        assert len(orch.pool._execution_claims) == (1 if peer_claim is not None else 0)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        ready.cancel()
        await asyncio.gather(task, ready, return_exceptions=True)
        if peer_claim is not None:
            peer_claim.__exit__(None, None, None)
        await orch.aclose()
        await provider._client.close()


async def test_event_consumer_has_no_lease_and_overlapping_public_run_is_rejected(tmp_path, monkeypatch):
    orch, provider, _service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [None, None])
    checked = []

    async def observe(event):
        assert current_repair() is None
        if event.type.value == "content":
            with pytest.raises(ValueError, match="already active"):
                await anext(orch.run_direct("engineer", "overlap"))
            checked.append(event)

    try:
        report = await orch.repair_direct("engineer", "Repair", request, on_event=observe)
        assert report.reason == "identical_failure_limit"
        assert len(calls) == 2 and checked
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("change", ["required_checks", "criteria"])
async def test_verification_rechecks_immutable_authority_before_the_next_effect(tmp_path, monkeypatch, change):
    from henchman.advanced import acceptance_checks

    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [])
    plan = service.create_plan(steps=["Repair with two trusted checks"], checks=[
        {"kind": "command", "argv": [sys.executable, "-B", "criteria.py"], "inputs": ["target.py", "criteria.py"]},
        {"kind": "command", "argv": [sys.executable, "-c", "from pathlib import Path; Path('second-effect').write_text('ran')"],
         "inputs": ["target.py", "criteria.py"]},
    ])
    request = request.model_copy(update={"plan_id": plan.plan_id})
    actual = acceptance_checks.run_bounded_subprocess
    commands = []

    async def changed(command, **kwargs):
        result = await actual(command, **kwargs)
        commands.append(command)
        if len(commands) == 1:
            if change == "required_checks":
                orch.settings.verification.checks = [{"kind": "file_exists", "path": "new-required.txt"}]
            else:
                (tmp_path / "criteria.py").write_text("print('weakened criterion')\n")
        return result

    monkeypatch.setattr(acceptance_checks, "run_bounded_subprocess", changed)
    try:
        report = await orch.repair_direct("engineer", "Repair", request)
        assert report.status == "incomplete"
        assert len(commands) == 1
        assert not (tmp_path / "second-effect").exists()
        assert calls == []
    finally:
        await orch.aclose()
        await provider._client.close()


async def test_formatter_handoff_does_not_grant_a_future_tool_dispatch(tmp_path, monkeypatch):
    params = {"path": "target.py", "old_str": "return ", "new_str": "return 0 + "}
    script = [("first", "edit_file", params), ("second", "edit_file", params), None]
    orch, provider, _service, request, calls, approvals = await make_runtime(tmp_path, monkeypatch, "openai_compat", script)
    request = request.model_copy(update={"max_repairs": 1})
    try:
        report = await orch.repair_direct("engineer", "Repair", request)
        assert report.reason == "attempts_exhausted"
        assert len(calls) == 3
        assert [item.tool_name for item in approvals].count("edit_file") == 2
        assert len(orch.tool_registry.list_approval_grants()) == 3
        assert "return 0 + 0 + a - b" in (tmp_path / "target.py").read_text()
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("durable", [False, True])
async def test_cancellation_joins_the_owned_verification_subprocess(tmp_path, monkeypatch, durable):
    from henchman.core.operation_recovery import OperationRecoveryError
    from henchman.core.session_data import Session, session_from_dict
    from henchman.core.session_helpers import compute_project_hash
    from henchman.core.session_operations import SessionRunOperations
    from henchman.tools import subprocess_utils

    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [])
    saved = []
    if durable:
        orch.settings.operations.persistence = "durable"
        session = Session("repair-session", compute_project_hash(tmp_path), "today", "today")
        orch.operation_runtime = SessionRunOperations(
            orch.settings, lambda: session, lambda item: saved.append(item.to_dict()), tmp_path / "ops.db")
    plan = service.create_plan(steps=["Wait in a trusted check"], checks=[{
        "kind": "command", "argv": [sys.executable, "-c", "import time; time.sleep(60)"],
        "inputs": ["target.py", "criteria.py"], "timeout": 60,
    }])
    request = request.model_copy(update={"plan_id": plan.plan_id})
    created = asyncio.Event()
    processes = []
    actual = subprocess_utils.asyncio.create_subprocess_exec

    async def observe(*command, **kwargs):
        process = await actual(*command, **kwargs)
        processes.append(process)
        created.set()
        return process

    monkeypatch.setattr(subprocess_utils.asyncio, "create_subprocess_exec", observe)
    task = asyncio.create_task(orch.repair_direct("engineer", "Repair", request))
    try:
        await asyncio.wait_for(created.wait(), 10)
        task.cancel("cancel owned verification")
        with pytest.raises(asyncio.CancelledError, match="cancel owned verification"):
            await task
        assert calls == [] and len(processes) == 1
        assert processes[0].returncode is not None
        retained = service.get_plan(plan.plan_id)
        assert retained.last_verification["status"] == "cancelled"
        assert retained.last_repair["reason"] == "cancelled"
        assert not orch._public_run_active and not orch.pool._execution_claims
        records = orch.operation_runtime.report().records
        assert len(records) == 1 and records[0].state == "outcome_unknown"
        assert records[0].context.agent_id == "runtime:verification"
        if durable:
            restored = session_from_dict(saved[-1])
            runtime = SessionRunOperations(orch.settings, lambda: restored, lambda _item: None, tmp_path / "ops.db")
            with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
                runtime.begin()
            assert len(runtime.report().records) == 1
            assert len(restored.operations.conversations[0].messages) == 1
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await orch.aclose()
        await provider._client.close()


async def test_unknown_model_operation_between_phases_blocks_next_check(tmp_path, monkeypatch):
    from dataclasses import asdict, replace

    from henchman.advanced import acceptance_checks
    from henchman.core.operation_bindings import OperationConversation
    from henchman.core.operation_recovery import OperationRecoveryError
    from henchman.core.session_models import SessionMessage
    from henchman.core.session_operations import SessionRunOperations
    from henchman.providers.base import ToolCall

    script = [("edit", "edit_file", {"path": "target.py", "old_str": "a - b", "new_str": "a + b"}), None]
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", script)
    held = []
    checks = []
    original_begin = SessionRunOperations.begin
    original_check = acceptance_checks.run_bounded_subprocess

    def begin(self, **kwargs):
        run = original_begin(self, **kwargs)
        held.append(run)
        return run

    async def checked(*args, **kwargs):
        checks.append(args)
        return await original_check(*args, **kwargs)

    monkeypatch.setattr(SessionRunOperations, "begin", begin)
    monkeypatch.setattr(acceptance_checks, "run_bounded_subprocess", checked)
    injected = []

    async def observe(event):
        if event.type.value != "content" or injected:
            return
        run = held[0]
        call = ToolCall("uncertain-edit", "edit_file", script[0][2])
        conversation_id = "specialist-uncertain"
        state = run.session.operations
        message = SessionMessage("assistant", tool_calls=[asdict(call)], agent_role="engineer")
        run.session.operations = replace(state, conversations=(*state.conversations,
            OperationConversation(conversation_id, (message,))))
        invocation = run.bind_call(call, agent_id="engineer", assistant_index=0, conversation_id=conversation_id)
        invocation.prepare(call.name, call.arguments, "effectful")
        invocation.start()
        invocation.cancel()
        injected.append(invocation.binding.operation_id)

    try:
        with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
            await orch.repair_direct("engineer", "Repair", request, on_event=observe)
        assert len(checks) == 1 and len(calls) == 2
        assert injected
        records = held[0].journal.report().records
        assert next(item for item in records if item.operation_id == injected[0]).state == "outcome_unknown"
        assert len([item for item in records if item.context.agent_id == "runtime:verification"]) == 1
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()


async def test_changed_session_controller_cannot_receive_another_runs_cleanup(tmp_path, monkeypatch):
    from types import SimpleNamespace

    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", [None])
    wrong_cleanup = []

    async def observe(event):
        if event.type.value == "content":
            orch.operation_runtime = SimpleNamespace(finish=lambda *args, **_kwargs: wrong_cleanup.append(args))

    try:
        with pytest.raises(RepairControlError, match="authority changed"):
            await orch.repair_direct("engineer", "Repair", request, on_event=observe)
        assert len(calls) == 1
        assert wrong_cleanup == []
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()


async def test_formatter_journal_failure_stops_before_another_model_request(tmp_path, monkeypatch):
    from henchman.core.operation_recovery import OperationRecoveryError
    from henchman.core.runtime_operations import current_operation_run
    from henchman.tools import formatting

    script = [("edit", "edit_file", {"path": "target.py", "old_str": "a - b", "new_str": "a + b"}), None]
    orch, provider, service, request, calls, _ = await make_runtime(tmp_path, monkeypatch, "openai_compat", script)
    actual = formatting.format_python_files
    failures = []

    async def unavailable_during_format(paths, *, cwd):
        run = current_operation_run()
        assert run is not None
        original = run.journal.report

        def unavailable():
            failures.append(True)
            raise OperationRecoveryError("storage_unavailable")

        monkeypatch.setattr(run.journal, "report", unavailable)
        try:
            return await actual(paths, cwd=cwd)
        finally:
            monkeypatch.setattr(run.journal, "report", original)

    monkeypatch.setattr(formatting, "format_python_files", unavailable_during_format)
    try:
        with pytest.raises(OperationRecoveryError, match="storage_unavailable"):
            await orch.repair_direct("engineer", "Repair", request)
        assert len(calls) == 1 and failures
        assert "a + b" in (tmp_path / "target.py").read_text()
        records = orch.operation_runtime.report().records
        assert next(item for item in records if item.tool_name == "edit_file").state == "outcome_unknown"
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
    finally:
        await orch.aclose()
        await provider._client.close()
