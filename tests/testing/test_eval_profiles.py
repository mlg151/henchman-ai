"""Offline contracts for explicit production-engineer evaluation profiles."""

import hashlib
from collections.abc import Iterator
from typing import Any

import pytest
from evals import helpers
from evals.helpers import EvalTestRig, MockProvider, eval_test

from henchman.agents.presets import get_default_team
from henchman.core.agent_config import AgentConfig
from henchman.providers.base import ToolCall


@pytest.fixture
def make_rig() -> Iterator[Any]:
    rigs: list[EvalTestRig] = []

    def make(**kwargs: Any) -> EvalTestRig:
        rig = EvalTestRig(provider=kwargs.pop("provider", MockProvider()), **kwargs)
        rigs.append(rig)
        rig.setup("eval-profile")
        return rig

    yield make
    for rig in reversed(rigs):
        rig.cleanup()


def test_unknown_profile_fails_before_provider_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden() -> None:
        pytest.fail("Unknown profiles must not construct a provider")

    monkeypatch.setattr(helpers, "get_eval_provider", forbidden)
    with pytest.raises(ValueError, match="profile"):
        EvalTestRig(profile="enginer")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"system_prompt": "custom"},
        {"system_prompt": ""},
        {"config": AgentConfig(system_prompt="custom")},
    ],
)
def test_engineer_rejects_custom_prompt_conflicts(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="prompt"):
        EvalTestRig(provider=MockProvider(), profile="engineer", **kwargs)


