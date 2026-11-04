from collections.abc import AsyncGenerator
from typing import Any

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_test_docs import (
    _CLAMP_SOURCE,
    run_test_docs_scenario,
    verify_clamp_documentation,
    verify_clamp_tests,
)
from tests.testing.test_test_docs_documentation import GOOD_DOC

from henchman.providers.base import Message, StreamChunk, ToolCall, ToolDeclaration


class _FailAfterWritesProvider(MockProvider):
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if self.calls:
            raise RuntimeError("test-docs runtime failure")
        async for chunk in super().chat_completion_stream(
            messages, tools, temperature, max_tokens, **kwargs
        ):
            yield chunk


FULL_TESTS = """import pytest
from bounds import clamp
@pytest.mark.parametrize("args,expected", [((-2,0,5),0), ((3,0,5),3), ((9,0,5),5), ((2,2,2),2), ((-3,-5,-1),-3)])
def test_values(args,expected):
    assert clamp(*args) == expected
def test_invalid():
    with pytest.raises(ValueError):
        clamp(0,4,1)"""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    ["complete", "missing-doc", "thin-tests", "changed-implementation", "no-op"],
    ids=["complete", "missing-doc", "thin-tests", "changed-implementation", "no-op"],
)
async def test_test_docs_scenario(scenario: str) -> None:
    if scenario == "no-op":
        provider = MockProvider(responses=["Done"])
    else:
        good_doc = GOOD_DOC
        tests_content = FULL_TESTS

        if scenario == "missing-doc":
            good_doc = good_doc.replace("    >>> clamp(9, 0, 5)\n    5\n", "    >>> 1 + 1\n    2\n")
        elif scenario == "thin-tests":
            tests_content = (
                "from bounds import clamp\ndef test_clamp():\n    assert clamp(3, 0, 5) == 3"
            )

        good_source = _CLAMP_SOURCE.replace(
            '"""Clamp a value between lower and upper bounds."""', good_doc
        )

        if scenario == "changed-implementation":
            good_source = good_source.replace(
                "return max(lower, min(value, upper))",
                "return max(lower, min(value, upper)) + (value == 4242)",
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
                        arguments={"path": "test_bounds.py", "content": tests_content},
                    ),
                ],
                "Done",
            ]
        )

    rig = EvalTestRig(provider=provider, profile="basic")
    try:
        rig.setup(f"test-docs-{scenario}")
        if scenario == "complete":
            result = await run_test_docs_scenario(rig)
            assert result.success
        else:
            expected_error = {
                "missing-doc": "not found in doctests",
                "thin-tests": "Mutant not rejected: missing-lower",
                "changed-implementation": "Implementation or signature changed",
                "no-op": "Documentation was not updated",
            }[scenario]
            with pytest.raises(AssertionError, match=expected_error):
                await run_test_docs_scenario(rig)
    finally:
        rig.cleanup()


@pytest.mark.asyncio
async def test_test_docs_runtime_failure() -> None:
    good_source = _CLAMP_SOURCE.replace(
        '"""Clamp a value between lower and upper bounds."""', GOOD_DOC
    )
    tests_content = FULL_TESTS

    provider = _FailAfterWritesProvider(
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
                    arguments={"path": "test_bounds.py", "content": tests_content},
                ),
            ],
            "Done",
        ]
    )

    rig = EvalTestRig(provider=provider, profile="basic")
    try:
        rig.setup("test-docs-runtime-failure")
        with pytest.raises(AssertionError, match="test-docs runtime failure"):
            await run_test_docs_scenario(rig)
        # Prove the runtime failure occurred after independently valid delivery.
        # Production writes format Python, so verify the actual delivered bytes.
        bounds = rig.test_dir / "bounds.py"
        tests = rig.test_dir / "test_bounds.py"
        delivered_source = bounds.read_bytes()
        delivered_tests = tests.read_bytes()
        await verify_clamp_documentation(rig.test_dir)
        await verify_clamp_tests(rig.test_dir)
        assert bounds.read_bytes() == delivered_source
        assert tests.read_bytes() == delivered_tests
    finally:
        rig.cleanup()
