"""Offline acceptance and fault contracts for fibonacci repair."""

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_coding_tasks import run_fibonacci_scenario
from tests.testing.test_counter_eval_contract import ErrorAfterWriteProvider

VALID_FIB = """def fib(n):
    if n == 0: return 0
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
"""

WRONG_FIB = """def fib(n):
    return n
"""

FALSE_FIB = """def fib(n):
    if n == 0: return False
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
"""

EXIT_FIB = """import os
os._exit(0)
"""

@pytest.mark.parametrize(
    ("source", "expected_success"),
    [
        pytest.param(VALID_FIB, True, id="correct-iterative"),
        pytest.param(WRONG_FIB, False, id="wrong-value"),
        pytest.param(FALSE_FIB, False, id="false-for-n0"),
        pytest.param(EXIT_FIB, False, id="os-exit"),
    ],
)
async def test_fibonacci_scenario_parametrized(source: str, expected_success: bool) -> None:
    provider = MockProvider()
    provider.set_tool_response(
        "write_file", {"path": "fibonacci.py", "content": source}, "Implemented",
    )
    rig = EvalTestRig(provider=provider)
    try:
        rig.setup("fibonacci-scenario")
        if expected_success:
            result = await run_fibonacci_scenario(rig)
            assert result.success
            assert any(log.tool_name == "write_file" and log.success for log in result.tool_logs)
        else:
            with pytest.raises(AssertionError):
                await run_fibonacci_scenario(rig)
    finally:
        rig.cleanup()


async def test_fibonacci_scenario_error_after_write() -> None:
    provider = ErrorAfterWriteProvider()
    provider.set_tool_response(
        "write_file", {"path": "fibonacci.py", "content": VALID_FIB}, "Implemented",
    )
    rig = EvalTestRig(provider=provider)
    try:
        rig.setup("fibonacci-scenario-provider-failure")
        with pytest.raises(AssertionError, match="Provider failed after writing counter"):
            await run_fibonacci_scenario(rig)
        path = rig.test_dir / "fibonacci.py"
        compile(path.read_bytes(), str(path), "exec")
    finally:
        rig.cleanup()
