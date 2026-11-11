"""Verification evidence never becomes credential-bearing executable storage."""

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from henchman.advanced.plans import PlanExecutionService
from henchman.utils.evidence_redaction import EvidenceRedactor

SECRET = "verification-canary-4d5718"


def index(root):
    return root / ".henchman/plans/verification.json"


@pytest.mark.parametrize("check", [
    {"kind": "command", "argv": ["fixture", SECRET]},
    {"kind": "file_contains", "path": "file", "text": SECRET},
    {"kind": "file_changed", "path": SECRET},
    {"kind": "command", "argv": ["fixture"], "inputs": [SECRET]},
    {"kind": "command", "argv": ["fixture"], "requirement_ids": [SECRET]},
])
def test_new_credential_specs_rejected_before_baseline_or_storage(tmp_path, monkeypatch, check):
    from henchman.advanced import plans

    monkeypatch.setenv("VERIFICATION_API_KEY", SECRET)
    def forbidden(*_args):
        pytest.fail("unsafe specifications reached baseline capture")
    monkeypatch.setattr(plans, "prepare_checks", forbidden)
    with pytest.raises(ValueError, match="credential") as error:
        PlanExecutionService(tmp_path).create_plan(steps=["check"], checks=[check])
    assert SECRET not in str(error.value)
    assert not index(tmp_path).exists()


async def test_safe_execution_and_projected_report_and_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("VERIFICATION_API_KEY", SECRET)
    monkeypatch.setenv("VERIFICATION_HEADER_VALUE", "unknown-header-canary")
    (tmp_path / "input").write_text("ordinary")
    service = PlanExecutionService(tmp_path)
    command = [sys.executable, "-c", "import os; print(os.environ['VERIFICATION_API_KEY']); print('Authorization: Bearer ' + os.environ['VERIFICATION_HEADER_VALUE'])"]
    plan = service.create_plan(title=SECRET, steps=["inspect " + SECRET], checks=[
        {"kind": "command", "argv": command, "inputs": ["input"]},
    ])
    assert SECRET not in plan.title + plan.steps[0].text
    service.complete_step(plan.plan_id, step=1, evidence=SECRET)
    report = await service.verify_plan(plan.plan_id)
    assert report["results"][0]["check"]["argv"] == command
    assert report["current_checks_passed"] is True
    assert SECRET not in json.dumps(report) + index(tmp_path).read_text()
    assert "unknown-header-canary" not in json.dumps(report) + index(tmp_path).read_text()
    assert service.verification_status(plan.plan_id)["status"] == "pass"


async def test_rotation_denies_replay_without_status_writes_then_sanitizes(tmp_path):
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture", SECRET]}])
    before = index(tmp_path).read_bytes()
    policy.register_secret(SECRET)
    restored = service.get_plan(plan.plan_id)
    assert restored.checks == ()
    assert restored.checks_unavailable["reason"] == "credential_sensitive"
    assert len(restored.checks_unavailable["spec_digest"]) == 64
    assert service.verification_status(plan.plan_id)["status"] == "unavailable"
    assert index(tmp_path).read_bytes() == before
    with pytest.raises(ValueError, match="unavailable"):
        await service.verify_plan(plan.plan_id)
    assert SECRET not in index(tmp_path).read_text()
    assert PlanExecutionService(tmp_path).get_plan(plan.plan_id).checks == ()


async def test_session_binding_sanitizes_and_keeps_rotation_live(tmp_path):
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool

    plan = PlanExecutionService(tmp_path).create_plan(steps=[SECRET], checks=[{"kind": "command", "argv": ["fixture", SECRET]}])
    policy = EvidenceRedactor([SECRET])
    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path, session_manager=SimpleNamespace(session_manager=SimpleNamespace(evidence_redactor=policy)))
    assert SECRET not in index(tmp_path).read_text()
    result = await tool.execute(action="verify", plan_id=plan.plan_id)
    assert not result.success and "unavailable" in result.content


