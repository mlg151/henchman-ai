# Missing Contract: Task Ledger Records (DelegationRecord, ChecklistItem)

**Severity:** Medium  
**Location:** `src/henchman/agents/ledger.py`  
**Source types:** `DelegationRecord`, `ChecklistItem`, `ProgressCounts`

## The gap

`src/henchman/agents/ledger.py` defines dataclasses used for the delegation
ledger. These are formatted into user-facing strings via `render()` and
`mission_recap()` but also serialized during delegation handoff. **No contract
test exists for their serialized shape.**

`DelegationRecord` stores the delegation status (an enum), agent name, task
summary, and metadata. `ChecklistItem` stores a task item with completion state.
These are consumed in the REPL output pipeline and in the orchestrator's
completion assessment.

## What's consumed

- `orchestrator_execution.py` reads delegation records for completion assessment.
- `orchestrator_events.py` emits events based on ledger state.
- User-facing `render()` produces formatted output consumed by the CLI renderer.

## Recommended contract schema

Create `tests/contracts/schemas/runtime/ledger_record.json` and
`tests/contracts/schemas/runtime/delegation_record.json`.

## Recommended contract test

Add a new file `tests/contracts/test_ledger_contracts.py`:

```python
def test_delegation_record_matches_contract(contract_suite):
    record = DelegationRecord(agent="coder", task="Write parser")
    ledger = TaskLedger()
    ledger.complete_delegation(record, "Done")
    payload = asdict(record)
    # Note: DelegationRecord may need a to_dict() method
    assert_contract_matches(
        payload=payload,
        schema_name="runtime/delegation_record",
        contract_suite=contract_suite,
    )
```

## Note

Neither `DelegationRecord` nor `ChecklistItem` are `SerializableDataclass`
subclasses. They lack `to_dict()`. Contracts would guard _when_ they gain
persistence — currently a low-but-real risk given cross-module dict access.
