"""Independent test-quality checks for the planned test/documentation case."""

from pathlib import Path

from evals.helpers import run_pytest_evidence

_CLAMP_SOURCE: str = """
def clamp(value: int, lower: int, upper: int) -> int:
    \"\"\"Clamp a value between lower and upper bounds.\"\"\"
    if lower > upper:
        raise ValueError("lower exceeds upper")
    return max(lower, min(value, upper))
"""

_CLAMP_MUTANTS: dict[str, str] = {
    "missing-lower": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return min(value, upper)",
    ),
    "missing-upper": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return max(lower, value)",
    ),
    "missing-range-error": _CLAMP_SOURCE.replace(
        '    if lower > upper:\n        raise ValueError("lower exceeds upper")\n', "",
    ),
    "equal-bounds-error": _CLAMP_SOURCE.replace("if lower > upper:", "if lower >= upper:"),
    "nonnegative-only": _CLAMP_SOURCE.replace(
        "return max(lower, min(value, upper))", "return max(0, max(lower, min(value, upper)))",
    ),
}


async def verify_clamp_tests(workspace: Path) -> None:
    """Require passing candidate tests and a real failure for every semantic mutant."""
    bounds_path = workspace / "bounds.py"
    test_bounds_path = workspace / "test_bounds.py"

    orig_bounds = bounds_path.read_bytes()
    orig_test_bounds = test_bounds_path.read_bytes()

    try:
        evidence = await run_pytest_evidence(workspace, "test_bounds.py")
        assert evidence.exit_status == 0 and evidence.failed == 0, "Candidate tests failed"
        assert bounds_path.read_bytes() == orig_bounds, "Tests changed candidate source"
        assert test_bounds_path.read_bytes() == orig_test_bounds, "Tests changed themselves"

        for name, mutant in _CLAMP_MUTANTS.items():
            bounds_path.write_bytes(mutant.encode("utf-8"))
            evidence = await run_pytest_evidence(workspace, "test_bounds.py")
            assert evidence.exit_status == 1 and evidence.failed > 0, f"Mutant not rejected: {name}"

            assert bounds_path.read_bytes() == mutant.encode("utf-8"), f"Mutant changed: {name}"
            assert test_bounds_path.read_bytes() == orig_test_bounds, f"Tests changed: {name}"
    finally:
        bounds_path.write_bytes(orig_bounds)
        test_bounds_path.write_bytes(orig_test_bounds)
