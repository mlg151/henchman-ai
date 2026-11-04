from collections.abc import Callable

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


@pytest.mark.parametrize(
    "edit, expected_pass",
    [
        (valid_repair, True),
        (always_none, False),
        (damaged_neighbor, False),
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
