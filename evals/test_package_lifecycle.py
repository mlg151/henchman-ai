from evals.helpers import EvalTestRig
from evals.models import EvalResult
from evals.test_team_python_package import run_team_python_package


async def run_package_lifecycle_scenario(rig: EvalTestRig) -> EvalResult:
    """Adapt the independent production-team package evaluator for corpus dispatch."""
    results: list[EvalResult] = []
    report = await run_team_python_package(rig, runtime_observer=results.append)

    assert report["success"], report["errors"]
    assert len(results) == 1, "Expected exactly one package runtime result"

    result = results[0]
    assert result.success, result.error or result.final_response

    return result