def test_basic_profile_and_custom_prompt_remain_available(
    make_rig: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_PROFILE", "engineer")
    rig = make_rig(profile="basic", system_prompt="custom private project instructions")
    assert rig._agent is not None
    assert rig._agent.messages[0].content == "custom private project instructions"
    assert set(rig.profile_metadata["tool_names"]) == {
        "read_file",
        "write_file",
        "edit_file",
        "ls",
        "glob",
        "grep",
        "shell",
        "web_fetch",
        "ask_user",
    }
    assert "custom private" not in str(rig.profile_metadata)
    config = AgentConfig(system_prompt="configured prompt", max_tokens=3072)
    configured = make_rig(profile="basic", config=config)
    assert configured._agent is not None
    assert configured._agent.messages[0].content == "configured prompt"
    assert config.system_prompt == "configured prompt"


def test_engineer_uses_canonical_prompt_tools_and_preserves_budget(make_rig: Any) -> None:
    from henchman.agents.prompts import get_agent_prompt
    from henchman.tools.builtins import iter_available_builtin_tool_classes

    config = AgentConfig(max_tokens=3072, context_window=16384, summarize_dropped=False, base_tool_iterations=7)
    rig = make_rig(profile="engineer", config=config)
    assert rig._agent is not None
    prompt = rig._agent.messages[0].content
    assert isinstance(prompt, str)
    assert prompt == get_agent_prompt(
        "engineer",
        environment_context=helpers._ENGINEER_EVAL_CONTEXT,
    )
    metadata = rig.profile_metadata
    assert metadata["profile"] == "engineer"
    assert metadata["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert metadata["prompt_chars"] == len(prompt)
    assert metadata["max_tokens"] == 3072
    assert metadata["context_window"] == 16384
    assert metadata["scope"] == "single_agent"
    assert "system_prompt" not in metadata
    names = set(metadata["tool_names"])
    assert names == set(get_default_team()["engineer"].tools)
    assert {"python_ast", "python_exec", "pytest_run", "patch_apply"} <= names
    assert not {"delegate_task", "lsp", "web_fetch", "ask_user"} & names
    available = iter_available_builtin_tool_classes()
    for name in names:
        tool = rig._agent.tool_registry.get(name)
        assert type(tool) in available
    assert rig._agent._config.summarize_dropped is False
    assert rig._agent._config.base_tool_iterations == 7
    assert config.system_prompt == ""
    assert config.max_tokens == 3072
    metadata["tool_names"].clear()
    assert rig.profile_metadata["tool_names"]


def test_engineer_respects_available_builtin_filter(
    make_rig: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from henchman.tools import builtins

    available = builtins.iter_available_builtin_tool_classes()
    monkeypatch.setattr(
        builtins,
        "iter_available_builtin_tool_classes",
        lambda: tuple(cls for cls in available if cls is not builtins.PythonAstTool),
    )
    rig = make_rig(profile="engineer")
    assert "python_ast" not in rig.profile_metadata["tool_names"]
    assert "python_exec" in rig.profile_metadata["tool_names"]


async def test_decorator_honors_environment_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_PROFILE", "engineer")
    monkeypatch.setattr(helpers, "get_eval_provider", MockProvider)

    @eval_test("ALWAYS_PASSES")
    async def scenario(rig: EvalTestRig) -> None:
        assert rig.profile_metadata["profile"] == "engineer"
        assert (await rig.run("Acknowledge")).success

    await scenario()


async def test_engineer_real_checker_failure_then_repair_is_visible(make_rig: Any) -> None:
    def call(name: str, **arguments: Any) -> list[ToolCall]:
        return [ToolCall(id=name + str(arguments), name=name, arguments=arguments)]

    provider = MockProvider(
        [
            call("write_file", path="broken.py", content="def answer(:\n    return 42\n"),
            call("python_ast", path="broken.py"),
            call("edit_file", path="broken.py", old_str="def answer(:", new_str="def answer():"),
            call("python_ast", path="broken.py"),
            call(
                "python_exec",
                code="from broken import answer; assert answer() == 42; print('verified')",
                background=False,
            ),
            "Repaired and verified.",
        ]
    )
    rig = make_rig(profile="engineer", provider=provider, config=AgentConfig(max_tokens=20000))
    result = await rig.run("Repair the syntax and verify the result.", max_iterations=8)
    assert result.success, result.error
    assert [(log.tool_name, log.success) for log in result.tool_logs] == [
        ("write_file", False),
        ("python_ast", False),
        ("edit_file", True),
        ("python_ast", True),
        ("python_exec", True),
    ]
    assert "verified" in result.tool_logs[-1].result
    repair_request = provider.calls[2]["messages"]
    assert any(
        message.role == "tool" and "Syntax error" in (message.content or "")
        for message in repair_request
    )
    assert rig.read_file("broken.py") == "def answer():\n    return 42\n"


def test_default_profile_is_basic_without_environment(
    make_rig: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EVAL_PROFILE", raising=False)
    rig = make_rig()
    assert rig.profile_metadata["profile"] == "basic"
    assert "python_ast" not in rig.profile_metadata["tool_names"]


def test_setup_failure_restores_cwd_and_removes_owned_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    from henchman.cli.tool_manager import ToolManager

    original = Path.cwd()
    created: list[Path] = []

    def fail(manager: ToolManager) -> None:
        assert manager._project_root == Path.cwd()
        created.append(Path.cwd())
        raise RuntimeError("tool assembly failed")

    monkeypatch.setattr(ToolManager, "register_builtin_tools", fail)
    rig = EvalTestRig(provider=MockProvider(), profile="engineer")
    with pytest.raises(RuntimeError, match="tool assembly failed"):
        rig.setup("failed-profile")
    assert Path.cwd() == original
    assert created and created[0] != original
    assert not created[0].exists()
    with pytest.raises(RuntimeError, match="not set up"):
        _ = rig.profile_metadata


@pytest.mark.asyncio
async def test_engineer_logging_preserves_schema_discovery(make_rig: Any) -> None:
    provider = MockProvider([
        [ToolCall("search", "tool_search", {"query": "pytest_run"})], "Found.",
    ])
    rig = make_rig(
        profile="engineer", provider=provider,
        config=AgentConfig(max_tokens=6000, context_window=8000),
    )
    assert rig._agent is not None
    registry = rig._agent.tool_registry
    assert registry.supports_tool_discovery
    result = await rig.run("Find the pytest tool")
    assert result.success
    assert registry.discovered_tools == ["pytest_run"]
    assert rig.tool_was_called("tool_search")
    assert not {"delegate_task", "web_fetch"} & set(registry.discovered_tools)
