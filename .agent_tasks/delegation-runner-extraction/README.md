# DelegationRunner Extraction Research

**Status**: Research complete  
**Date**: 2025-02-27  
**Source file**: `src/henchman/agents/orchestrator.py` (1943 lines)

---

## 1. Delegation-Only Methods (Candidates for Extraction)

These methods are ONLY called by delegation code paths.

| # | Method | Line | Signature | self.* Attributes Accessed |
|---|--------|------|-----------|---------------------------|
| 1 | `_execute_delegation_tool` | 1375 | `async (self, agent: Agent, tool_call: ToolCall, depth: int, tool_errors: list[str]) -> AsyncIterator[AgentEvent]` | `metrics` (via `_update_delegation_metrics`, `_update_tool_metrics`), `ledger` |
| 2 | `_prepare_delegation_brief` | 999 | `(self, tool_call: ToolCall) -> dict[str, Any]` | *(none — pure function, accesses only tool_call arg)* |
| 3 | `_update_delegation_metrics` | 1017 | `(self, target: str) -> None` | `metrics.delegation_count`, `metrics.delegation_by_type` |
| 4 | `_process_delegation_result` | 1027 | `(self, agent: Agent, tool_call: ToolCall, result_content: str, delegation_had_error: bool, ledger_record: Any \| None) -> str` | `ledger` |
| 5 | `_prepare_delegation_context` | 1482 | `(self, target_role: str, brief: dict[str, Any] \| None) -> dict[str, Any]` | `shared_context`, `ledger` |
| 6 | `_process_delegation_results` | 1533 | `(self, target_role: str, target_agent: Agent, msg_start: int) -> tuple[str, dict[str, str], CompletionStatus]` | *(calls `_parse_completion_report`, `_assess_completion`)* |
| 7 | `_run_delegation` | 1574 | `async (self, params: DelegationParams) -> AsyncIterator[AgentEvent]` | *(orchestrator entry — calls sub-methods)* |
| 8 | `_is_delegation_depth_exceeded` | 1629 | `(self, depth: int) -> bool` | `settings.agents.max_delegation_depth` |
| 9 | `_yield_depth_exceeded_error` | 1640 | `async (self) -> AsyncIterator[AgentEvent]` | `settings.agents.max_delegation_depth` |
| 10 | `_get_target_agent_with_error_handling` | 1657 | `async (self, target_role: str) -> Agent \| AgentEvent` | `pool` |
| 11 | `_yield_agent_not_found_completion` | 1673 | `async (self, target_role: str) -> AsyncIterator[AgentEvent]` | *(none — pure event factory)* |
| 12 | `_prepare_delegation_execution` | 1690 | `(self, params: DelegationParams) -> None` | `ledger` (via `_prepare_delegation_context`, `_assemble_delegation_input`) |
| 13 | `_execute_delegation_loop` | 1721 | `async (self, params: DelegationParams) -> AsyncIterator[AgentEvent]` | `settings.agents.max_delegation_turns` |
| 14 | `_finalize_delegation` | 1745 | `async (self, params: DelegationParams) -> AsyncIterator[AgentEvent]` | `shared_context` |
| 15 | `_assemble_delegation_input` | 1787 | `@staticmethod (task: str, brief: dict \| None, mission: str \| None) -> str` | **Already static** |
| 16 | `_parse_completion_report` | 1851 | `@staticmethod (summary: str) -> dict[str, str]` | **Already static** |

---

## 2. Shared Methods (Used by BOTH delegation and non-delegation code)

These are called from delegation paths BUT ALSO from `run()` / `run_direct()`:

| Method | Line | Delegation Callers | Non-Delegation Callers |
|--------|------|--------------------|----------------------|
| `_assess_completion` | 975 | `_process_delegation_results` (L1570) | `run()` (L834), `run_direct()` (L873) |
| `_update_tool_metrics` | 1139 | `_execute_delegation_tool` (L1398) | `_execute_regular_tool` (L1477) |
| `_yield_tool_result_event` | 1165 | `_execute_delegation_tool` (L1451) | `_execute_regular_tool` (L1480) |
| `_track_tool_error` | 1151 | *(not directly, but tool_errors list passed)* | `_execute_regular_tool` (L1474) |
| `_run_agent_loop` | 1192 | `_execute_delegation_loop` (L1742) | `run()` (L823), `run_direct()` (L870) |
| `_build_timeout_summary` | 1883 | *(static, used in `_enforce_turn_limits` L1109)* | `_enforce_turn_limits` (shared) |
| `_register_delegate_task_tool` | 705 | *(setup, not runtime delegation)* | `__init__` (L699) |

