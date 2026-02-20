1.  **Esc should immediately halt processing and return to the prompt.**
    *   **Fix:** `Repl.run()` was updated to distinguish between `KeyboardInterrupt` (Ctrl+C, which exits the REPL) and `KeyMonitor.stop_requested` (Esc key, which interrupts the current agent operation and returns to the prompt). Related tests were refactored to simulate Esc using `monitor.stop_requested = True` in `_run_agent`.

2.  **Web Search Tool Integration.**
    *   **Fix:** Integrated `DuckDuckGoSearchTool` using `aiohttp` and `beautifulsoup4` to provide web search functionality. `pyproject.toml` was updated with the new dependency.

3.  **UI Issues - Input prompt writes over output.**
    *   **Fix:** Added `self.console.print()` before `prompt_async` in `_get_input` within `src/henchman/cli/repl.py` to ensure the prompt always appears on a new line.

4.  **UI Issues - Bottom bar disappears.**
    *   **Fix:** Implemented `_get_rich_status_message` and integrated it with `rich.status.Status` in `_run_agent` and `_process_agent_stream` to maintain a persistent status bar during agent processing.

5.  **Loading sessions does not work correctly.**
    *   **Fix:** Modified the `load` method in `src/henchman/core/session.py` to support loading sessions by ID prefix in addition to exact UUIDs, enabling resumption with truncated IDs displayed in `/chat list`.

6.  **Functional testing of the `/plan` tool.**
    *   **Fix:** An E2E test (`tests/e2e/test_plan_mode_workflow.py`) was added to verify `/plan` command behavior, ensuring writes are blocked/allowed correctly based on plan mode status. The `test_cli_plan_flag` assertion was updated to reflect the new `_run_interactive` signature.

7.  **Tool execution - Shell commands hanging indefinitely.**
    *   **Fix:** Added `asyncio.CancelledError` handling to `ShellTool.execute` to ensure subprocesses are killed if the shell tool execution is interrupted. Tests were added (`tests/tools/test_shell_advanced.py`) to verify shell tool handling of pipes, redirection, and timeouts.

8.  **`AttributeError: 'Repl' object has no attribute '_get_rich_status'` failures.**
    *   **Fix:** This was primarily a Python import caching issue after refactoring `_get_rich_status` to `_get_rich_status_message`. Clearing `__pycache__` directories resolved the widespread `AttributeError`s.

9.  **`OSError: pytest: reading from stdin while output is captured!` in tool execution tests.**
    *   **Fix:** Modified relevant test setups in `tests/e2e/test_tool_fix.py` and `tests/ui_integration/test_tool_calls.py` to set `repl.config.auto_approve_tools = True`, preventing interactive confirmation prompts during automated testing.

10. **`test_version.py::test_version_tuple` version mismatch.**
    *   **Fix:** Updated the expected version tuple in `tests/test_version.py` from `(0, 1, 11)` to `(0, 1, 13)` to align with the current project version.

11. **`test_rag_command.py::TestRagCommand::test_reindex_with_rag_system` failure.**
    *   **Fix:** Corrected the mocking logic in the test to ensure `mock_repl.rag_system.index` was properly configured and its `is_indexing` attribute was set to `False`, allowing the `index` method to be called and asserted.

12. **`test_loop_protection.py::TestSpinningDetection::test_consecutive_duplicate_detection` failure.**
    *   **Fix:** Modified the test case to use a non-read-only tool (`write_file`) and increased the number of calls to correctly trigger the consecutive duplicate detection logic within `TurnState.is_spinning()`.