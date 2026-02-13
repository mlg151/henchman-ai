# Henchman Alpha Test Log
**Date:** 2026-02-02
**Tester:** Senior Principal QA Lead

## Objectives
- Verify architectural constraints.
- specific tool usage patterns.
- Test self-correction capabilities.
- Verify context maintenance.

## Issues Found

### 1. Session Management Completely Missing in CLI
**Severity:** Critical
**Description:** `app.py` does not initialize `SessionManager` or `Session` for `Repl`. As a result, conversation history is not recorded or saved to disk by default.
**Impact:** Users lose all conversation history when the CLI exits.

### 2. Session Loading Amnesia
**Severity:** High
**Description:** When a session is loaded (manually or via `/chat resume`), the `Agent.messages` history is not automatically synced with the loaded session's history. While `/chat resume` attempts to do this, it doesn't update `Repl.session`, leading to inconsistent state.
**Impact:** Context loss and failed auto-saves for resumed sessions.

### 4. Interrupted Turn Inconsistency
**Severity:** High
**Description:** If a turn is interrupted (e.g., Ctrl+C) during tool execution, the assistant message is recorded in the session with tool calls, but no tool results are added.
**Impact:** Resuming such a session creates an invalid message sequence for most LLM providers (OpenAI requires responses for all tool calls), causing the next turn to fail with an API error.

### 5. Brittle Tool Execution Loop
**Severity:** Medium
**Description:** `Repl` executes tool calls sequentially instead of using `ToolRegistry.execute_batch`.
**Impact:** Significant performance penalty when multiple independent tools are called in a single turn.

### 6. Duplication Risk in Context Compaction
**Severity:** Low/Medium
**Description:** The `ContextCompactor` extracts system messages to prepend them to the result, but also includes them in the first atomic sequence. If the first sequence is kept, the system message is duplicated.
**Impact:** Minor token waste, but could potentially confuse some sensitive models.

### 7. Missing Tool Confirmation Handler
**Severity:** Critical (Security)
**Description:** The CLI does not set a confirmation handler on the `ToolRegistry`. Consequently, tools marked as `WRITE`, `EXECUTE`, or `NETWORK` (like `shell` or `write_file`) are executed immediately without any user oversight.
**Impact:** Highly dangerous. The agent can run arbitrary shell commands or modify any file without the user being able to stop it.

## Summary for Development Team
The core agent logic and loop protection are robust, but the **CLI integration layer** is currently an "Alpha" state with broken session persistence and context handling. Priority should be given to wiring up `SessionManager` in `app.py` and ensuring `Agent.messages` is always synced with `Repl.session.messages`.

