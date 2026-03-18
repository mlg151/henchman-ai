# TUI Markup Bug Fix

## Problem
Rich markup like `[bold]Henchman-AI[/bold]` appears literally in the TUI welcome message instead of being rendered as bold text.

## Root Cause
`ChatMessage._render_plain_text()` passes all content through `_safe_markup()` which escapes `[` to `\[`, preventing Rich markup rendering.

## TDD Plan
1. **RED**: Write failing test that asserts Rich markup renders correctly
2. **YELLOW**: Fix the rendering to support trusted markup
3. **GREEN**: Verify all tests pass
