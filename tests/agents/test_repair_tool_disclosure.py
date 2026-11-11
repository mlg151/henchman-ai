"""Repair model payloads expose only the captured foreground file tools."""

import asyncio
import subprocess
import sys
from types import SimpleNamespace

import pytest
from tests.e2e.test_bounded_repair import PROVIDERS, make_runtime

from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.tools.registry import ToolRegistry
from henchman.tools.repair_scope import RepairControlError, RepairScope, current_repair

FILES = {"read_file", "edit_file", "write_file"}
ALL = FILES | {"verify_plan_execution"}


def wire_names(payload):
    return {item.get("function", item)["name"] for item in payload["tools"]}


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_real_provider_wire_has_only_repair_file_tools_then_restores_direct_disclosure(
    tmp_path, monkeypatch, provider_name,
):
    script = [
        ("read", "read_file", {"path": "target.py"}),
        ("miss", "edit_file", {"path": "target.py", "old_str": "missing", "new_str": "ignored"}),
        ("edit", "edit_file", {"path": "target.py", "old_str": "a - b", "new_str": "a + b"}),
        ("write", "write_file", {"path": "target.py", "content": "def add(a, b):\n    return a + b\n"}),
        None,
        None,  # A separate ordinary direct run retains its usual catalog.
    ]
    orch, provider, service, request, calls, _ = await make_runtime(
        tmp_path, monkeypatch, provider_name, script,
    )
    held = {name: orch.tool_registry.get(name) for name in ALL}
    criteria = (tmp_path / "criteria.py").read_bytes()
    try:
        report = await orch.repair_direct("engineer", "Repair addition", request)
        assert report.status == "scoped_pass" and not report.task_verified
        assert len(calls) == 5
        assert all(wire_names(payload) == FILES for payload in calls)
        assert all(orch.tool_registry.get(name) is tool for name, tool in held.items())
        assert {item.name for item in orch.pool.get_agent("engineer").tool_registry.get_declarations()} == ALL
        records = orch.operation_runtime.report().records
        controller = [item for item in records if item.context.agent_id == "runtime:verification"]
        assert len(controller) == 2 and all(item.state == "completed" for item in controller)
        assert any(item.tool_name == "edit_file" and not item.result.success for item in records)
        assert service.get_plan(request.plan_id).last_repair == report.to_dict()
        assert (tmp_path / "criteria.py").read_bytes() == criteria
        oracle = subprocess.run([sys.executable, "-B", "criteria.py"], cwd=tmp_path,
                                capture_output=True, timeout=20)
        assert oracle.returncode == 0, oracle.stderr.decode()
        async for _event in orch.run_direct("engineer", "Describe the result"):
            pass
        assert len(calls) == 6 and wire_names(calls[-1]) == ALL
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.mark.parametrize("provider_name", PROVIDERS)
async def test_hallucinated_current_plan_verification_still_stops_without_retry(
    tmp_path, monkeypatch, provider_name,
):
    script = [None]
    orch, provider, service, request, calls, _ = await make_runtime(
        tmp_path, monkeypatch, provider_name, script,
    )
    script[0] = ("forbidden", "verify_plan_execution", {"action": "verify", "plan_id": request.plan_id})
    before = (tmp_path / "target.py").read_bytes()
    try:
        with pytest.raises(RepairControlError, match="unsupported"):
            await orch.repair_direct("engineer", "Repair addition", request)
        assert len(calls) == 1 and wire_names(calls[0]) == FILES
        assert (tmp_path / "target.py").read_bytes() == before
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
        records = orch.operation_runtime.report().records
        controller = [item for item in records if item.context.agent_id == "runtime:verification"]
        assert len(controller) == 1  # Only the runtime's initial check occurred.
        assert {item.name for item in orch.pool.get_agent("engineer").tool_registry.get_declarations()} == ALL
    finally:
        await orch.aclose()
        await provider._client.close()


@pytest.fixture
def held_scope(tmp_path):
    def capture():
        registry = ToolRegistry()
        tools = (ReadFileTool(), EditFileTool(), WriteFileTool(), VerifyPlanExecutionTool())
        for tool in tools:
            registry.register(tool)
        scope = RepairScope(SimpleNamespace(_current=lambda: None), root=tmp_path, tools=tools,
                            verifier=tools[-1], checks=(), validate=lambda: None)
        return registry, scope
    return capture


async def test_controller_phase_discloses_no_model_tools_without_unregistering(held_scope):
    registry, scope = held_scope()
    with scope.activate("verify"):
        assert registry.get_declarations() == []
        assert registry.get("verify_plan_execution") is scope.verifier
    assert {item.name for item in registry.get_declarations()} == ALL


