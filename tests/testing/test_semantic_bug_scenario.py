from collections.abc import Callable
from typing import Any

import pytest
from evals import helpers
from evals import test_edit_precision as scenarios
from tests.testing.test_edit_eval_contract import EditingProvider


def valid_repair(source: str) -> str:
    return source.replace("return 0  # BUG: should return None, not 0", "return None")


def always_none(source: str) -> str:
    source = valid_repair(source)
    return source.replace("return a / b", "return None")


def damaged_neighbor(source: str) -> str:
    source = valid_repair(source)
    return source.replace("return max(min_val, min(value, max_val))", "return 123")


def equivalent_neighbor(source: str) -> str:
    source = valid_repair(source)
    return source.replace(
        "return max(min_val, min(value, max_val))", "return max(min_val, min(value, max_val)) + 0"
    )


@pytest.mark.parametrize(
    "edit, expected_pass",
    [
        (valid_repair, True),
        (always_none, False),
        (damaged_neighbor, False),
        (equivalent_neighbor, False),
    ],
)
async def test_semantic_bug_scenario(
    monkeypatch: pytest.MonkeyPatch,
    edit: Callable[[str], str],
    expected_pass: bool,
) -> None:
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: EditingProvider({"utils.py": edit}))
    if expected_pass:
        await scenarios.test_fix_bug_preserve_formatting()
    else:
        with pytest.raises(AssertionError):
            await scenarios.test_fix_bug_preserve_formatting()


@pytest.mark.parametrize(
    "fail",
    [False, True],
)
async def test_semantic_bug_scenario_contract(
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    from evals.models import EvalResult

    provider = EditingProvider({"utils.py": valid_repair}, fail=fail)
    rig = helpers.EvalTestRig(provider=provider)

    actual_results: list[EvalResult] = []

    original_run = rig.run

    async def tracked_run(*args: Any, **kwargs: Any) -> EvalResult:
        result = await original_run(*args, **kwargs)
        actual_results.append(result)
        return result

    monkeypatch.setattr(rig, "run", tracked_run)

    try:
        rig.setup()
        if fail:
            with pytest.raises(AssertionError, match="provider failed after edit"):
                await scenarios.run_semantic_bug_fix_scenario(rig)
            assert len(actual_results) == 1
            assert not actual_results[0].success
        else:
            result = await scenarios.run_semantic_bug_fix_scenario(rig)
            assert len(actual_results) == 1
            assert result is actual_results[0]
            assert result.success

        verify_code = """
from utils import safe_divide, clamp
assert safe_divide(1,0) is None
assert safe_divide(6,3) == 2
assert clamp(-2, 0, 5) == 0
assert clamp(3, 0, 5) == 3
assert clamp(9, 0, 5) == 5
"""
        await helpers.verify_python(rig.test_dir, verify_code)
    finally:
        rig.cleanup()
