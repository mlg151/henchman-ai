# Bug Tracker

## Legend
- **Severity:** critical | high | medium | low
- **Status:** open | in-progress | resolved

---

## Open Bugs

_None_

---

## Resolved Bugs

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