@pytest.mark.parametrize("change", ["instance", "subclass", "method", "removed"])
async def test_mutated_held_file_implementation_is_fatal_before_disclosure(held_scope, monkeypatch, change):
    registry, scope = held_scope()
    original = registry.get("edit_file")
    if change in {"instance", "subclass", "removed"}:
        registry.unregister("edit_file")
        if change != "removed":
            class Replacement(EditFileTool):
                pass
            registry.register(EditFileTool() if change == "instance" else Replacement())
    else:
        async def changed(**_kwargs):
            pytest.fail("Replacement implementation must never run")
        monkeypatch.setattr(original, "execute", changed)
    with scope.activate("repair"):
        with pytest.raises(RepairControlError, match="implementation"):
            registry.get_declarations()
        # A captured failure cannot be cleared by replacing the tool again.
        registry.unregister("edit_file")
        registry.register(original)
        with pytest.raises(RepairControlError):
            registry.get_declarations()


@pytest.mark.parametrize("phase", ["repair", "verify"])
async def test_held_authority_failure_is_preserved_before_any_declaration(held_scope, monkeypatch, phase):
    from henchman.core.operation_recovery import OperationRecoveryError

    registry, scope = held_scope()
    error = OperationRecoveryError("unresolved_operation")
    def unavailable():
        raise error
    scope.validate = unavailable
    monkeypatch.setattr(registry.get("read_file"), "to_declaration",
                        lambda: pytest.fail("Failed authority disclosed a schema"))
    with scope.activate(phase), pytest.raises(OperationRecoveryError) as caught:
        registry.get_declarations()
    assert caught.value is error


async def test_new_file_tool_is_not_an_implicit_repair_capability(held_scope):
    registry, scope = held_scope()
    del scope.tools["write_file"]  # The role did not hold this tool at capture.
    with scope.activate("repair"), pytest.raises(RepairControlError, match="implementation"):
        registry.get_declarations()


@pytest.mark.parametrize("state", ["closed", "failed", "other_owner", "missing_phase"])
async def test_unavailable_lease_cannot_publish_a_model_catalog(held_scope, state):
    registry, scope = held_scope()
    with scope.activate("repair"):
        if state == "closed":
            scope.active = False
        elif state == "failed":
            with pytest.raises(RepairControlError):
                scope.deny("retained authority failure")
        elif state == "missing_phase":
            scope.phase = None
        with pytest.raises(RepairControlError):
            if state == "other_owner":
                async def inherited():
                    return registry.get_declarations()
                await asyncio.create_task(inherited())
            else:
                registry.get_declarations()


async def test_cancelled_public_repair_restores_disclosure_and_closes_inherited_scope(tmp_path, monkeypatch):
    orch, provider, service, request, calls, _ = await make_runtime(
        tmp_path, monkeypatch, "openai_compat", [None],
    )
    scopes = []
    original = ToolRegistry.get_declarations
    def capture(self):
        scope = current_repair()
        if scope is not None:
            scopes.append(scope)
        return original(self)
    monkeypatch.setattr(ToolRegistry, "get_declarations", capture)
    entered = asyncio.Event()
    async def observe(event):
        if event.type.value == "content":
            entered.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(orch.repair_direct("engineer", "Repair", request, on_event=observe))
    ready = asyncio.create_task(entered.wait())
    try:
        done, _ = await asyncio.wait({task, ready}, return_when=asyncio.FIRST_COMPLETED,
                                     timeout=request.timeout_seconds + 10)
        if task in done:
            await task
            pytest.fail("Repair completed before the cancellation boundary")
        assert ready in done
        task.cancel("stop disclosed repair")
        with pytest.raises(asyncio.CancelledError, match="stop disclosed repair"):
            await task
        assert len(calls) == 1 and wire_names(calls[0]) == FILES
        assert scopes and all(not scope.active for scope in scopes)
        assert current_repair() is None
        assert not orch._public_run_active and not orch.pool._execution_claims
        assert service.get_plan(request.plan_id).last_repair["reason"] == "cancelled"
        assert {item.name for item in orch.pool.get_agent("engineer").tool_registry.get_declarations()} == ALL
        with scopes[-1].activate("repair"), pytest.raises(RepairControlError):
            orch.pool.get_agent("engineer").tool_registry.get_declarations()
    finally:
        if not task.done():
            task.cancel()
        ready.cancel()
        await asyncio.gather(task, ready, return_exceptions=True)
        await orch.aclose()
        await provider._client.close()


async def test_public_repair_implementation_mutation_stops_before_provider_payload(tmp_path, monkeypatch):
    orch, provider, service, request, calls, _ = await make_runtime(
        tmp_path, monkeypatch, "openai_compat", [],
    )
    original = ToolRegistry.get_declarations
    changed = []
    def mutate(self):
        scope = current_repair()
        if scope is not None and not changed:
            held = self.get("edit_file")
            async def replacement(**_kwargs):
                pytest.fail("Replacement must never dispatch")
            monkeypatch.setattr(held, "execute", replacement)
            changed.append(held)
        return original(self)
    monkeypatch.setattr(ToolRegistry, "get_declarations", mutate)
    try:
        with pytest.raises(RepairControlError, match="implementation"):
            await orch.repair_direct("engineer", "Repair", request)
        assert changed and calls == []
        assert service.get_plan(request.plan_id).last_repair["status"] == "incomplete"
        assert not orch._public_run_active and not orch.pool._execution_claims
    finally:
        await orch.aclose()
        await provider._client.close()
