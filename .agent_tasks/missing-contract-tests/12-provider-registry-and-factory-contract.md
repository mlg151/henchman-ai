# Missing Contract: Provider Registry and Registration Interface

**Severity:** Low  
**Location:** `src/henchman/providers/registry.py`

## The gap

`ProviderRegistry` is the factory/registry for model providers. It provides
`register()`, `get()`, `list_providers()`, and `create()` methods. **There is
no contract test** verifying that:

1. A registered provider class can be retrieved by name.
2. `create(name)` produces a callable `ModelProvider` instance.
3. `list_providers()` returns registered names.
4. `get_default_registry()` contains the expected set of built-in providers.

## What's consumed

- `ProviderRegistry` is consumed by:
  - `cli/core_init.py` — creating the default provider at startup
  - `agents/pool.py` — resolving provider instances for agent configs
  - `api/server.py` and `api/endpoints/chat.py` — API provider resolution
  - `config/repository.py` — settings-driven provider resolution

## Recommended contract test

Add to a new or existing provider contract file:

```python
def test_provider_registry_contract():
    """ProviderRegistry must satisfy the registration/lookup contract."""
    registry = ProviderRegistry()

    # Register
    registry.register("test_provider", MockProvider)
    assert "test_provider" in registry.list_providers()

    # Get
    provider_class = registry.get("test_provider")
    assert provider_class == MockProvider

    # Get raises for missing
    with pytest.raises(KeyError):
        registry.get("nonexistent")

    # Create
    provider = registry.create("test_provider", api_key="test")
    assert isinstance(provider, MockProvider)


def test_default_registry_contract():
    """get_default_registry() must contain all built-in providers."""
    registry = get_default_registry()
    providers = registry.list_providers()
    for name in ["anthropic", "openai", "deepseek", "ollama", "openrouter"]:
        assert name in providers
```

## Existing coverage

The explicit provider contract tests (anthropic, deepseek, ollama, openai,
openrouter) test the provider implementations. The **registry itself** is the gap.

## Priority

Low — the registry is simple and unlikely to change shape. The risk is that
a new provider is added to `get_default_registry()` in one place but the
enumeration `list_providers()` is expected to match somewhere else.