async def test_capped_utf8_output_never_persists_partial_credential(tmp_path, monkeypatch):
    secret = "private-é-final"
    monkeypatch.setenv("VERIFICATION_API_KEY", secret)
    # The raw 64 KiB prefix ends inside the multibyte credential character.
    script = "import os; os.write(1, b'x'*(65536-9) + os.environ['VERIFICATION_API_KEY'].encode())"
    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": [sys.executable, "-c", script]}])
    report = await service.verify_plan(plan.plan_id)
    output = report["results"][0]["stdout"]
    assert "private-" not in output + index(tmp_path).read_text()
    assert report["results"][0]["stdout_truncated"] is True
    assert len(output.encode()) <= 65536


async def test_rotation_between_checks_stops_next_dispatch(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[
        {"kind": "command", "argv": ["first"]},
        {"kind": "command", "argv": ["second", SECRET]},
    ])
    calls = []
    async def run(_root, spec, **_kwargs):
        calls.append(spec.argv)
        policy.register_secret(SECRET)
        return {"passed": True}
    monkeypatch.setattr(acceptance_checks, "_command_result", run)
    with pytest.raises(ValueError, match="credential|unavailable"):
        await service.verify_plan(plan.plan_id)
    assert calls == [("first",)]
    assert SECRET not in index(tmp_path).read_text()


async def test_cancel_primary_survives_failed_evidence_save(tmp_path, monkeypatch):
    from henchman.advanced import plans

    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_exists", "path": "x"}])
    async def cancel(*_args, **_kwargs):
        raise asyncio.CancelledError("primary")
    def fail(*_args):
        raise OSError(SECRET)
    monkeypatch.setenv("VERIFICATION_API_KEY", SECRET)
    monkeypatch.setattr(plans, "run_checks", cancel)
    monkeypatch.setattr(service, "_save_report", fail)
    with pytest.raises(asyncio.CancelledError, match="primary") as error:
        await service.verify_plan(plan.plan_id)
    assert SECRET not in str(error.value.__notes__)


async def test_structural_words_and_hashes_are_not_rewritten_as_evidence(tmp_path):
    (tmp_path / "value").write_text("good")
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_exists", "path": "value"}])
    report = await service.verify_plan(plan.plan_id)
    for value in ("status", "finished", "current", "file_exists", report["run_id"], report["spec_digest"]):
        policy.register_secret(value)
    stored = service.get_plan(plan.plan_id)
    assert stored.checks == plan.checks
    assert stored.last_verification["status"] == "finished"
    assert stored.last_verification["run_id"] == report["run_id"]
    assert stored.last_verification["spec_digest"] == report["spec_digest"]
    assert service.verification_status(plan.plan_id)["status"] == "pass"


async def test_legacy_report_sanitation_preserves_hashes_and_read_only_status(tmp_path):
    (tmp_path / "value").write_text("good")
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(title=SECRET, steps=[SECRET], checks=[{"kind": "file_exists", "path": "value"}])
    report = await service.verify_plan(plan.plan_id)
    payload = json.loads(index(tmp_path).read_text())
    payload[0]["last_verification"]["results"][0]["stdout"] = SECRET
    payload[0]["last_verification"]["error"] = "Authorization: Bearer legacy-header-canary"
    index(tmp_path).write_text(json.dumps(payload))
    raw = index(tmp_path).read_bytes()
    policy.register_secret(SECRET)
    safe = service.get_plan(plan.plan_id)
    assert SECRET not in json.dumps(safe.to_dict())
    assert "legacy-header-canary" not in json.dumps(safe.to_dict())
    assert service.verification_status(plan.plan_id)["status"] == "pass"
    assert index(tmp_path).read_bytes() == raw
    service.sanitize_persisted_evidence()
    assert SECRET not in index(tmp_path).read_text()
    assert "legacy-header-canary" not in index(tmp_path).read_text()
    assert safe.last_verification["spec_digest"] == report["spec_digest"]
    assert list(index(tmp_path).parent.glob("tmp*")) == []


