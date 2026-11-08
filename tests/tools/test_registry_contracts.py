"""Every registered implementation carries locally checked input/output contracts."""

import pytest

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.contracts import SchemaContract, SchemaContractError
from henchman.tools.registry import ToolRegistry


class ContractTool(Tool):
    name = "contract_fixture"
    description = "Controlled typed output"
    kind = ToolKind.READ

    def __init__(self, schema=None, result=None):
        self.input_schema = {"type": "object"}
        self.schema = schema
        self.result = result or ToolResult("legacy text")
        self.calls = 0

    @property
    def parameters(self):
        return self.input_schema

    @property
    def output_schema(self):
        return self.schema

    async def execute(self, **_params):
        self.calls += 1
        return self.result


@pytest.mark.parametrize("field", ["input_schema", "schema"])
@pytest.mark.parametrize("schema", [{"type": "invalid"}, {"$ref": "https://private.invalid/canary"},
                                   {"$defs": {"unused": {"$ref": "#/missing"}}}])
def test_invalid_contract_is_rejected_before_publication(field, schema):
    tool = ContractTool()
    setattr(tool, field, schema)
    registry = ToolRegistry()
    with pytest.raises(SchemaContractError) as raised:
        registry.register(tool)
    assert registry.get(tool.name) is None
    assert not registry.get_declarations()
    assert "private.invalid" not in str(raised.value)


@pytest.mark.parametrize(("schema", "value"), [({"type": "null"}, None),
    ({"type": "array", "items": {"type": "integer"}}, [1, 2]),
    ({"type": ["string", "null"]}, "value"), (True, False)])
async def test_valid_scalar_array_and_null_outputs_are_preserved(schema, value):
    tool = ContractTool(schema, ToolResult("typed", structured_content=value, structured_content_present=True))
    registry = ToolRegistry()
    registry.register(tool)
    result = await registry.execute(tool.name, {})
    assert result.success and result.structured_content_present
    assert result.structured_content == value
    assert tool.calls == 1


@pytest.mark.parametrize("present", [False, True])
async def test_missing_is_not_null_and_invalid_output_is_not_success(present):
    tool = ContractTool({"type": "integer"}, ToolResult("secret-returned-value", structured_content=None,
                                                      structured_content_present=present))
    registry = ToolRegistry()
    registry.register(tool)
    result = await registry.execute(tool.name, {})
    assert not result.success
    assert "contract" in result.error.lower()
    assert "secret-returned-value" not in repr(result)
    assert tool.calls == 1


async def test_failure_result_does_not_require_success_schema():
    tool = ContractTool({"type": "object"}, ToolResult("Tool refused", success=False, error="Refused"))
    registry = ToolRegistry()
    registry.register(tool)
    result = await registry.execute(tool.name, {})
    assert result == tool.result


async def test_changed_output_schema_during_approval_requires_new_authority():
    tool = ContractTool({"type": "null"}, ToolResult("typed", structured_content_present=True))
    tool.kind = ToolKind.NETWORK
    registry = ToolRegistry()
    registry.register(tool)

    async def approve(_request):
        tool.schema = {"type": "integer"}
        return True

    registry.set_confirmation_handler(approve)
    result = await registry.execute(tool.name, {})
    assert not result.success and tool.calls == 0
    assert "changed" in result.content


async def test_changed_input_schema_during_approval_requires_new_authority():
    tool = ContractTool()
    tool.kind = ToolKind.NETWORK
    registry = ToolRegistry()
    registry.register(tool)

    async def approve(_request):
        tool.input_schema["description"] = "Changed semantics of the approved invocation"
        return True

    registry.set_confirmation_handler(approve)
    result = await registry.execute(tool.name, {})
    assert not result.success and tool.calls == 0
    assert "changed" in result.content


async def test_output_contract_uses_dispatch_snapshot_after_tool_mutates_schema():
    tool = ContractTool({"type": "integer"}, ToolResult("typed", structured_content="private-canary",
                                                      structured_content_present=True))
    registry = ToolRegistry()
    registry.register(tool)
    original_execute = tool.execute

    async def change_schema(**params):
        tool.schema["type"] = "string"
        return await original_execute(**params)

    tool.execute = change_schema
    result = await registry.execute(tool.name, {})
    assert not result.success and tool.calls == 1
    assert "private-canary" not in repr(result)


async def test_invalid_typed_payload_is_rejected_without_echoing_values():
    tool = ContractTool(result=ToolResult("private-canary", metadata={"bad": {"not-json"}}))
    registry = ToolRegistry()
    registry.register(tool)
    result = await registry.execute(tool.name, {})
    assert not result.success
    assert "private-canary" not in repr(result)


async def test_schema_absence_preserves_legacy_text_only_success():
    tool = ContractTool()
    registry = ToolRegistry()
    registry.register(tool)
    assert await registry.execute(tool.name, {}) == tool.result


async def test_invalid_output_is_journaled_as_completed_failure_without_repeating_effect(tmp_path):
    from henchman.core.runtime_operations import use_operation_call
    from tests.core.test_session_operations import setup

    _, call, _, runtime, registry, tool = setup(tmp_path)
    original_execute = tool.execute

    async def bad_output(**params):
        await original_execute(**params)
        return ToolResult("private-canary", metadata={"not_json": {1, 2}})

    tool.execute = bad_output
    invocation = runtime.begin().bind_call(call, agent_id="tech_lead", assistant_index=0)
    with use_operation_call(invocation):
        result = await registry.execute(call.name, call.arguments)
    record = runtime.report().records[0]
    assert record.state == "completed" and not record.result.success
    assert not result.success and "private-canary" not in repr(result)
    with use_operation_call(invocation):
        replay = await registry.execute(call.name, call.arguments)
    assert replay == result and tool.calls == ["original"]


@pytest.mark.parametrize("field", ["input_schema", "schema"])
async def test_cached_nested_schema_change_during_approval_still_denies_dispatch(field):
    original = {"type": "object", "properties": {"value": {"type": "integer"}}}
    replacement = {"type": "object", "properties": {"value": {"type": "string"}}}
    SchemaContract(original)
    SchemaContract(replacement)
    tool = ContractTool(result=ToolResult("typed", structured_content={"value": 1}, structured_content_present=True))
    setattr(tool, field, original)
    tool.kind = ToolKind.NETWORK
    registry = ToolRegistry()
    registry.register(tool)

    async def approve(_request):
        getattr(tool, field)["properties"]["value"]["type"] = "string"
        return True

    registry.set_confirmation_handler(approve)
    result = await registry.execute(tool.name, {"value": 1})
    assert not result.success and tool.calls == 0
    assert "changed" in result.content


async def test_warmed_schema_does_not_reuse_revoked_approval_or_skip_current_arguments():
    tool = ContractTool()
    tool.input_schema = {"type": "object", "properties": {"value": {"type": "integer"}}}
    tool.kind = ToolKind.NETWORK
    registry = ToolRegistry()
    registry.register(tool)
    prompts = []

    async def approve_once(request):
        prompts.append(request)
        return len(prompts) == 1

    registry.set_confirmation_handler(approve_once)
    assert (await registry.execute(tool.name, {"value": 1})).success
    registry.clear_grants()
    refused = await registry.execute(tool.name, {"value": 1})
    assert not refused.success and len(prompts) == 2 and tool.calls == 1
    invalid = await registry.execute(tool.name, {"value": "invalid"})
    assert not invalid.success and "contract" in invalid.content.lower()
    assert len(prompts) == 2 and tool.calls == 1
