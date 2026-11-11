"""Offline acceptance and fault contracts for syntax repair."""

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_coding_tasks import run_fix_syntax_error_scenario
from tests.testing.test_counter_eval_contract import ErrorAfterWriteProvider

VALID_SOURCE = 'def greet(name):\n    print(f"Hello, {name}!")\n    return True\n'


@pytest.mark.parametrize(
    ("source", "expected_success"),
    [
        pytest.param(VALID_SOURCE, True, id="valid-patch"),
        pytest.param(VALID_SOURCE.replace("Hello,", "Goodbye,"), False, id="wrong-greeting"),
        pytest.param("import os; os._exit(0)\n", False, id="early-zero-exit"),
    ],
)
async def test_fix_syntax_error_parametrized(source: str, expected_success: bool) -> None:
    provider = MockProvider()
    provider.set_tool_response(
        "write_file", {"path": "broken.py", "content": source}, "Fixed",
    )
    rig = EvalTestRig(provider=provider)
    try:
        rig.setup("syntax-scenario")
        if expected_success:
            result = await run_fix_syntax_error_scenario(rig)
            assert result.success
            assert any(log.tool_name == "write_file" and log.success for log in result.tool_logs)
        else:
            with pytest.raises(AssertionError):
                await run_fix_syntax_error_scenario(rig)
    finally:
        rig.cleanup()


async def test_fix_syntax_error_provider_failure() -> None:
    provider = ErrorAfterWriteProvider()
    provider.set_tool_response(
        "write_file", {"path": "broken.py", "content": VALID_SOURCE}, "Fixed",
    )
    rig = EvalTestRig(provider=provider)
    try:
        rig.setup("syntax-scenario-provider-failure")
        with pytest.raises(AssertionError, match="Provider failed after writing counter"):
            await run_fix_syntax_error_scenario(rig)
        path = rig.test_dir / "broken.py"
        compile(path.read_bytes(), str(path), "exec")
    finally:
        rig.cleanup()
