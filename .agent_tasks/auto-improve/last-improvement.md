# Auto-Improvement Summary

## Date/Time
2024-12-30

## Files Changed
1. `src/henchman/cli/repl.py` - Added `agent_role` field to `ReplConfig` class
2. `src/henchman/cli/app.py` - Updated `_run_textual_tui` to pass `agent_role` to `TextualConfig`
3. `src/henchman/cli/textual_app.py` - Updated `_run_orchestrator` to use `agent_role` when specified
4. `tests/cli/test_app.py` - Fixed tests to include `chat` subcommand in CLI invocations
5. `tests/cli/test_app_extended.py` - Fixed test to include `chat` subcommand

## Rationale
The TODO comment in `app.py` said "Add agent_role support to Textual TUI" with a warning message when `agent_role` was provided. The Textual TUI didn't support the `agent_role` parameter that other modes (headless, interactive) supported.

## Changes Made
1. **Added agent_role field to ReplConfig**: This allows the configuration to store which agent role to target for all inputs in a session.

2. **Updated Textual TUI configuration**: The `_run_textual_tui` function now passes the `agent_role` parameter to `TextualConfig`, removing the warning message.

3. **Implemented agent_role usage in Textual TUI**: Modified `_run_orchestrator` in `textual_app.py` to check if `agent_role` is set in the config. If set, it uses `orchestrator.run_direct(agent_role, text)` instead of `orchestrator.run(text)`. This makes the Textual TUI target the specified agent for all user inputs, similar to how headless mode works.

4. **Fixed broken tests**: Several tests were invoking the CLI incorrectly (e.g., `henchman --plan` instead of `henchman chat --plan`). Fixed them to include the `chat` subcommand. These tests were failing because they were testing the wrong CLI invocation pattern.

## Impact
- Textual TUI now supports the `--agent` parameter like other modes
- When `--agent <role>` is specified, the Textual TUI will target that specific agent for all user inputs
- This enables users to work with specialist agents directly through the Textual TUI interface
- The implementation is consistent with how headless mode handles `agent_role`

## Testing
All tests pass after the fixes. The implementation maintains backward compatibility - when `agent_role` is not specified, the Textual TUI behaves as before (using the default orchestrator).