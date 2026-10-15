"""Execution discovery follows each scoped executor and its tracking tools."""

import pytest

from henchman.cli.commands.discovery_capabilities import (
    build_discovery_capabilities,
    classify_registered_tool,
)

TRACKING = ("task_get", "task_list", "task_output", "task_stop")


@pytest.mark.parametrize("executor", ["shell", "python_exec"])
def test_one_executor_with_tracking_is_available_without_the_other(executor: str) -> None:
    capability = classify_registered_tool(executor, registered_tool_names=(executor, *TRACKING))
    assert capability is not None
    assert capability.classification == "runtime-wired"
    assert executor in capability.aliases
    assert "background" in capability.search_text


@pytest.mark.parametrize("missing", TRACKING)
def test_missing_companion_makes_execution_capability_unavailable(missing: str) -> None:
    registered = ("shell", *(name for name in TRACKING if name != missing))
    capability = classify_registered_tool("shell", registered_tool_names=registered)
    assert capability is not None
    assert capability.classification == "unavailable"


def test_missing_executor_cannot_appear_available_from_tracking_alone() -> None:
    capabilities = build_discovery_capabilities(registered_tool_names=TRACKING)
    execution = [item for item in capabilities if "shell" in item.aliases or "python_exec" in item.aliases]
    assert len(execution) == 2
    assert all(item.classification == "unavailable" for item in execution)