---

## 3. Call Graph

```
_process_pending_tool_calls (L1346)  ← dispatcher, NOT delegation-only
  └─ if tool_call.name == "delegate_task":
      └─ _execute_delegation_tool (L1375)         ★ ENTRY POINT
          ├─ _update_delegation_metrics (L1397)
          ├─ _update_tool_metrics (L1398)          ← SHARED
          ├─ _prepare_delegation_brief (L1419)
          ├─ _run_delegation (L1426)               ★ CORE
          │   ├─ _is_delegation_depth_exceeded (L1597)
          │   ├─ _yield_depth_exceeded_error (L1598)
          │   ├─ _get_target_agent_with_error_handling (L1603)
          │   ├─ _yield_agent_not_found_completion (L1606)
          │   ├─ _prepare_delegation_execution (L1619)
          │   │   ├─ _prepare_delegation_context (L1710)
          │   │   │   ├─ reads self.shared_context
          │   │   │   └─ reads self.ledger.delegations
          │   │   └─ _assemble_delegation_input (L1713) [static]
          │   ├─ _execute_delegation_loop (L1622)
          │   │   └─ _run_agent_loop (L1742)       ← SHARED (callback)
          │   └─ _finalize_delegation (L1626)
          │       ├─ _process_delegation_results (L1760)
          │       │   ├─ _parse_completion_report [static]
          │       │   └─ _assess_completion        ← SHARED
          │       └─ self.shared_context.append()
          ├─ _process_delegation_result (L1446)    (singular — handles ledger + submit)
          └─ _yield_tool_result_event (L1451)      ← SHARED
```

---

## 4. Required `self.*` Attributes

| Attribute | Type | Used By (delegation methods) |
|-----------|------|------------------------------|
| `self.pool` | `AgentPool` | `_get_target_agent_with_error_handling` |
| `self.ledger` | `TaskLedger \| None` | `_execute_delegation_tool`, `_process_delegation_result`, `_prepare_delegation_context`, `_prepare_delegation_execution`, `_process_delegation_results` (indirect) |
| `self.settings` | `Settings` | `_is_delegation_depth_exceeded` (.agents.max_delegation_depth), `_execute_delegation_loop` (.agents.max_delegation_turns) |
| `self.shared_context` | `list[dict[str, Any]]` | `_prepare_delegation_context`, `_finalize_delegation` |
| `self.metrics` | `OrchestratorMetrics` | `_update_delegation_metrics`, `_update_tool_metrics` (shared) |
| `self._last_loop_tool_call_count` | `int` | `_assess_completion` (shared — via getattr) |

---

## 5. Static Methods (Already or Could Be)

| Method | Status | Notes |
|--------|--------|-------|
| `_assemble_delegation_input` | **Already @staticmethod** | No self access |
| `_parse_completion_report` | **Already @staticmethod** | No self access |
| `_prepare_delegation_brief` | **Could be static** | Only accesses `tool_call` arg, zero `self.*` usage |
| `_yield_agent_not_found_completion` | **Could be static** | Only creates AgentEvent from args |

---

## 6. Line Count Estimate

