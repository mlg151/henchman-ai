import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_test_docs import _CLAMP_SOURCE, run_test_docs_scenario
from tests.testing.test_test_docs_documentation import GOOD_DOC

from henchman.providers.base import ToolCall

FULL_TESTS = """import pytest
from bounds import clamp
@pytest.mark.parametrize("args,expected", [((-2,0,5),0), ((3,0,5),3), ((9,0,5),5), ((2,2,2),2), ((-3,-5,-1),-3)])
def test_values(args,expected):
    assert clamp(*args) == expected
def test_invalid():
    with pytest.raises(ValueError):
        clamp(0,4,1)"""


@pytest.mark.asyncio
async def test_test_docs_scenario() -> None:
    good_source = _CLAMP_SOURCE.replace(
        '"""Clamp a value between lower and upper bounds."""', GOOD_DOC
    )
    provider = MockProvider(
        responses=[
            [
                ToolCall(
                    id="docs",
                    name="write_file",
                    arguments={"path": "bounds.py", "content": good_source},
                ),
                ToolCall(
                    id="tests",
                    name="write_file",
                    arguments={"path": "test_bounds.py", "content": FULL_TESTS},
                ),
            ],
            "Done",
        ]
    )
    rig = EvalTestRig(provider=provider, profile="basic")
    try:
        rig.setup("test-docs-positive")
        result = await run_test_docs_scenario(rig)
        assert result.success
    finally:
        rig.cleanup()
