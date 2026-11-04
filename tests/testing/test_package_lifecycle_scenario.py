from typing import Any
from unittest.mock import AsyncMock

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.models import EvalResult
from evals.test_package_lifecycle import run_package_lifecycle_scenario
from tests.testing.test_team_package_scenario import script

from henchman.config.schema import Settings


@pytest.mark.asyncio
async def test_package_lifecycle_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=script(), profile="team", settings=settings)
    actual_results: list[EvalResult] = []
    original = rig.run

    async def tracked(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original(*args, **kwargs)
        actual_results.append(result)
        return result

    monkeypatch.setattr(rig, "run", tracked)

    try:
        rig.setup("package-lifecycle-positive")
        result = await run_package_lifecycle_scenario(rig)
        assert result.success
        assert len(actual_results) == 1
        assert result is actual_results[0]
    finally:
        rig.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["no_review", "late_edit", "failed_review"])
async def test_package_lifecycle_scenario_defects(defect: str) -> None:
    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=script(defect), profile="team", settings=settings)
    try:
        rig.setup("package-lifecycle-" + defect)
        with pytest.raises(
            AssertionError, match="Missing team evidence: independent_review_completed"
        ):
            await run_package_lifecycle_scenario(rig)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_package_lifecycle_scenario_authoritative_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=script(), profile="team", settings=settings)

    import evals.test_package_lifecycle as case_module

    original_run = rig.run
    original_runner = case_module.run_team_python_package
    captured_results: list[EvalResult] = []
    reports: list[dict[str, Any]] = []

    async def failed_run(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original_run(*args, **kwargs)
        result.success = False
        result.error = "Authoritative package root failure"
        captured_results.append(result)
        return result

    async def record_report(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = await original_runner(*args, **kwargs)
        reports.append(report)
        return report

    monkeypatch.setattr(rig, "run", failed_run)
    monkeypatch.setattr(case_module, "run_team_python_package", record_report)

    try:
        rig.setup("package-authoritative-runtime-failure")
        with pytest.raises(AssertionError, match="Authoritative package root failure"):
            await run_package_lifecycle_scenario(rig)

        assert len(captured_results) == len(reports) == 1
        assert reports[0]["package"]["success"] is True
        assert reports[0]["package"]["artifacts"]["executed_tests"] == 5
        assert reports[0]["runtime"]["success"] is False
        assert reports[0]["workflow"]["independent_review_completed"] is True
        assert "Authoritative package root failure" in reports[0]["errors"]
    finally:
        rig.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["basic", "engineer"])
async def test_rejection_before_creation_production_profiles(
    profile: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = MockProvider(responses=["Done"])
    rig = EvalTestRig(provider=provider, profile=profile)
    spy = AsyncMock(wraps=rig.run)
    monkeypatch.setattr(rig, "run", spy)
    try:
        rig.setup("package-unsupported-" + profile)
        assert not (rig.test_dir / "pyproject.toml").exists()
        with pytest.raises(AssertionError, match="requires the production team"):
            await run_package_lifecycle_scenario(rig)
        spy.assert_not_awaited()
        assert provider.calls == []
        assert not (rig.test_dir / "pyproject.toml").exists()
    finally:
        rig.cleanup()