| Method | Start | End | Lines |
|--------|-------|-----|-------|
| `_prepare_delegation_brief` | 999 | 1015 | 17 |
| `_update_delegation_metrics` | 1017 | 1025 | 9 |
| `_process_delegation_result` | 1027 | 1066 | 40 |
| `_execute_delegation_tool` | 1375 | 1453 | 79 |
| `_prepare_delegation_context` | 1482 | 1531 | 50 |
| `_process_delegation_results` | 1533 | 1572 | 40 |
| `_run_delegation` | 1574 | 1627 | 54 |
| `_is_delegation_depth_exceeded` | 1629 | 1638 | 10 |
| `_yield_depth_exceeded_error` | 1640 | 1655 | 16 |
| `_get_target_agent_with_error_handling` | 1657 | 1671 | 15 |
| `_yield_agent_not_found_completion` | 1673 | 1688 | 16 |
| `_prepare_delegation_execution` | 1690 | 1719 | 30 |
| `_execute_delegation_loop` | 1721 | 1743 | 23 |
| `_finalize_delegation` | 1745 | 1785 | 41 |
| `_assemble_delegation_input` | 1787 | 1849 | 63 |
| `_parse_completion_report` | 1851 | 1881 | 31 |
| **TOTAL** | | | **~534 lines** |

Plus `DelegationParams` dataclass (L59-81) = ~23 lines.  
Plus constants used only by delegation: `RECENT_CONTEXT_ENTRIES`, `MAX_CONTENT_LENGTH`, `MAX_SUMMARY_LENGTH`, `RECENT_ERRORS_TO_SHOW`, `_DELEGATE_TASK_TOOL`.

**Grand total: ~560 lines extractable** (29% of the 1943-line file).

---

## 7. Proposed `DelegationRunner` Design

### Constructor Dependencies (injected)

```python
class DelegationRunner:
    def __init__(
        self,
        pool: AgentPool,
        ledger: TaskLedger | None,      # mutable ref — updated per run()
        settings: Settings,
        shared_context: list[dict[str, Any]],  # mutable ref — shared with Orchestrator
        metrics: OrchestratorMetrics,
        run_agent_loop: Callable[[AgentLoopParams], AsyncIterator[AgentEvent]],  # callback
        update_tool_metrics: Callable[[str, dict, bool], None],  # callback
        yield_tool_result_event: Callable[[Agent, ToolCall, str, bool], AgentEvent],  # callback
    ):
```

### Callbacks Needed from Orchestrator

| Callback | Why |
|----------|-----|
| `_run_agent_loop(params)` | Used by `_execute_delegation_loop` to actually run the specialist |
| `_update_tool_metrics(name, args, success)` | Used by `_execute_delegation_tool` for metrics |
| `_yield_tool_result_event(agent, tc, content, success)` | Used by `_execute_delegation_tool` |
| `_assess_completion(agent)` | Used by `_process_delegation_results` — OR copy to DelegationRunner since it's simple |

### Alternative: Protocol/Interface

Instead of callbacks, define a `DelegationHost` protocol:

```python
class DelegationHost(Protocol):
    def _run_agent_loop(self, params: AgentLoopParams) -> AsyncIterator[AgentEvent]: ...
    def _update_tool_metrics(self, name: str, args: dict, success: bool) -> None: ...
    def _yield_tool_result_event(self, agent: Agent, tc: ToolCall, content: str, success: bool) -> AgentEvent: ...
    def _assess_completion(self, agent: Agent) -> CompletionStatus: ...
```

### Mutable State Concern

`self.ledger` on Orchestrator is set to `None` initially and replaced per `run()` call. The `DelegationRunner` needs a way to get the current ledger. Options:
1. **Property/getter callback**: `get_ledger: Callable[[], TaskLedger | None]`
2. **Re-inject**: Orchestrator sets `runner.ledger = ...` before each `run()`
3. **Shared reference wrapper**: Wrap in a container object

### Entry Point for Orchestrator

After extraction, the dispatch in `_process_pending_tool_calls` becomes:

```python
if tool_call.name == _DELEGATE_TASK_TOOL:
    async for event in self._delegation_runner.execute(agent, tool_call, depth, tool_errors):
        yield event
```

---

## 8. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Shared mutable `ledger` reference | Medium | Use getter callback or reset per-run |
| Shared mutable `shared_context` list | Low | Pass by reference (list is mutable) |
| `_assess_completion` is shared | Low | Duplicate into DelegationRunner (9 lines, reads only `_last_loop_tool_call_count`) |
| Test coverage — delegation tests tightly coupled to Orchestrator | Medium | Tests mock at method level; need to update imports |
| `_build_timeout_summary` is static + shared | Low | Leave on Orchestrator or move to utils |
