from typing import Any

import pytest
from evals.helpers import EvalTestRig
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
