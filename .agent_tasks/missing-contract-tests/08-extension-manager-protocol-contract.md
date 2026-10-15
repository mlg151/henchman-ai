# Missing Contract: Extension Manager Protocol & Plugin Database

**Severity:** Medium  
**Location:** `src/henchman/extensions/base.py`, `src/henchman/extensions/manager.py`, `src/henchman/extensions/plugin_database.py`

## The gap

### 1. Extension ABC contract

`src/henchman/extensions/base.py` defines `Extension(ABC)` with abstract
methods `name`, `version`, `description`, `get_tools`, `get_commands`,
`get_context`. **There is no contract test** verifying that a minimal valid
extension satisfies all required methods — analogous to the
`test_tool_contracts.py::test_tool_contract_methods` test for tools.

### 2. ExtensionManager behavior contract

`ExtensionManager` has methods like `register`, `unregister`, `list_extensions`,
`get_all_tools`, `get_all_commands`, `discover_entry_points`,
`discover_directory`. **No contract test** verifies the manager's interfaces
work correctly with minimal extension implementations.

### 3. Plugin database payloads

While `test_extension_contracts.py` covers `PluginMetadata`, `PluginSearchResult`,
`PluginInstallation`, etc., the actual **plugin database persistence layer**
(`plugin_database.py`) has no shape contract for its stored records.

## What's consumed

- The `Extension` ABC is the base for all plugins in `henchman-cli` and
  third-party extensions.
- `ExtensionManager` is consumed by `cli/plugins.py` and `cli/repl.py`.
- Plugin database records are persisted and loaded across sessions.

## Recommended contract test

### Extension ABC

Add to `tests/contracts/test_extension_contracts.py`:

```python
def test_extension_is_abstract():
    """Extension should be an abstract base class."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        Extension()


def test_extension_contract_methods():
    """Concrete extensions must provide required methods and properties."""
    class IncompleteExtension(Extension):
        pass
    with pytest.raises(TypeError):
        IncompleteExtension()

    class ValidExtension(Extension):
        @property
        def name(self) -> str: return "test"
        @property
        def version(self) -> str: return "1.0.0"
        @property
        def description(self) -> str: return "A test extension"
        def get_tools(self) -> list[Tool]: return []
        def get_commands(self) -> list[Command]: return []
        def get_context(self) -> str: return ""

    ext = ValidExtension()
    assert ext.name == "test"
    assert ext.version == "1.0.0"
    assert ext.description == "A test extension"
```

### ExtensionManager protocol

```python
def test_extension_manager_matches_protocol():
    """ExtensionManager should work with minimal extensions."""
    manager = ExtensionManager()
    ext = ValidExtension()
    manager.register(ext)
    assert "test" in manager.list_extensions()
    assert manager.get_all_tools() == []
    assert manager.get_all_commands() == []
```

### Plugin database contract

Add a schema `tests/contracts/schemas/extensions/plugin_database_record.json`
for the persisted record shape in `plugin_database.py`.
