# Missing Contract: Config Context Loader Payloads

**Severity:** Low  
**Location:** `src/henchman/config/context.py`  
**Source types:** `ContextLoader`

## The gap

`ContextLoader` discovers and loads prompt-context files (e.g., `HENCHMAN.md`)
from project directories. Its outputs (list of discovered paths, concatenated
content string) are consumed by the CLI startup pipeline and orchestrator
initialization.

While the return type is a simple string, **there's no contract test** verifying
the deterministic ordering and deduplication guarantees of the output. This is
a functional contract rather than a shape contract.

## What's consumed

- `cli/core_init.py` consumes the loaded context for system prompt construction.
- The orchestrator uses context for agent system prompts.

## Recommended contract test

Rather than a JSON schema, this boundary needs a behavioral contract test:

```python
def test_context_loader_deterministic_order(tmp_path):
    """ContextLoader should discover files in deterministic order."""
    (tmp_path / ".henchman").mkdir()
    (tmp_path / ".henchman" / "A.md").write_text("a")
    (tmp_path / ".henchman" / "B.md").write_text("b")
    loader = ContextLoader(start_dir=tmp_path)
    files = loader.discover_files()
    assert files == [tmp_path / ".henchman" / "A.md", tmp_path / ".henchman" / "B.md"]
```

## Existing test coverage

There are existing tests in `tests/config/` but they focus on file discovery,
not the contractual guarantees (ordering, deduplication, naming conventions).

## Priority

Low — the risk of breakage is minimal since the output shape is simple.
