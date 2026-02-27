# Refactoring: src/henchman/agents/orchestrator.py
**Date/Time**: 2026-02-27T20:45:00Z
**Files Changed**: src/henchman/agents/orchestrator.py

## Working Memory

### Current Task: Refactor orchestrator.py to address all code smells
**Task Objectives**:
1. Fix Feature Envy issues (7 instances)
2. Fix Long Method issues (2 instances)
3. Fix Duplicate Code issues (2 instances)
4. Fix Large Class issue (Orchestrator class too large)
5. Fix Complex Function issues (cyclomatic complexity)

**Recent Files**:
- `src/henchman/agents/orchestrator.py`: Full file analysis, 1089 lines, 12 classes
- `.agent_tasks/auto-improve/smell-report.md`: Smell analysis showing 77 smells

**Active Context**:
- Project: Henchman-AI multi-agent CLI
- Architecture: Orchestrator coordinates Tech Lead and specialist agents
- Key patterns: Event-driven async execution, delegation system, metrics tracking
- Constraints: Must maintain backward compatibility, all tests must pass

**Decisions Made**:
1. Will extract helper methods from long functions
2. Will move Feature Envy methods to appropriate classes
3. Will eliminate duplicate code by extracting shared logic
4. Will consider extracting subclasses from Orchestrator

**Completed Steps**:
1. ✅ Analyzed file structure and smell report
2. ✅ Ran tests to establish baseline (53 tests pass)

**Next Actions**:
1. Extract helper methods from `run_agent_loop` (63 lines)
2. Extract helper methods from `_run_agent_loop` (71 lines)
3. Merge duplicate colon stall checking logic
4. Merge duplicate turn limit enforcement logic
5. Address Feature Envy in static methods
6. Consider extracting subclasses from Orchestrator

**Insights Gained**:
- Many static methods exhibit Feature Envy because they operate on parameters rather than self
- Duplicate code exists between ExecutionController and Orchestrator methods
- The class is already well-structured with separate components (Validator, ToolController, ExecutionController)

**Problems Encountered**: None yet

## Refactoring Strategy

### Phase 1: Extract Helper Methods from Long Functions
- Extract `_process_agent_events_and_tools` from `run_agent_loop`
- Extract `_handle_no_pending_tools` from `run_agent_loop`
- Extract `_execute_pending_tools` from `run_agent_loop`

### Phase 2: Address Feature Envy
- Move `PromptFactory.create_tech_lead_prompt` logic to where `c` is owned
- Move `TimeoutSummaryBuilder._format_summary` to work with `self`
- Move `AgentValidator.check_stall_failure` to Agent class
- Move `ToolController.execute_regular_tool` helper logic
- Move `ToolController.prepare_delegation_brief` to ToolCall class
- Move `ExecutionController.enforce_turn_limits` to TurnEnforcementParams
- Move `Orchestrator._enforce_turn_limits` to TurnEnforcementParams
- Move `Orchestrator._run_agent_loop` state handling to LoopState

### Phase 3: Eliminate Duplicate Code
- Extract shared colon stall logic to `_check_colon_stall_common`
- Extract shared turn limit logic to `_enforce_turn_limits_common`

### Phase 4: Reduce Class Size
- Extract `OrchestratorInitializer` class for initialization logic
- Extract `OrchestratorRunner` class for execution logic

### Phase 5: Improve Readability
- Rename variables for clarity
- Add type hints where missing
- Extract magic numbers to constants

## Testing Implications
- Need to ensure all 53 existing tests still pass
- May need to update tests that directly call refactored methods
- Should add tests for new extracted helper methods
- Edge cases: colon stall detection, turn limits, delegation handling