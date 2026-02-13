# Beta Testing Issues Report

**Date:** 2026-02-02
**Tester:** Gemini CLI

## Summary
The Henchman CLI (v0.1.11) shows significant improvements over the Alpha state. Session persistence is functional (files are saved), and tool confirmation workflows are implemented. However, critical CLI commands for managing sessions and MCP servers are missing from the registry, making it impossible to manage sessions or MCP connections interactively.

## Issues Found

### 1. Missing `/chat` Command
**Severity:** High
**Description:** The `/chat` command (implemented in `src/henchman/cli/commands/chat.py`) is not registered in `src/henchman/cli/commands/builtins.py`.
**Impact:** Users cannot save, list, or resume sessions interactively. The `ChatCommand` class exists but is unreachable.
**Reproduction:**
```bash
henchman
> /chat list
✗ Unknown command: /chat
```

### 2. Missing `/mcp` Command
**Severity:** Medium
**Description:** The `/mcp` command (implemented in `src/henchman/cli/commands/mcp.py`) is not registered in `src/henchman/cli/commands/builtins.py`.
**Impact:** Users cannot manage or inspect Model Context Protocol (MCP) servers interactively.
**Reproduction:**
```bash
henchman
> /mcp list
✗ Unknown command: /mcp
```

### 3. Session Resume Requires Tags
**Severity:** Medium
**Description:** The `/chat resume` command implementation only supports loading by `tag` (`manager.load_by_tag`). It does not appear to support loading by Session ID. Since sessions are created without tags by default, users cannot easily resume a specific previous session without manually editing the session file to add a tag or implementing a tagging workflow.
**Impact:** Resuming the "last session" or a specific untitled session is difficult/impossible via the CLI.
**Location:** `src/henchman/cli/commands/chat.py`, `_resume` method.

### 4. Cosmetic: CLI Self-Identification
**Severity:** Low
**Description:** `henchman --version` output identifies as `mlg`.
**Output:** `mlg, version 0.1.11`
**Expected:** `henchman, version 0.1.11`

## Verification of Alpha Issues

- **Session Management Missing:** [FIXED] `SessionManager` is correctly initialized in `app.py`, and session files are created in `~/.henchman/sessions`.
- **Missing Tool Confirmation Handler:** [FIXED] `ToolRegistry.set_confirmation_handler` is called in `Repl.__init__`, and prompts are displayed for dangerous tools (verified with `write_file`).
- **Session Loading Amnesia:** [PARTIALLY VERIFIED] Could not fully verify due to missing `/chat` command, but code inspection of `ChatCommand._resume` suggests it now correctly syncs `Repl.session` and `Agent.messages`.

## Recommendations

1.  **Register Missing Commands:** Add `ChatCommand()` and `McpCommand()` to the list returned by `get_builtin_commands()` in `src/henchman/cli/commands/builtins.py`.
2.  **Enhance Resume:** Modify `ChatCommand._resume` to try loading by ID if loading by tag fails, or add a separate `load` subcommand that accepts IDs.
3.  **Auto-Resume:** Consider an option or flag (e.g., `henchman --resume`) to automatically load the most recent session.
