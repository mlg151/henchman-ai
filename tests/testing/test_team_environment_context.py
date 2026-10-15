"""Team evaluation requests carry the CLI's actual workspace snapshot."""

import platform
import sys
from pathlib import Path

import pytest
from evals import team_runtime
from evals.helpers import EvalTestRig, MockProvider

from henchman.agents.config import AgentConfig
from henchman.config.schema import Settings
from henchman.providers.base import ToolCall


def inspection_script() -> MockProvider:
    return MockProvider(
        [
            [
                ToolCall(
                    "inspect",
                    "delegate_task",
                    {
                        "agent": "explorer",
                        "task": "Explain the workspace context provided to you.",
                        "completion_requirement": "response",
                    },
                )
            ],
            "Context inspected.",
            "Inspection returned.",
        ]
    )


async def test_actual_leader_and_specialist_requests_include_workspace_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "NEVER_INCLUDE_ENVIRONMENT_SECRET")
    original = Path.cwd()
    provider = inspection_script()
    rig = EvalTestRig(provider=provider, profile="team")
    try:
        rig.setup("environment-parity")
        workspace = rig.test_dir.resolve()
        result = await rig.run("Inspect the workspace context.", timeout=10)
        assert result.success, result.error
        assert len(provider.calls) == 3
        for request in provider.calls[:2]:
            system = "\n".join(
                message.content or "" for message in request["messages"] if message.role == "system"
            )
            assert f"* Working directory: {workspace}" in system
            assert f"* OS: {platform.system()}" in system
            assert f"* Python: {sys.version_info.major}.{sys.version_info.minor}." in system
            assert "<environment_context>" in system
            assert "Tools are automatically approved" in system
            assert "not an OS sandbox" in system
            assert "NEVER_INCLUDE_ENVIRONMENT_SECRET" not in system
    finally:
        rig.cleanup()
    assert Path.cwd() == original
    assert not workspace.exists()


@pytest.mark.parametrize("role,request_index", [("tech_lead", 0), ("explorer", 1)])
async def test_environment_parity_preserves_explicit_role_prompt(
    role: str, request_index: int
) -> None:
    custom = "Use the supplied task; these are the exact custom role instructions."
    settings = Settings()
    settings.agents.agents[role] = AgentConfig(
        name=role, role=role, description="Custom prompt fixture", system_prompt=custom
    )
    provider = inspection_script()
    rig = EvalTestRig(provider=provider, profile="team", settings=settings)
    try:
        rig.setup("custom-environment-parity")
        await rig.run("Inspect the workspace context.", timeout=10)
        system_messages = [
            message.content
            for message in provider.calls[request_index]["messages"]
            if message.role == "system"
        ]
        assert system_messages == [custom]
    finally:
        rig.cleanup()


def test_environment_gather_failure_restores_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.cwd()
    rig = EvalTestRig(provider=MockProvider(), profile="team")

    def fail(_workspace: Path) -> None:
        raise RuntimeError("Environment gathering failed")

    monkeypatch.setattr(team_runtime, "gather_environment", fail, raising=False)
    try:
        with pytest.raises(RuntimeError, match="Environment gathering failed"):
            rig.setup("failed-environment-parity")
        assert Path.cwd() == original
        assert rig._temp_dir is None
    finally:
        rig.cleanup()
