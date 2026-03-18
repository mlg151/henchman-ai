# Four Lenses Bug Report: src/henchman/cli/textual_mixins.py
## Date: 2024-01-15T00:00:00Z
## Bug Summary
TOCTOU (Time-Of-Check-Time-Of-Use) race condition in `_cleanup_confirm_futures` method where `hasattr` check is not atomic with attribute access, potentially causing AttributeError during application shutdown.

## Lens
Phase 1: The Intent vs. Reality Check - Logic Gaps

## Expected vs. Observed
| Expected Behavior | Observed Risk |
|---|---|
| `_cleanup_confirm_futures` should safely clean up pending confirmation futures even in concurrent scenarios | Between `hasattr(self, '_confirm_futures')` check and `futures_dict = self._confirm_futures` access, another thread could delete the attribute or set it to `None`, causing AttributeError |
| Application shutdown should be graceful without crashes | AttributeError could crash during shutdown if `_confirm_futures` attribute is deleted between check and use |

## Root Cause
The method uses a non-atomic pattern:
```python
if not hasattr(self, '_confirm_futures'):
    return  # Nothing to clean up
futures_dict = self._confirm_futures  # TOCTOU: attribute could be deleted here
```

In concurrent execution (especially during application shutdown), another thread could:
1. Delete `_confirm_futures` attribute
2. Set `_confirm_futures = None` 
3. Delete the object entirely

Between the `hasattr` check and the attribute access, the attribute state can change, leading to `AttributeError: '_InitMixin' object has no attribute '_confirm_futures'` or `AttributeError: 'NoneType' object has no attribute 'keys'`.

## Fix Plan
Replace the non-atomic `hasattr` + attribute access pattern with a single atomic operation using `getattr` with a default value:
```python
futures_dict = getattr(self, '_confirm_futures', None)
if futures_dict is None:
    return
```

This ensures atomic retrieval of the attribute value and handles the case where the attribute doesn't exist or is `None`.

## Status: IN PROGRESS