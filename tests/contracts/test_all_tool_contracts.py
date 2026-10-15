"""Contract tests for all available builtin tools."""

from __future__ import annotations

import pytest

from henchman.tools.base import ToolKind
from henchman.tools.builtins import ShellTool, iter_available_builtin_tool_classes

# Minimal meta-schema for tool parameters (JSON Schema subset supported by ContractSuite)
TOOL_PARAMETERS_META_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["object"]},
        "properties": {"type": "object"},
        "required": {"type": "array", "items": {"type": "string"}},
        "additionalProperties": {"type": "boolean"}
    },
    "required": ["type"]
}

def test_shell_tool_contract(contract_suite) -> None:
    """ShellTool must satisfy the tool contract."""
    tool = ShellTool()
    assert isinstance(tool.name, str) and tool.name
    assert isinstance(tool.description, str) and tool.description
    assert tool.kind == ToolKind.EXECUTE

    errors = contract_suite.validate_json_schema(tool.parameters, TOOL_PARAMETERS_META_SCHEMA)
    assert errors == [], f"ShellTool parameters schema invalid: {errors}"

@pytest.mark.parametrize("tool_class", iter_available_builtin_tool_classes())
def test_all_builtin_tools_contracts(tool_class, contract_suite) -> None:
    """All available builtin tools must satisfy the basic tool contract."""
    # Some tools might require arguments in __init__, but most builtins don't or have defaults
    try:
        tool = tool_class()
    except TypeError:
        # Skip tools that require mandatory init arguments for now if they aren't standard
        pytest.skip(f"Tool {tool_class.__name__} requires mandatory init arguments")
        return

    assert isinstance(tool.name, str) and tool.name, f"{tool_class.__name__} has invalid name"
    assert isinstance(tool.description, str) and tool.description, f"{tool_class.__name__} has invalid description"

    # Validate parameters schema
    params = tool.parameters
    assert isinstance(params, dict), f"{tool_class.__name__} parameters must be a dict"

    if params:
        errors = contract_suite.validate_json_schema(params, TOOL_PARAMETERS_META_SCHEMA)
        assert errors == [], f"{tool_class.__name__} parameters schema invalid: {errors}"

    # Verify to_declaration
    decl = tool.to_declaration()
    assert decl.name == tool.name
    assert decl.description == tool.description
    assert decl.parameters == tool.parameters
