# Missing Contract: Ops Flags and AppState Payloads

**Severity:** Low–Medium  
**Location:** `src/henchman/ops/flags.py`, `src/henchman/ops/state.py`  
**Source types:** `FeatureFlagService`, `AppStateStore`

## The gap

`FeatureFlagService` stores and retrieves feature flag state as boolean values
with string keys and source metadata. `AppStateStore` persists arbitrary
key-value state.

Neither service validates payload shape against a schema, and **neither has
a contract test** for their persisted/returned payloads. The flags service in
particular returns dicts with structure `{"flag_name": {"enabled": bool, "source": str}}`.

## What's consumed

- Feature flags influence runtime toggles in `cli/`, `api/`, and `tools/` subsystems.
- AppState is consumed by `ops/migrations.py`.
- Both feed into the `ops/store.py` persistence layer.

## Recommended contract

Add schema tests for:

1. **Flag state shape**: `tests/contracts/schemas/ops/flag_state.json`
2. **App state shape**: `tests/contracts/schemas/ops/app_state.json`

## Recommended contract test

```python
def test_feature_flag_payload_matches_contract(contract_suite, ops_store):
    service = FeatureFlagService(store=ops_store)
    service.set_flag("advanced_mode", True, source="env")
    payload = service.is_enabled("advanced_mode")
    # Not a dict — consider testing the internal state dict instead
    # via store iteration
    ...
```

## Caveat

These are simpler boundaries. The current risk is low because the values are
simple booleans, but they should still be schema-verified for safety if the
shape ever becomes more complex.
