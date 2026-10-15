"""Offline rejection contracts for real edit-evaluation tools and Python oracles."""

from collections.abc import AsyncGenerator, Callable
from pathlib import Path
from typing import Any

import pytest
from evals import helpers
from evals import test_edit_precision as scenarios
from evals.helpers import MockProvider

from henchman.providers.base import Message, StreamChunk, ToolCall, ToolDeclaration

Edit = Callable[[str], str]


def calculator(source: str) -> str:
    return source + (
        "\n    def multiply(self, x):\n        self.result *= x\n        return self.result\n"
    )


def renamed(source: str) -> str:
    return source.replace("tmp", "result")


def user_model(source: str) -> str:
    return source.replace(
        "def __init__(self, name):", "def __init__(self, name, email=None):"
    ).replace("self.name = name", "self.name = name\n        self.email = email")


def user_app(source: str) -> str:
    return source.replace('User("World")', 'User("World", email="world@example.test")')


class EditingProvider(MockProvider):
    """Emit genuine file-tool calls, followed by completion or a provider failure."""

    def __init__(self, edits: dict[str, Edit], *, fail: bool = False) -> None:
        super().__init__()
        self.edits = edits
        self.fail = fail

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamChunk, None]:
        if not self.calls:
            self._responses = [
                [
                    ToolCall(
                        id=f"write-{index}",
                        name="write_file",
                        arguments={"path": path, "content": edit(Path(path).read_text())},
                    )
                    for index, (path, edit) in enumerate(self.edits.items())
                ],
                "Done.",
            ]
        elif self.fail:
            raise RuntimeError("provider failed after edit")
        async for chunk in super().chat_completion_stream(
            messages,
            tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        ):
            yield chunk


GOOD = [
    ("test_add_method_to_class", {"calculator.py": calculator}),
    ("test_rename_variable_consistently", {"processor.py": renamed}),
    ("test_multi_file_edit", {"models.py": user_model, "app.py": user_app}),
]


@pytest.mark.parametrize(("scenario", "edits"), GOOD)
async def test_accepts_real_successful_edits(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    edits: dict[str, Edit],
) -> None:
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: EditingProvider(edits))
    await getattr(scenarios, scenario)()


@pytest.mark.parametrize(("scenario", "edits"), GOOD)
async def test_rejects_provider_failure_after_correct_files(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    edits: dict[str, Edit],
) -> None:
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: EditingProvider(edits, fail=True))
    with pytest.raises(AssertionError, match="provider failed"):
        await getattr(scenarios, scenario)()


@pytest.mark.parametrize(
    "edit",
    [
        lambda source: source + "\n    def multiply(self, x):\n        return self.result * x\n",
        lambda source: calculator(source).replace(
            "self.result += x", "self.result = self.result + x"
        ),
    ],
)
async def test_rejects_nonmutating_multiply_and_changed_original_methods(
    monkeypatch: pytest.MonkeyPatch,
    edit: Edit,
) -> None:
    monkeypatch.setattr(
        helpers,
        "get_eval_provider",
        lambda: EditingProvider({"calculator.py": edit}),
    )
    with pytest.raises(AssertionError):
        await scenarios.test_add_method_to_class()


@pytest.mark.parametrize(
    "edit",
    [
        lambda source: source,
        lambda source: renamed(source).replace("item * 2", "item * 3"),
        lambda source: renamed(source).replace("result = data.copy()", "result = data"),
        lambda source: renamed(source).replace("result", "answer") + "\n# result " * 6,
    ],
)
async def test_rejects_unchanged_broken_mutating_and_comments_only_rename(
    monkeypatch: pytest.MonkeyPatch,
    edit: Edit,
) -> None:
    monkeypatch.setattr(
        helpers,
        "get_eval_provider",
        lambda: EditingProvider({"processor.py": edit}),
    )
    with pytest.raises(AssertionError):
        await scenarios.test_rename_variable_consistently()


@pytest.mark.parametrize(
    "edits",
    [
        {
            "models.py": lambda source: source + "\n# email\n",
            "app.py": lambda source: source + "\n# email\n",
        },
        {"models.py": user_model, "app.py": lambda source: source + "\n# email\n"},
        {
            "models.py": lambda source: user_model(source).replace("email=None", "email"),
            "app.py": user_app,
        },
        {
            "models.py": lambda source: user_model(source).replace(
                "self.email = email", "self.email = None"
            ),
            "app.py": user_app,
        },
    ],
)
async def test_rejects_missing_email_contract_or_callsite(
    monkeypatch: pytest.MonkeyPatch,
    edits: dict[str, Edit],
) -> None:
    monkeypatch.setattr(helpers, "get_eval_provider", lambda: EditingProvider(edits))
    with pytest.raises(AssertionError):
        await scenarios.test_multi_file_edit()


@pytest.mark.parametrize(("scenario", "edits"), GOOD)
@pytest.mark.parametrize("fail", [False, True])
async def test_reusable_scenarios_return_result_or_reject_failed_runtime(
    scenario: str,
    edits: dict[str, Edit],
    fail: bool,
) -> None:
    rig = helpers.EvalTestRig(provider=EditingProvider(edits, fail=fail))
    rig.setup("direct-edit-contract")
    try:
        run_scenario = getattr(scenarios, scenario.replace("test_", "run_", 1) + "_scenario")
        if fail:
            with pytest.raises(AssertionError, match="provider failed"):
                await run_scenario(rig)
        else:
            result = await run_scenario(rig)
            assert result.success
            assert any(log.success and log.tool_name == "write_file" for log in result.tool_logs)
    finally:
        rig.cleanup()


@pytest.mark.parametrize(
    ("construction", "accepted"),
    [
        ('User("World", email="world@example.test")', True),
        ('User("World", "world@example.test")', True),
        ('User("World")\n    user.email = "world@example.test"', False),
        ('User("World", email="")\n    user.email = "world@example.test"', False),
    ],
)
async def test_multifile_observes_supplied_constructor_email(
    construction: str,
    accepted: bool,
) -> None:
    edits = {
        "models.py": user_model,
        "app.py": lambda source: source.replace('User("World")', construction),
    }
    rig = helpers.EvalTestRig(provider=EditingProvider(edits))
    rig.setup("constructor-arguments-contract")
    try:
        if accepted:
            result = await scenarios.run_multi_file_edit_scenario(rig)
            assert result.success
        else:
            with pytest.raises(AssertionError, match="nonempty email"):
                await scenarios.run_multi_file_edit_scenario(rig)
    finally:
        rig.cleanup()
