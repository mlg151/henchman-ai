"""Discovery distinguishes local workflow metadata from command execution."""

import pytest

from henchman.cli.commands.discovery_capabilities import classify_registered_tool
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.builtins.tier5_tools import WorkflowTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.parametrize("registered", [True, False])
def test_workflow_classification_tracks_registration_without_claiming_execution(registered):
    capability = classify_registered_tool(
        "workflow",
        registered_tool_names=("workflow",) if registered else (),
    )
    assert capability is not None
    assert capability.classification == ("metadata-only" if registered else "unavailable")


async def test_bound_search_annotates_actual_workflow_tool_as_metadata():
    registry = ToolRegistry()
    registry.register(WorkflowTool())
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)

    result = await registry.execute("tool_search", {"query": "workflow"})

    assert result.success
    assert any(
        line.startswith("- workflow") and "metadata-only" in line
        for line in result.content.splitlines()
    )