async def test_newly_secret_input_contents_revoke_proof_without_writing(tmp_path):
    (tmp_path / "value").write_text(SECRET)
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_exists", "path": "value"}])
    await service.verify_plan(plan.plan_id)
    assert service.verification_status(plan.plan_id)["status"] == "pass"
    raw = index(tmp_path).read_bytes()
    policy.register_secret(SECRET)
    assert service.verification_status(plan.plan_id)["status"] == "unverified"
    assert index(tmp_path).read_bytes() == raw


def test_settings_credentials_reject_persistence_without_changing_config(tmp_path):
    settings = tmp_path / ".henchman/settings.yaml"
    settings.parent.mkdir()
    text = "providers:\n  deepseek:\n    api_key: " + SECRET + "\n"
    settings.write_text(text)
    with pytest.raises(ValueError, match="credential"):
        PlanExecutionService(tmp_path).create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture", SECRET]}])
    assert settings.read_text() == text
    assert not index(tmp_path).exists()


@pytest.mark.parametrize("failure", [OSError, "lock_timeout"])
async def test_binding_failure_is_local_and_value_free(tmp_path, monkeypatch, failure):
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
    from henchman.utils.file_lock import LockTimeoutError

    def fail(_self):
        if failure == "lock_timeout":
            raise LockTimeoutError(SECRET, 0.01)
        raise failure(SECRET)
    monkeypatch.setattr(PlanExecutionService, "sanitize_persisted_evidence", fail)
    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path)
    result = await tool.execute(action="list")
    assert not result.success and "sanitation failed" in result.content
    assert SECRET not in result.content


def test_unavailable_marker_cannot_reactivate_preview_as_checks(tmp_path):
    service = PlanExecutionService(tmp_path)
    service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture"]}])
    records = json.loads(index(tmp_path).read_text())
    records[0]["checks_unavailable"] = {"reason": "credential_sensitive", "spec_digest": "a" * 64}
    index(tmp_path).write_text(json.dumps(records))
    with pytest.raises(ValueError, match="unavailable"):
        service.list_plans()


@pytest.mark.parametrize("field", ["plan_id", "created_at", "updated_at"])
def test_unvalidated_record_identities_cannot_hide_credentials(tmp_path, field):
    service = PlanExecutionService(tmp_path, redactor=EvidenceRedactor([SECRET]))
    service.create_plan(steps=["check"])
    payload = json.loads(index(tmp_path).read_text())
    payload[0][field] = SECRET
    index(tmp_path).write_text(json.dumps(payload))
    with pytest.raises(ValueError) as error:
        service.list_plans()
    assert SECRET not in str(error.value)


async def test_redacted_untrusted_provenance_cannot_claim_current_pass(tmp_path):
    (tmp_path / "value").write_text("good")
    service = PlanExecutionService(tmp_path, redactor=EvidenceRedactor([SECRET]))
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_exists", "path": "value"}])
    await service.verify_plan(plan.plan_id)
    payload = json.loads(index(tmp_path).read_text())
    payload[0]["last_verification"]["run_id"] = SECRET
    index(tmp_path).write_text(json.dumps(payload))
    assert service.verification_status(plan.plan_id)["status"] == "unverified"


async def test_mcp_credentials_registered_after_binding_block_saved_replay(tmp_path):
    from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool

    policies = []
    manager = SimpleNamespace(register_evidence=policies.append)
    tool = VerifyPlanExecutionTool()
    tool.bind_runtime(project_root=tmp_path, mcp_manager=manager)
    result = await tool.execute(action="create", steps=["check"], checks=[{"kind": "command", "argv": ["fixture", SECRET]}])
    assert result.success
    plan, = PlanExecutionService(tmp_path).list_plans()
    policies[0].register_secret(SECRET)
    result = await tool.execute(action="verify", plan_id=plan.plan_id)
    assert not result.success and "unavailable" in result.content
    assert SECRET not in index(tmp_path).read_text()


