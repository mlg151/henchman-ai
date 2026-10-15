# Missing Contract: Agent Catalog and Platform Manager

**Severity:** Medium  
**Location:** `src/henchman/agents/catalog.py`, `src/henchman/agents/platform_manager.py`

## The gap

`src/henchman/agents/catalog.py` defines `AgentCatalog` which discovers agent
definitions from project and user directories. `src/henchman/agents/platform_manager.py`
defines `AgentPlatformManager` which manages installation/uninstallation/publishing
of agent definitions.

While `test_agent_contracts.py` covers the serialization contracts of
`AgentDefinition`, `AgentInstallation`, `AgentPublication`, etc., **there are
no contract tests verifying:**

1. **Catalog loading** — that agent definitions parsed from files conform to
   the `agents/agent_definition` schema when loaded by the catalog.
2. **Platform manager initialization** — that persisted installation state
   round-trips correctly.
3. **Agent file loading** — that `load_agent_definition_file()` produces
   schema-compliant payloads from both YAML and JSON files.

## What's consumed

- `AgentCatalog` is consumed by `platform_manager.py`, `pool.py`, and CLI commands.
- `AgentPlatformManager` is consumed by `cli/commands/agents_platform_command.py`.
- Agent config maps from `catalog.as_config_map()` feed into `AgentPool`.

## Recommended contract test

Create `tests/contracts/test_catalog_contracts.py`:

```python
def test_agent_catalog_yaml_file_matches_definition_contract(contract_suite, tmp_path):
    """Agent definitions loaded from YAML must satisfy the definition schema."""
    agent_dir = tmp_path / "agents"
    agent_dir.mkdir()
    (agent_dir / "coder.yaml").write_text("""
name: Coder
role: coder
description: Writes production code
system_prompt: Write code
tools:
  - read
  - write
""")
    catalog = AgentCatalog(project_root=tmp_path)
    definitions = catalog.list_agents()
    for defn in definitions:
        payload = defn.to_payload()
        assert_contract_matches(
            payload=payload,
            schema_name="agents/agent_definition",
            contract_suite=contract_suite,
        )
```

And for the platform manager:

```python
def test_platform_manager_installation_roundtrip(contract_suite, tmp_path):
    """Persisting and loading installations should preserve the contract."""
    manager = AgentPlatformManager(data_dir=tmp_path / "data")
    # Use a local YAML file as the install source
    definition = load_agent_definition_file(
        Path("tests/fixtures/agents/coder.yaml"), "local"
    )
    payload = definition.to_payload()
    assert_contract_matches(
        payload=payload,
        schema_name="agents/agent_definition",
        contract_suite=contract_suite,
    )
```

## Existing coverage

The `test_agent_contracts.py` file validates serialized agent definition shapes
from *in-memory* objects but never tests the *file loading* path. This is a gap
in the input validation contract.
