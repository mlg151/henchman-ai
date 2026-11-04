"""Real subprocess contracts for generated-test mutation coverage."""

from pathlib import Path

import pytest
from evals.test_test_docs import _CLAMP_SOURCE, verify_clamp_tests


@pytest.mark.parametrize(
    "omitted",
    [
        None,
        "missing-lower",
        "missing-upper",
        "missing-range-error",
        "equal-bounds-error",
        "nonnegative-only",
    ],
)
async def test_verify_clamp_tests_oracle(tmp_path: Path, omitted: str | None) -> None:
    bounds_path = tmp_path / "bounds.py"
    test_bounds_path = tmp_path / "test_bounds.py"

    bounds_path.write_bytes(_CLAMP_SOURCE.encode("utf-8"))

    data = [
        ((-2, 0, 5), 0, "below"),
        ((3, 0, 5), 3, "inside"),
        ((9, 0, 5), 5, "above"),
        ((2, 2, 2), 2, "equal"),
        ((-3, -5, -1), -3, "negative"),
    ]

    filtered_data = []
    for args, expected, domain in data:
        if omitted is None:
            filtered_data.append((args, expected))
        elif (
            omitted == "missing-lower"
            and domain == "below"
            or omitted == "missing-upper"
            and domain == "above"
            or omitted == "equal-bounds-error"
            and domain == "equal"
            or omitted == "nonnegative-only"
            and domain == "negative"
        ):
            continue
        else:
            filtered_data.append((args, expected))

    params_str = repr(filtered_data)

    test_bounds_content = f"""
import pytest
from bounds import clamp

@pytest.mark.parametrize("args, expected", {params_str})
def test_clamp_values(args, expected):
    assert clamp(*args) == expected
"""

    if omitted != "missing-range-error":
        test_bounds_content += """
def test_clamp_invalid_range():
    with pytest.raises(ValueError):
        clamp(0, 4, 1)
"""

    test_bounds_path.write_bytes(test_bounds_content.encode("utf-8"))

    orig_bounds = bounds_path.read_bytes()
    orig_test_bounds = test_bounds_path.read_bytes()

    if omitted is None:
        await verify_clamp_tests(tmp_path)
    else:
        with pytest.raises(AssertionError, match=omitted):
            await verify_clamp_tests(tmp_path)

    assert bounds_path.read_bytes() == orig_bounds, "Tests changed candidate source"
    assert test_bounds_path.read_bytes() == orig_test_bounds, "Tests changed themselves"
