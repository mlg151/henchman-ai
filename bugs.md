# Bug Tracker

## Legend
- **Severity:** critical | high | medium | low
- **Status:** open | in-progress | resolved

---

## Open Bugs

### BUG-004: MCP manager silently swallows server connection failures
- **Severity:** medium
- **Status:** open
- **Found:** 2026-05-31
- **File:** `src/henchman/mcp/manager.py:63`
- **Replication:**
  1. Configure an MCP server with invalid credentials or unreachable endpoint
  2. Start the application
  3. No error, warning, or diagnostic output is produced — the server simply doesn't appear
- **Description:**
  `MCPManager.connect_all()` iterates configured servers and calls `connect_server()` for each. Any exception during connection is caught by a bare `except Exception: continue` with no logging. The module has no logger at all. This means MCP server connection failures (network errors, auth failures, config issues) are completely invisible to users — there is no way to diagnose why a configured MCP server isn't working.

---

## Resolved Bugs

### BUG-003: `DelegationManager.wait_for_delegation` raises exception when delegation failed
- **Severity:** medium
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `src/henchman/agents/delegation_manager.py:253-254`
- **Root Cause:**
  When `_run_delegation` catches an exception, it calls `task_future.set_exception(e)` and sets `task.completed = True`. The fast path in `wait_for_delegation` (line 253: `task.completed and task.task_future.done()`) then calls `task_future.result()` which re-raises the original exception, violating the method contract to return `tuple[str, bool]`.
- **Fix:**
  Wrapped the completed-task fast path in `try/except (asyncio.CancelledError, Exception)` that converts exceptions to `(f"Delegation failed: {error_msg}", False)` tuples. The `asyncio.wait_for` path is left unwrapped so `TimeoutError` propagates naturally as documented.
- **Verification:** All 17 delegation manager tests pass, full suite 2773 passed.

### BUG-002: `test_skill_tool_rejects_unknown_skill` test assertion too strict
- **Severity:** low
- **Status:** resolved
- **Resolved:** 2026-05-31
- **Found:** 2026-05-31
- **File:** `tests/tools/test_tier1_tools.py:167`
- **Root Cause:**
  The test asserted `"Available skills: planner"` in the error message, but `SkillTool._list_available_skills()` merges both handler-backed skills AND catalog-discovered skills (from `SkillCatalog.list_skills()`). The catalog picks up real project skills like `discord-message`, so the full message read `"Available skills: discord-message, planner."`.
- **Fix:**
  Changed the assertion to `assert "planner" in result.content` — verifying the registered handler name appears in the available-skills list without assuming it's the only entry.
- **Verification:** All 3 SkillTool tests pass, full suite 2773 passed, 0 failed.

### BUG-001: `SerializableDataclass.from_dict` fails on nested dataclasses with `| None` syntax
- **Severity:** high
- **Status:** resolved
- **Resolved:** 2026-05-31
- **File:** `src/henchman/utils/serialization.py`
- **Root Cause:**
  `_deserialize_val` checked `origin is Union` (imported from `typing`), but Python 3.10+ `X | None` syntax produces `types.UnionType`, not `typing.Union`. Nested dataclass fields declared with `| None` were never deserialized — the raw dict was returned instead of the dataclass instance.
- **Fix:**
  1. Added `import types` at top of file
  2. Changed `if origin is Union:` to `if origin in (Union, types.UnionType):` on line 62
- **Verification:** All 12 contract tests pass, full test suite (2483+ tests) has no regression from this change.
