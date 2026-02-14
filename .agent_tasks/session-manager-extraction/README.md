# Session Manager Extraction Task

## Objective
Extract session management concerns from the REPL class into a separate ReplSessionManager class.

## Current Status
Analyzing REPL class to identify all session management logic.

## Files to Modify
1. Create new file: `src/henchman/cli/session_manager.py` with ReplSessionManager class
2. Update `src/henchman/cli/repl.py` to use ReplSessionManager
3. Ensure tests pass: `tests/cli/test_repl.py`

## Session Management Logic in REPL
Based on initial analysis:

### Attributes in REPL:
- `self.session_manager: SessionManager | None = None` (core SessionManager)
- `self.session: Session | None = None` (current session)

### Methods to extract:
1. `set_session(self, session: Session) -> None` - Sets current session and syncs with agent history
2. `_auto_save_session(self) -> None` - Auto-saves session if enabled and has content

### Session usage patterns:
1. Session message recording in `_run_agent`, `_run_agent_direct`, `_process_agent_stream`
2. Session access in `_get_toolbar_status`, `_get_rich_status_message`
3. Session manager usage in command context setup

## Design Approach
Create `ReplSessionManager` that:
- Wraps core `SessionManager`
- Manages auto-save logic
- Handles session state tracking
- Provides methods for session creation/loading
- Manages session-message-agent history synchronization

## Exit Conditions
1. New ReplSessionManager class exists in src/henchman/cli/session_manager.py
2. REPL class uses ReplSessionManager instead of direct session management
3. All tests pass (run pytest tests/cli/test_repl.py)
4. No breaking changes to public API