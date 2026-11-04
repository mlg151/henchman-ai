"""Evaluate recovery from a real failed tool check before a verified repair."""

from evals.helpers import EvalTestRig, verify_python
from evals.models import EvalResult


async def run_tool_failure_recovery_scenario(rig: EvalTestRig) -> EvalResult:
    """Require observed checker failure, recovery, and independent correctness."""
    rig.create_file(
        "pricing.py",
        "def total_price(unit_price, quantity):\n    return unit_price + quantity\n",
    )
    result = await rig.run(
        "First use python_exec to run an assertion that total_price(7, 3) == 21 "
        "from pricing.py and observe its failure. Then fix total_price to multiply "
        "unit_price by quantity. Run the same assertion successfully with python_exec. "
        "Read current source for each check so a cached module cannot hide the repair.",
        max_iterations=10,
    )
    assert result.success, result.error or result.final_response
    checks = [log for log in result.tool_logs if log.tool_name == "python_exec"]
    assert any(
        not failed.success and any(later.success for later in checks[index + 1 :])
        for index, failed in enumerate(checks)
    ), "Missing failed python_exec followed by successful python_exec"
    await verify_python(
        rig.test_dir,
        """from pricing import total_price
for price, quantity, expected in [(7, 3, 21), (2, 0, 0), (0, 9, 0), (-3, 4, -12), (1.5, 2, 3)]:
    actual = total_price(price, quantity)
    assert isinstance(actual, (int, float)) and not isinstance(actual, bool)
    assert actual == expected
""",
    )
    return result
