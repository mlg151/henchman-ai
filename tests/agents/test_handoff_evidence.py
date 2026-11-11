"""Generated delegation notes project evidence without editing caller inputs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from henchman.agents.delegation import (
    DelegationRunner,
    _add_to_shared_context,
    _finalize_execution,
    _populate_execution_params,
)
from henchman.agents.orchestrator_types import CompletionStatus, DelegationParams
from henchman.config.schema import Settings
from henchman.utils.evidence_redaction import EvidenceRedactor


def runner(shared, secret="configured-handoff-secret"):
    return DelegationRunner(
        pool=None, settings=Settings(providers={"deepseek": {"api_key": secret}}), shared_context=shared,
        metrics=None, run_agent_loop=None, assess_completion=None,
    )


def test_generated_handoff_does_not_echo_configured_credential_to_next_brief():
    secret = "configured-handoff-secret"
    shared = []
    _add_to_shared_context(shared, "engineer", f"Observed failure with credential {secret}", {})
    source = deepcopy(shared)
    controller = runner(shared, secret)
    original = {"background": "Preserve explicit caller context", "files": ["target.py"]}
    before = deepcopy(original)
    prepared = controller._prepare_delegation_context("engineer", original, task="failure")
    assert secret not in prepared["background"] and "[REDACTED]" in prepared["background"]
    assert shared == source and original == before


def test_new_shared_summary_projects_before_storage_cut_without_mutating_source():
    secret = "cross-boundary-private-value"
    summary = "x" * 790 + secret + " after"
    parsed = {"files_modified": f"path/{secret}/file.py"}
    before = deepcopy(parsed)
    shared = []
    _add_to_shared_context(shared, "engineer", summary, parsed, redactor=EvidenceRedactor([secret]))
    assert "cross-boun" not in shared[0]["summary"]
    assert "[REDACTED]" in shared[0]["summary"] and len(shared[0]["summary"]) <= 800
    assert secret not in shared[0]["files_modified"]
    assert summary.endswith(secret + " after") and parsed == before


@pytest.mark.parametrize("clipped", [False, True])
def test_rotation_projects_legacy_summary_before_short_presentation_cut(clipped):
    secret = "rotated-private-" + "s" * (700 if clipped else 40)
    original = "x" * 180 + secret + " trailing"
    # Emulate an already persisted/generated legacy 800-character snapshot.
    shared = [{"agent": "engineer", "summary": original[:800], "files_modified": "", "timestamp": "old"}]
    source = deepcopy(shared)
    controller = runner(shared, "previous-provider-secret")
    controller._prepare_delegation_context("engineer", {}, task="initial")
    controller.settings.providers.deepseek["api_key"] = secret
    prepared = controller._prepare_delegation_context("engineer", {}, task="later")
    assert "rotated-private-" not in prepared["background"]
    assert "[REDACTED]" in prepared["background"]
    assert shared == source


def test_reference_rotation_preserves_old_credentials_and_original_caller_context(monkeypatch):
    old, new = "previous-env-handoff-secret", "replacement-env-handoff-secret"
    monkeypatch.setenv("PRIVATE_HANDOFF_CREDENTIAL", old)
    shared = [{"agent": "engineer", "summary": f"{old} and {new}", "files_modified": ""}]
    source = deepcopy(shared)
    controller = runner(shared, "${PRIVATE_HANDOFF_CREDENTIAL}")
    first = controller._prepare_delegation_context("engineer", {}, task=old)
    assert old not in first["background"] and new in first["background"]
    monkeypatch.setenv("PRIVATE_HANDOFF_CREDENTIAL", new)
    caller = {"background": f"Explicit caller input {old}", "acceptance": [new]}
    prepared = controller._prepare_delegation_context("engineer", caller, task=old)
    generated = prepared["background"].split("### Prior agent work\n", 1)[1]
    assert old not in generated and new not in generated
    assert prepared["background"].startswith(caller["background"])
    assert caller == {"background": f"Explicit caller input {old}", "acceptance": [new]}
    assert shared == source


def test_generated_failure_note_projects_quotation_but_preserves_ledger_and_caller():
    secret = "configured-handoff-secret"
    controller = runner([])
    prior = SimpleNamespace(agent="engineer", status="FAILED", task=f"Previously used {secret}")
    controller.ledger = SimpleNamespace(delegations=[prior])
    caller = {"background": "Current explicit instructions"}
    prepared = controller._prepare_delegation_context("engineer", caller, task=secret)
    assert secret not in prepared["background"] and "[REDACTED]" in prepared["background"]
    assert prior.task == f"Previously used {secret}" and caller["background"] == "Current explicit instructions"


def test_auth_headers_and_display_role_are_projected_without_mutating_prior_record():
    shared = [{"agent": "configured-handoff-secret", "summary": "Authorization: Bearer unmarked-header-value",
               "files_modified": ""}]
    source = deepcopy(shared)
    prepared = runner(shared)._prepare_delegation_context("engineer", {}, task="review")
    assert "configured-handoff-secret" not in prepared["background"]
    assert "unmarked-header-value" not in prepared["background"]
    assert shared == source


@pytest.mark.asyncio
async def test_finalization_registers_actual_specialist_key_without_rewriting_execution_result():
    secret = "actual-specialist-handoff-secret"
    controller = runner([])
    agent = SimpleNamespace(provider=SimpleNamespace(api_key=secret))
    summary = f"Completed inspection with {secret}"
    parsed = {"files_modified": f"path/{secret}.py"}
    controller._process_delegation_results = lambda *_: (summary, parsed, CompletionStatus.RESPONDED)
    params = DelegationParams(target_role="engineer", task="unchanged", target_agent=agent)
    events = [event async for event in _finalize_execution(controller, params)]
    assert secret not in controller.shared_context[0]["summary"]
    assert secret not in controller.shared_context[0]["files_modified"]
    assert events[0].data["summary"] == summary and parsed["files_modified"] == f"path/{secret}.py"
    assert agent.provider.api_key == secret and params.task == "unchanged"


def test_preparation_registers_already_selected_specialist_before_injecting_history():
    secret = "new-target-provider-secret"
    shared = [{"agent": "engineer", "summary": f"Prior failure echoed {secret}", "files_modified": ""}]
    source = deepcopy(shared)
    controller = runner(shared)
    agent = SimpleNamespace(provider=SimpleNamespace(api_key=secret), messages=[])
    params = DelegationParams(target_role="engineer", task="Current exact task", brief={"background": "caller background"})
    before = deepcopy(params.brief)
    _populate_execution_params(controller, params, agent)
    assert secret not in params.full_task and "[REDACTED]" in params.full_task
    assert "Current exact task" in params.full_task and "caller background" in params.full_task
    assert params.task == "Current exact task" and params.brief == before and shared == source


def test_json_escaped_rotated_credential_prefix_is_masked_in_legacy_clipped_summary():
    import json

    secret = 'escaped-"private"-' + "s" * 700
    summary = ("x" * 180 + json.dumps(secret)[1:-1])[:800]
    shared = [{"agent": "engineer", "summary": summary, "files_modified": ""}]
    prepared = runner(shared, secret)._prepare_delegation_context("engineer", {}, task="review")
    assert "escaped-" not in prepared["background"] and "[REDACTED]" in prepared["background"]
    assert shared[0]["summary"] == summary


def test_complete_ordinary_words_are_not_treated_as_truncated_credential_prefixes():
    shared = []
    _add_to_shared_context(shared, "engineer", "repaired", {}, redactor=EvidenceRedactor(["different-secret"]))
    assert shared[0]["summary"] == "repaired"
    prepared = runner(shared, "different-secret")._prepare_delegation_context("engineer", {}, task="review")
    assert prepared["background"].endswith("repaired")


@pytest.mark.parametrize("escaped", [False, True])
@pytest.mark.parametrize("old_at_start", [False, True])
def test_overlapping_retained_credential_cannot_expose_rotated_clipped_prefix(escaped, old_at_start):
    import json

    old = "previous-known-value"
    prefix = old + "-private-prefix-" if old_at_start else "private-prefix-" + old
    secret = prefix + ('-"suffix"' if escaped else "-suffix") + "z" * 800
    value = json.dumps(secret)[1:-1] if escaped else secret
    shared = [{"agent": "engineer", "summary": ("x" * 180 + value)[:800], "files_modified": ""}]
    before = deepcopy(shared)
    controller = runner(shared, old)
    controller._prepare_delegation_context("engineer", {}, task="initial")
    controller.settings.providers.deepseek["api_key"] = secret
    prepared = controller._prepare_delegation_context("engineer", {}, task="current")
    assert "private-" not in prepared["background"]
    assert "[REDACTED]" in prepared["background"]
    assert shared == before
