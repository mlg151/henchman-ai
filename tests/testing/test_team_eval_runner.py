"""The explicit live-team runner preserves reports, limits and credentials."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from evals import run_team

from henchman.config.schema import Settings


@pytest.fixture
def experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.chdir(tmp_path)
    settings = Settings.model_validate({
        "providers": {"openrouter": {"api_key": "private-config-key", "model": "saved-model"}},
        "context": {"max_tokens": 8192, "compaction_threshold": 0.5},
    })
    provider = SimpleNamespace(name="openrouter", default_model="selected-model",
                               _client=SimpleNamespace(close=AsyncMock()))
    specialist = SimpleNamespace(name="openrouter", default_model="specialist-model",
                                 _client=SimpleNamespace(close=AsyncMock()))
    state = SimpleNamespace(settings=settings, provider=provider, specialist=specialist,
                            constructions=[], rigs=[], success=True, cleanup_error=None)
    monkeypatch.setattr(run_team, "load_settings", lambda **_kwargs: settings)

    def construct(providers: Any, **kwargs: Any) -> Any:
        state.constructions.append((providers, kwargs))
        return provider

    monkeypatch.setattr(run_team, "create_configured_provider", construct)

    class Rig:
        def __init__(self, **kwargs: Any) -> None:
            state.rigs.append(self)
            self.options = kwargs
            self.original = Path.cwd()
            self.profile_metadata = {"profile": "team", "scope": "orchestrator",
                                     "roles": {"tech_lead": {"model": "selected-model"}}}
            self.orchestrator = SimpleNamespace(pool=SimpleNamespace(_agents={
                "tech_lead": SimpleNamespace(provider=provider),
                "engineer": SimpleNamespace(provider=specialist),
                "explorer": SimpleNamespace(provider=specialist),
            }))

        @property
        def providers(self) -> list[Any]:
            return [provider, *(agent.provider for agent in self.orchestrator.pool._agents.values())]

        def setup(self, _name: str) -> None:
            state.setup_name = _name
            workspace = tmp_path / "workspace"
            workspace.mkdir()
            monkeypatch.chdir(workspace)

        def cleanup(self) -> None:
            monkeypatch.chdir(self.original)
            if state.cleanup_error is not None:
                raise state.cleanup_error

    async def scenario(rig: Any, **kwargs: Any) -> dict[str, Any]:
        state.run_kwargs = kwargs
        assert Path.cwd() == tmp_path / "workspace"
        assert rig.options["profile"] == "team"
        return {"scenario": "team_python_workflow", "version": 1,
                "success": state.success, "task_verified": False, "checks": {"behavior": True}}

    monkeypatch.setattr(run_team, "EvalTestRig", Rig)
    monkeypatch.setattr(run_team, "run_team_python_workflow", scenario)
    return state


def test_saved_settings_selection_limits_and_report_survive_temporary_cwd(
    experiment: SimpleNamespace, tmp_path: Path,
) -> None:
    before = experiment.settings.model_dump()
    code = run_team.main([
        "--model", "vendor/coder", "--context-length", "700000", "--max-iterations", "12",
        "--timeout", "120", "--report", "result.json",
    ])
    assert code == 0
    report = json.loads((tmp_path / "result.json").read_text())
    assert report["success"] is True and report["task_verified"] is False
    assert report["result"]["checks"]["behavior"] is True
    assert report["usage"] is None and report["cost"] is None
    assert report["requested"]["provider"] == "openrouter"
    assert report["requested"]["context_length"] == 700000
    assert experiment.run_kwargs == {"max_iterations": 12, "timeout": 120.0}
    constructed = experiment.constructions[0]
    assert constructed[1] == {"provider_name": "openrouter", "model": "vendor/coder"}
    options = experiment.rigs[0].options
    assert options["settings"].context.max_tokens == 700000
    assert options["settings"].context.compaction_threshold == 0.5
    assert experiment.settings.model_dump() == before
    assert Path.cwd() == tmp_path
    experiment.provider._client.close.assert_awaited_once()
    experiment.specialist._client.close.assert_awaited_once()
    assert "private-config-key" not in json.dumps(report)


def test_omitted_context_uses_saved_policy(experiment: SimpleNamespace) -> None:
    assert run_team.main(["--provider", "ollama", "--report", "result.json"]) == 0
    assert experiment.rigs[0].options["settings"].context.max_tokens == 8192
    assert experiment.constructions[0][1] == {"provider_name": "ollama", "model": None}


def test_package_scenario_selection_preserves_runtime_limits_and_report(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def package(rig: Any, **kwargs: Any) -> dict[str, Any]:
        assert rig.options["profile"] == "team"
        assert kwargs == {"max_iterations": 9, "timeout": 90.0}
        return {"scenario": "team_python_package", "success": True, "task_verified": False}

    monkeypatch.setattr(run_team, "run_team_python_package", package, raising=False)
    assert run_team.main([
        "--scenario", "package", "--max-iterations", "9", "--timeout", "90",
        "--report", "package.json",
    ]) == 0
    report = json.loads((tmp_path / "package.json").read_text())
    assert report["requested"]["scenario"] == "package"
    assert report["result"]["scenario"] == "team_python_package"
    assert experiment.setup_name == "team-python-package"
    experiment.provider._client.close.assert_awaited_once()
    experiment.specialist._client.close.assert_awaited_once()


def test_unknown_scenario_fails_before_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_team, "load_settings", lambda **_kw: pytest.fail("loaded settings"))
    with pytest.raises(SystemExit) as outcome:
        run_team.main(["--scenario", "unknown", "--report", "unused.json"])
    assert outcome.value.code == 2


@pytest.mark.parametrize(("option", "value"), [
    ("--context-length", "0"), ("--context-length", "-1"), ("--context-length", "1.5"),
    ("--max-iterations", "-1"), ("--timeout", "0"), ("--timeout", "nan"),
    ("--timeout", "inf"),
])
def test_invalid_limits_fail_before_configuration_or_provider_lookup(
    monkeypatch: pytest.MonkeyPatch, option: str, value: str,
) -> None:
    def forbidden(**_kwargs: Any) -> None:
        pytest.fail("Invalid limits must not load settings or construct a provider")
    monkeypatch.setattr(run_team, "load_settings", forbidden)
    monkeypatch.setattr(run_team, "create_configured_provider", forbidden)
    with pytest.raises(SystemExit) as outcome:
        run_team.main([option, value, "--report", "unused.json"])
    assert outcome.value.code == 2


def test_scenario_failure_writes_failure_report_and_returns_nonzero(
    experiment: SimpleNamespace, tmp_path: Path,
) -> None:
    experiment.success = False
    assert run_team.main(["--report", "failure.json"]) == 1
    report = json.loads((tmp_path / "failure.json").read_text())
    assert report["success"] is False
    assert report["result"]["success"] is False
    experiment.provider._client.close.assert_awaited_once()


def test_configuration_failure_is_reported_without_fallback_or_secret_leak(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_kwargs: Any) -> None:
        raise ValueError("No API key configured: private-config-key")
    monkeypatch.setattr(run_team, "create_configured_provider", lambda *_a, **kw: fail(**kw))
    assert run_team.main(["--report", "failure.json"]) == 2
    text = (tmp_path / "failure.json").read_text()
    report = json.loads(text)
    assert report["success"] is False and report["result"] is None
    assert report["error"]["type"] == "ValueError"
    assert "No API key configured" in report["error"]["message"]
    assert "private-config-key" not in text
    assert not experiment.rigs


def test_scenario_exception_restores_cwd_closes_clients_and_keeps_report(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("scenario interrupted: private-config-key")
    monkeypatch.setattr(run_team, "run_team_python_workflow", fail)
    assert run_team.main(["--report", "failure.json"]) == 1
    report = json.loads((tmp_path / "failure.json").read_text())
    assert report["error"]["type"] == "RuntimeError"
    assert "private-config-key" not in json.dumps(report)
    assert Path.cwd() == tmp_path
    experiment.provider._client.close.assert_awaited_once()
    experiment.specialist._client.close.assert_awaited_once()


def test_cleanup_failure_cannot_leave_a_success_report(
    experiment: SimpleNamespace, tmp_path: Path,
) -> None:
    experiment.cleanup_error = RuntimeError("cleanup failed")
    assert run_team.main(["--report", "failure.json"]) == 1
    report = json.loads((tmp_path / "failure.json").read_text())
    assert report["success"] is False
    assert "cleanup failed" in report["error"]["message"]


@pytest.mark.usefixtures("experiment")
def test_report_write_error_returns_nonzero(tmp_path: Path) -> None:
    directory = tmp_path / "report-directory"
    directory.mkdir()
    assert run_team.main(["--report", str(directory)]) == 2


def test_cancelled_scenario_retains_report_and_releases_owned_clients(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def cancel(*_args: Any, **_kwargs: Any) -> None:
        raise asyncio.CancelledError
    monkeypatch.setattr(run_team, "run_team_python_workflow", cancel)
    assert run_team.main(["--report", "cancelled.json"]) == 130
    report = json.loads((tmp_path / "cancelled.json").read_text())
    assert report["success"] is False
    assert report["error"]["type"] == "CancelledError"
    assert Path.cwd() == tmp_path
    experiment.provider._client.close.assert_awaited_once()
    experiment.specialist._client.close.assert_awaited_once()


def test_client_close_failure_keeps_primary_error_and_still_restores_workspace(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("Primary evaluation failure")
    monkeypatch.setattr(run_team, "run_team_python_workflow", fail)
    experiment.provider._client.close.side_effect = RuntimeError("Client cleanup failed")
    assert run_team.main(["--report", "failure.json"]) == 1
    report = json.loads((tmp_path / "failure.json").read_text())
    assert report["error"]["message"] == "Primary evaluation failure"
    assert report["cleanup_errors"][0]["message"] == "Client cleanup failed"
    assert Path.cwd() == tmp_path
    experiment.specialist._client.close.assert_awaited_once()


def test_reference_credentials_are_redacted_even_with_custom_environment_name(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment.settings.providers.openrouter["api_key"] = "${CUSTOM_ROUTER_CREDENTIAL}"
    monkeypatch.setenv("CUSTOM_ROUTER_CREDENTIAL", "resolved-private-value")
    async def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("transport: resolved-private-value")
    monkeypatch.setattr(run_team, "run_team_python_workflow", fail)
    assert run_team.main(["--report", "failure.json"]) == 1
    assert "resolved-private-value" not in (tmp_path / "failure.json").read_text()


def test_unparsed_settings_error_does_not_echo_configuration_contents(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_kwargs: Any) -> None:
        raise ValueError("Malformed input: api_key=unparsed-private-value")
    monkeypatch.setattr(run_team, "load_settings", fail)
    assert run_team.main(["--report", "failure.json"]) == 2
    text = (tmp_path / "failure.json").read_text()
    assert "unparsed-private-value" not in text
    assert json.loads(text)["error"]["type"] == "ValueError"
    assert not experiment.constructions


def test_cancelled_client_close_cannot_mask_primary_error_or_skip_workspace_cleanup(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("Primary failure")
    monkeypatch.setattr(run_team, "run_team_python_workflow", fail)
    experiment.provider._client.close.side_effect = asyncio.CancelledError
    assert run_team.main(["--report", "failure.json"]) == 1
    report = json.loads((tmp_path / "failure.json").read_text())
    assert report["error"]["message"] == "Primary failure"
    assert report["cleanup_errors"][0]["type"] == "CancelledError"
    assert Path.cwd() == tmp_path
    experiment.specialist._client.close.assert_awaited_once()


def test_partial_setup_still_closes_role_clients(
    experiment: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig_type = vars(run_team)["EvalTestRig"]
    original = rig_type.setup
    def fail(self: Any, name: str) -> None:
        original(self, name)
        raise RuntimeError("Later role failed to initialize")
    monkeypatch.setattr(rig_type, "setup", fail)
    assert run_team.main(["--report", "failure.json"]) == 2
    assert Path.cwd() == tmp_path
    experiment.provider._client.close.assert_awaited_once()
    experiment.specialist._client.close.assert_awaited_once()


def test_role_client_created_during_scenario_is_closed(
    experiment: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    late = SimpleNamespace(_client=SimpleNamespace(close=AsyncMock()))
    async def scenario(rig: Any, **_kwargs: Any) -> dict[str, Any]:
        rig.orchestrator.pool._agents["late"] = SimpleNamespace(provider=late)
        return {"success": True}
    monkeypatch.setattr(run_team, "run_team_python_workflow", scenario)
    assert run_team.main(["--report", "result.json"]) == 0
    late._client.close.assert_awaited_once()
    experiment.provider._client.close.assert_awaited_once()
