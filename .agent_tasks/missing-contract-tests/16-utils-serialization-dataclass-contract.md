# Missing Contract: SerializableDataclass Base Contract

**Severity:** Low  
**Location:** `src/henchman/utils/serialization.py`

## The gap

`src/henchman/utils/serialization.py` defines a `SerializableDataclass` base
class used by `WorkingMemory`, `WorkingMemoryEntry`, `DecisionEntry`,
`ActionEntry`, `ProblemEntry`, and other dataclasses. It provides a `to_dict()`
method and serialization helpers.

**No contract test** verifies:

1. That the `to_dict()` method correctly serializes nested dataclasses.
2. That `from_dict()` (or equivalent) correctly deserializes.
3. That optional fields with `None` values are handled correctly.
4. That field ordering is preserved.

## What's consumed

`SerializableDataclass` is the serialization base for:
- `WorkingMemory` and all its entry types
- Other dataclasses that inherit from it (if any)

These are consumed by the YAML persistence layer, agent loop context injectors,
and the delegation handoff pipeline.

## Recommended contract test

Create `tests/contracts/test_serialization_contract.py`:

```python
def test_serializable_dataclass_roundtrip():
    """SerializableDataclass subclasses must roundtrip via to_dict."""
    class TestData(SerializableDataclass):
        name: str
        count: int = 0
        tags: list[str] | None = None

    original = TestData(name="test", count=42, tags=["a", "b"])
    data = original.to_dict()
    assert data["name"] == "test"
    assert data["count"] == 42
    assert data["tags"] == ["a", "b"]
    
    # Verify via WorkingMemoryEntry at minimum
    entry = WorkingMemoryEntry(path="/src/main.py", purpose="test")
    data = entry.to_dict()
    assert "path" in data
    assert "purpose" in data
    assert "lines_read" in data  # optional, should be None/absent
```

## Priority

Low — the serialization contract is implicitly tested through the existing
`test_working_memory_contracts.py` tests, but there's no _base_ contract.