def test_sanitation_failure_keeps_original_and_only_projects_owned_temporary(tmp_path, monkeypatch):
    from henchman.advanced import plans

    service = PlanExecutionService(tmp_path, redactor=EvidenceRedactor())
    service.create_plan(steps=[SECRET])
    original = index(tmp_path).read_bytes()
    service._policy.register_secret(SECRET)
    def fail(source, _destination):
        assert SECRET not in Path(source).read_text()
        raise OSError("replacement failed")
    monkeypatch.setattr(plans.os, "replace", fail)
    with pytest.raises(OSError, match="replacement failed"):
        service.sanitize_persisted_evidence()
    assert index(tmp_path).read_bytes() == original
    assert {path.name for path in index(tmp_path).parent.iterdir()} <= {"verification.json", "verification.lock"}


async def test_exception_evidence_projects_before_its_capture_cutoff(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    policy = EvidenceRedactor([SECRET])
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture"]}])
    async def fail(*_args):
        raise OSError("x" * 4090 + SECRET)
    monkeypatch.setattr(acceptance_checks, "_command_result", fail)
    report = await service.verify_plan(plan.plan_id)
    assert "verifi" not in report["results"][0]["error"]
    assert SECRET not in index(tmp_path).read_text()


async def test_new_config_credential_masks_an_already_cut_exception_prefix(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    service = PlanExecutionService(tmp_path)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture"]}])
    async def fail(*_args):
        (tmp_path / ".henchman/settings.yaml").write_text("providers:\n  deepseek:\n    api_key: " + SECRET)
        raise OSError("x" * 4090 + SECRET)
    monkeypatch.setattr(acceptance_checks, "_command_result", fail)
    report = await service.verify_plan(plan.plan_id)
    stored = json.loads(index(tmp_path).read_text())[0]["last_verification"]
    assert "verifi" not in report["results"][0]["error"] + stored["results"][0]["error"]
    assert SECRET not in index(tmp_path).read_text()


@pytest.mark.parametrize("executable", [False, True])
def test_rotation_at_persistence_projects_return_or_rejects_new_checks(tmp_path, monkeypatch, executable):
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    original = service._persist_records
    def rotate(**kwargs):
        policy.register_secret(SECRET)
        original(**kwargs)
    monkeypatch.setattr(service, "_persist_records", rotate)
    if executable:
        with pytest.raises(ValueError, match="credential"):
            service.create_plan(steps=["check"], checks=[{"kind": "command", "argv": ["fixture", SECRET]}])
        assert not index(tmp_path).exists()
    else:
        plan = service.create_plan(title=SECRET, steps=[SECRET])
        assert SECRET not in json.dumps(plan.to_dict()) + index(tmp_path).read_text()


def test_baseline_error_projects_shared_credentials_before_cutoff(tmp_path, monkeypatch):
    from henchman.advanced import acceptance_checks

    policy = EvidenceRedactor()
    policy.register_secret(SECRET)
    def fail(_path):
        raise OSError("x" * 4090 + SECRET)
    monkeypatch.setattr(acceptance_checks, "_read_file", fail)
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_changed", "path": "value.txt"}])
    assert "verifi" not in plan.checks[0].baseline_error
    assert "verifi" not in json.loads(index(tmp_path).read_text())[0]["checks"][0]["baseline_error"]


def test_legacy_baseline_error_cutoff_is_unavailable_after_rotation(tmp_path):
    policy = EvidenceRedactor()
    service = PlanExecutionService(tmp_path, redactor=policy)
    plan = service.create_plan(steps=["check"], checks=[{"kind": "file_changed", "path": "value.txt"}])
    saved = json.loads(index(tmp_path).read_text())
    saved[0]["checks"][0]["baseline_error"] = "x" * 4090 + SECRET[:6]
    index(tmp_path).write_text(json.dumps(saved))
    policy.register_secret(SECRET)
    assert service.verification_status(plan.plan_id)["status"] == "unavailable"
    service.sanitize_persisted_evidence()
    assert SECRET[:6] not in json.dumps(json.loads(index(tmp_path).read_text())[0]["checks"])
