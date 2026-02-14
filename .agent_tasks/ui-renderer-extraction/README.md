# UI Renderer Extraction Task

## Objective
Extract UI rendering concerns from the REPL class into a separate UIRenderer class.

## Current State
- REPL class is 911 lines and mixes UI concerns with agent coordination and session management
- UI rendering is handled through self.renderer (OutputRenderer) and various _print_* methods
- Methods to extract: _print_welcome(), _print_goodbye(), _get_rich_status_message()
- REPL uses self.renderer directly for various UI operations

## Plan
1. Create new UIRenderer class in src/henchman/cli/ui_renderer.py
2. UIRenderer should wrap OutputRenderer and add REPL-specific UI methods
3. Move UI rendering logic from REPL to UIRenderer
4. Update REPL to use UIRenderer instance instead of direct OutputRenderer calls
5. Ensure all tests pass

## Exit Conditions
1. New UIRenderer class exists in src/henchman/cli/ui_renderer.py
2. REPL class uses UIRenderer instead of direct self.renderer calls
3. All tests pass (run pytest tests/cli/test_repl.py)
4. No breaking changes to public API

## Status
IN PROGRESS