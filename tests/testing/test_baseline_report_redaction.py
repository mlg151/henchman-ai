"""Evaluation report evidence uses the runtime credential policy before JSON."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evals import baseline_runs

from henchman.utils.evidence_redaction import EvidenceRedactor


def report(error: str) -> dict[str, Any]:
    records = [baseline_runs.RunRecord(
        case_id="syntax-fix", run_index=1, profile="engineer", outcome="runtime_error",
        duration_ms=12.5, tokens_in=1, tokens_out=None, task_verified=False, error=error,
    )]
    return baseline_runs.build_report(
        cohort="local", requested={"cases": ["syntax-fix"], "runs_per_case": 1,
            "timeout": 120.0, "max_iterations": 10, "provider": "mock", "model": "mock-model"},
        summary=baseline_runs.summarize_runs(records), records=records,
    )


@pytest.mark.parametrize("secret", ["x", "1", "xy7!", 'q"\\\nΩ'])
def test_short_and_escaped_credentials_are_projected_before_serialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, secret: str,
) -> None:
    monkeypatch.setenv("BASELINE_REPORT_API_KEY", secret)
    source = report(f"Request failed: {secret}")
    before = deepcopy(source)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source)
    stored = json.loads(path.read_text())
    assert stored["runs"][0]["error"] == "Request failed: [REDACTED]"
    assert stored["budget"] == {"planned_runs": 1, "executed_runs": 1}
    assert stored["runs"][0]["tokens_in"] == 1
    assert stored["runs"][0]["tokens_out"] is None
    assert stored["runs"][0]["duration_ms"] == 12.5
    assert stored["runs"][0]["task_verified"] is False
    assert source == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("secret", ["error", "runtime_error", "local", "1"])
def test_fixed_keys_counts_and_outcome_enums_remain_machine_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, secret: str,
) -> None:
    monkeypatch.setenv("BASELINE_REPORT_API_KEY", secret)
    source = report(secret)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source)
    stored = json.loads(path.read_text())
    assert stored["kind"] == "baseline_repeat_runs"
    assert stored["cohort"] == "local"
    assert stored["cost"] == {"source": "local", "amount_usd": 0.0, "billing": "none"}
    assert stored["summary"]["outcome_counts"]["runtime_error"] == 1
    assert stored["summary"]["usage"] == {"tokens_in": 1, "tokens_out": None, "available": True}
    assert stored["runs"][0]["outcome"] == "runtime_error"
    assert stored["runs"][0]["error"] == "[REDACTED]"


@pytest.mark.parametrize("diagnostic", [
    "Authorization: Bearer header-canary\nregular diagnostic",
    "  Proxy-Authorization : opaque header-canary\nregular diagnostic",
    "Cookie: session=header-canary\nregular diagnostic",
    "Authorization without colon: header-canary",
    "prefix Authorization: header-canary",
])
def test_header_projection_matches_existing_policy_exactly(tmp_path: Path, diagnostic: str) -> None:
    source = report(diagnostic)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source)
    stored = json.loads(path.read_text())
    assert stored["runs"][0]["error"] == EvidenceRedactor().text(diagnostic)
    assert source["runs"][0]["error"] == diagnostic


def test_marked_fields_are_collected_before_echoes_without_mutating_report(tmp_path: Path) -> None:
    source = report("Failure: marked-short")
    source["diagnostic_metadata"] = {"api_key": "marked-short", "echo": "marked-short"}
    before = deepcopy(source)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source)
    stored = json.loads(path.read_text())
    assert stored["runs"][0]["error"] == "Failure: [REDACTED]"
    assert stored["diagnostic_metadata"] == {"api_key": "[REDACTED]", "echo": "[REDACTED]"}
    assert source == before


def test_explicit_policy_retains_rotated_values_across_report_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = EvidenceRedactor(["old-explicit"])
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, report("old-explicit"), evidence_redactor=policy)
    monkeypatch.setenv("BASELINE_REPORT_API_KEY", "new-env")
    baseline_runs.write_report(path, report("new-env"), evidence_redactor=policy)
    monkeypatch.delenv("BASELINE_REPORT_API_KEY")
    policy.register_secret("new-explicit")
    baseline_runs.write_report(path, report("old-explicit/new-env/new-explicit"), evidence_redactor=policy)
    stored = json.loads(path.read_text())
    assert stored["runs"][0]["error"] == "[REDACTED]/[REDACTED]/[REDACTED]"


def test_cli_learns_actual_provider_key_before_runs_and_refreshes_before_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SimpleNamespace(name="mock", default_model="fixture", api_key="old-provider")
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: provider)

    async def run(_case_id: str, **_kwargs: Any) -> list[baseline_runs.RunRecord]:
        provider.api_key = "rotated-provider"
        return [baseline_runs.RunRecord(
            case_id="syntax-fix", run_index=1, profile="engineer", outcome="runtime_error",
            duration_ms=1.0, tokens_in=None, tokens_out=None, task_verified=False,
            error="old-provider/rotated-provider",
        )]

    monkeypatch.setattr(baseline_runs, "run_case_repeated", run)
    path = tmp_path / "report.json"
    assert baseline_runs.main(["--cases", "syntax-fix", "--runs", "1", "--report", str(path)]) == 1
    assert json.loads(path.read_text())["runs"][0]["error"] == "[REDACTED]/[REDACTED]"


def test_real_write_failure_remains_visible_and_preserves_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "report.json"
    path.write_text("previous complete report")
    failure = OSError("test publication failed")

    def fail_replace(*_args: Any) -> None:
        raise failure

    monkeypatch.setattr(baseline_runs.os, "replace", fail_replace)
    with pytest.raises(OSError) as raised:
        baseline_runs.write_report(path, report("failure"))
    assert raised.value is failure
    assert path.read_text() == "previous complete report"
    assert list(tmp_path.iterdir()) == [path]


def test_escaped_echoes_and_untrusted_labels_are_projected(tmp_path: Path) -> None:
    secret = 'q"\\\nΩ'
    policy = EvidenceRedactor([secret])
    source = report(json.dumps(secret, ensure_ascii=True)[1:-1])
    source["requested"]["provider"] = secret
    source["requested"]["model"] = secret
    source["runs"][0]["profile"] = secret
    before = deepcopy(source)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source, evidence_redactor=policy)
    stored = json.loads(path.read_text())
    assert stored["requested"]["provider"] == "[REDACTED]"
    assert stored["requested"]["model"] == "[REDACTED]"
    assert stored["runs"][0]["profile"] == "[REDACTED]"
    assert stored["runs"][0]["error"] == "[REDACTED]"
    assert source == before


def test_cli_retains_environment_values_removed_during_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BASELINE_REPORT_API_KEY", "old-env")
    provider = SimpleNamespace(name="mock", default_model="fixture", api_key="")
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: provider)

    async def run(_case_id: str, **_kwargs: Any) -> list[baseline_runs.RunRecord]:
        monkeypatch.delenv("BASELINE_REPORT_API_KEY")
        monkeypatch.setenv("BASELINE_REPORT_ACCESS_KEY", "new-env")
        return [baseline_runs.RunRecord(
            case_id="syntax-fix", run_index=1, profile="engineer", outcome="runtime_error",
            duration_ms=1.0, tokens_in=None, tokens_out=None, task_verified=False,
            error="old-env/new-env",
        )]

    monkeypatch.setattr(baseline_runs, "run_case_repeated", run)
    path = tmp_path / "report.json"
    assert baseline_runs.main(["--cases", "syntax-fix", "--runs", "1", "--report", str(path)]) == 1
    assert json.loads(path.read_text())["runs"][0]["error"] == "[REDACTED]/[REDACTED]"


@pytest.mark.parametrize("location", [
    ("kind",), ("generated_at",), ("cohort",), ("requested", "cases"),
    ("cost", "source"), ("cost", "billing"), ("runs", 0, "case_id"), ("runs", 0, "outcome"),
])
def test_only_validated_identities_can_bypass_credential_projection(
    tmp_path: Path, location: tuple[str | int, ...],
) -> None:
    secret = "identity-private-canary"
    policy = EvidenceRedactor([secret])
    source = report("ordinary failure")
    target: Any = source
    for field in location[:-1]:
        target = target[field]
    target[location[-1]] = [secret] if location == ("requested", "cases") else secret
    before = deepcopy(source)
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source, evidence_redactor=policy)
    assert secret not in path.read_text()
    assert source == before


@pytest.mark.parametrize("credential_source", ["provider", "environment"])
def test_cli_captures_credential_rotation_at_each_attempt_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, credential_source: str,
) -> None:
    provider = SimpleNamespace(name="mock", default_model="fixture", api_key="initial-private-canary")
    monkeypatch.setenv("BASELINE_REPORT_API_KEY", "initial-private-canary")
    monkeypatch.setattr(baseline_runs, "get_eval_provider", lambda: provider)

    async def attempt(
        case_id: str, profile: str, provider: Any, run_index: int, *_args: Any,
    ) -> baseline_runs.RunRecord:
        value = f"attempt-{run_index}-private-canary"
        if credential_source == "provider":
            provider.api_key = value
        else:
            monkeypatch.setenv("BASELINE_REPORT_API_KEY", value)
        return baseline_runs.RunRecord(
            case_id=case_id, run_index=run_index, profile=profile, outcome="runtime_error",
            duration_ms=1.0, tokens_in=None, tokens_out=None, task_verified=False,
            error=f"initial-private-canary/{value}",
        )

    monkeypatch.setattr(baseline_runs, "_run_once", attempt)
    path = tmp_path / "report.json"
    assert baseline_runs.main(["--cases", "syntax-fix", "--runs", "3", "--report", str(path)]) == 1
    stored = json.loads(path.read_text())
    assert [run["error"] for run in stored["runs"]] == ["[REDACTED]/[REDACTED]"] * 3


def test_mixed_identity_lists_preserve_only_known_entries(tmp_path: Path) -> None:
    secret = "unknown-private-canary"
    policy = EvidenceRedactor([secret, "syntax-fix", "runtime_error"])
    source = report("ordinary failure")
    source["requested"]["cases"] = ["syntax-fix", secret]
    source["runs"].append({**source["runs"][0], "case_id": secret, "outcome": secret})
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source, evidence_redactor=policy)
    stored = json.loads(path.read_text())
    assert stored["requested"]["cases"] == ["syntax-fix", "[REDACTED]"]
    assert stored["runs"][0]["case_id"] == "syntax-fix"
    assert stored["runs"][0]["outcome"] == "runtime_error"
    assert stored["runs"][1]["case_id"] == "[REDACTED]"
    assert stored["runs"][1]["outcome"] == "[REDACTED]"


@pytest.mark.parametrize("timestamp", [
    "2026-11-07T12:34:56+00:00", "2026-11-07T12:34:56.123456+00:00",
])
def test_canonical_report_timestamps_remain_protocol_identity(tmp_path: Path, timestamp: str) -> None:
    source = report("ordinary failure")
    source["generated_at"] = timestamp
    path = tmp_path / "report.json"
    baseline_runs.write_report(path, source, evidence_redactor=EvidenceRedactor(["1"]))
    assert json.loads(path.read_text())["generated_at"] == timestamp
