import json
from typing import Any

import pytest
from evals.helpers import EvalTestRig
from evals.models import EvalResult
from evals.test_team_python_package import run_team_python_package
from tests.testing.test_team_package_scenario import script

from henchman.config.schema import Settings


@pytest.mark.asyncio
async def test_package_runtime_observer_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=script(), profile="team", settings=settings)
    observed: list[EvalResult] = []
    actual: list[EvalResult] = []
    original = rig.run

    async def tracked(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original(*args, **kwargs)
        actual.append(result)
        return result

    monkeypatch.setattr(rig, "run", tracked)

    try:
        rig.setup("package-runtime-observer-contract")
        report = await run_team_python_package(rig, timeout=90, runtime_observer=observed.append)
        assert report["success"], report["errors"]
        assert len(observed) == len(actual) == 1
        assert observed[0] is actual[0]
        assert observed[0].success
        assert report["package"]["artifacts"]["executed_tests"] == 5
        json.dumps(report)
    finally:
        rig.cleanup()
