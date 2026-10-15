# Missing Contract: Utils Compaction and Intelligent Context Payloads

**Severity:** Medium  
**Location:** `src/henchman/utils/compaction.py`, `src/henchman/utils/intelligent_context.py`, `src/henchman/utils/intelligent_context_types.py`

## The gap

The `utils/compaction.py` module defines `CompactionResult` (with fields like
`compacted`, `original_count`, `compacted_count`, `original_tokens`,
`compacted_tokens`, etc.) — a dataclass that is the **primary return type**
of the message compaction pipeline.

Similarly, `intelligent_context_types.py` defines `IntelligentCompactionResult`
and related types (`CompressionConfig`, `PreservedContent`, `ResultCreationParams`).

The existing `test_context_contracts.py` only validates the compaction result
of `IntelligentContextManager` against a `context/compaction_result.json` schema.
**The `ContextCompactor.compact_with_result()` method's return type has no
contract test.**

## What's consumed

- `CompactionResult` is consumed by `core/agent.py` in the compaction pipeline.
- `IntelligentCompactionResult` is consumed by `IntelligentContextManager`
  callers in `utils/intelligent_context.py`.
- Both result types flow into the agent loop for context window management.

## Recommended contract test

Add to `tests/contracts/test_context_contracts.py`:

```python
def test_compaction_result_matches_contract(contract_suite):
    """ContextCompactor.compact_with_result() must produce a contract-compliant result."""
    compactor = ContextCompactor(max_tokens=100)
    messages = [
        Message(role="system", content="You are helpful."),
        Message(role="user", content="Hello " * 50),
    ]
    result = compactor.compact_with_result(messages)
    assert_contract_matches(
        payload=serialize_contract_value(result),
        schema_name="context/compaction_result",
        contract_suite=contract_suite,
    )
```

## Existing schema

The `context/compaction_result.json` schema already exists. The gap is that it's
only tested against the `IntelligentContextManager` path, not the
`ContextCompactor` path.
