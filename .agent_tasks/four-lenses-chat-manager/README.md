# Four Lenses Bug Report: src/henchman/chat/manager.py
## Date: 2025-04-11T00:00:00Z
## Bug Summary
The `_get_provider_settings` method returns an empty dict `{}` for unknown provider names, but the provider registry's `create` method requires at least a model parameter for most providers. This causes a silent failure when creating agents for users.

## Lens
**Phase 1: The Intent vs. Reality Check** - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| When provider settings are missing, the method should return reasonable defaults with at least a model parameter | Returns empty dict `{}` which causes provider creation to fail |
| Unknown providers should either raise an error or return defaults | Returns empty dict, leading to downstream failures |
| The code should handle missing settings gracefully | Silent failure with no clear error message |

## Root Cause
The `_get_provider_settings` method has a logic gap at line 123-124:
```python
if provider_name not in provider_settings_map:
    return {}
```

This returns an empty dict for unknown providers, but the provider registry's `create` method expects certain parameters (like `model`) for most providers. When `registry.create(provider_name, **{})` is called with an empty dict, it may fail silently or with a cryptic error.

## Fix Plan
1. Change the return statement for unknown providers from `return {}` to return reasonable defaults with at least a `model` parameter.
2. Add logging to warn about unknown providers.
3. Ensure the fix doesn't break existing tests that expect `{}` for unknown providers.

## Status: IN PROGRESS