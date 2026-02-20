# Phase 1 Implementation Plan: Theme System Enhancement

## Overview
Phase 1 focuses on enhancing the theme system with additional built-in themes, interactive theme management command, and theme persistence from settings.

## Current State Analysis

### Existing Theme System (`src/henchman/cli/console.py`)
- `Theme` dataclass with 7 color properties
- `ThemeManager` with only `dark` and `light` themes
- `OutputRenderer` uses theme for styling
- `UIRenderer` wraps `OutputRenderer` for REPL-specific UI

### Current Limitations
1. Only 2 themes available (dark, light)
2. No interactive theme management command
3. Theme not loaded from settings
4. No theme persistence across sessions
5. No theme preview functionality

## Implementation Tasks

### Task 1.1: Add Additional Built-in Themes
**File**: `src/henchman/cli/console.py`
**Objective**: Add 6 new themes to ThemeManager

**New Themes to Add**:
1. `solarized-dark` - Solarized dark theme
2. `solarized-light` - Solarized light theme  
3. `monokai` - Monokai theme
4. `dracula` - Dracula theme
5. `high-contrast-dark` - High contrast dark theme
6. `high-contrast-light` - High contrast light theme

**Implementation Steps**:
1. Add theme definitions after `LIGHT_THEME` in console.py
2. Update `ThemeManager.__init__` to include new themes
3. Add tests for new themes in `tests/cli/test_console.py`
4. Verify all themes can be retrieved and listed

**Code Changes**:
```python
# After LIGHT_THEME definition in console.py
SOLARIZED_DARK = Theme(
    name="solarized-dark",
    primary="cyan",
    secondary="blue",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_black"
)

SOLARIZED_LIGHT = Theme(
    name="solarized-light",
    primary="cyan",
    secondary="blue",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_black"
)

MONOKAI = Theme(
    name="monokai",
    primary="magenta",
    secondary="cyan",
    success="green",
    warning="yellow",
    error="red",
    muted="white"
)

DRACULA = Theme(
    name="dracula",
    primary="purple",
    secondary="pink",
    success="green",
    warning="yellow",
    error="red",
    muted="bright_white"
)

HIGH_CONTRAST_DARK = Theme(
    name="high-contrast-dark",
    primary="white",
    secondary="bright_white",
    success="bright_green",
    warning="bright_yellow",
    error="bright_red",
    muted="white"
)

HIGH_CONTRAST_LIGHT = Theme(
    name="high-contrast-light",
    primary="black",
    secondary="bright_black",
    success="green",
    warning="yellow",
    error="red",
    muted="black"
)

# Update ThemeManager.__init__
class ThemeManager:
    def __init__(self) -> None:
        """Initialize the theme manager with default themes."""
        self._themes: dict[str, Theme] = {
            "dark": DARK_THEME,
            "light": LIGHT_THEME,
            "solarized-dark": SOLARIZED_DARK,
            "solarized-light": SOLARIZED_LIGHT,
            "monokai": MONOKAI,
            "dracula": DRACULA,
            "high-contrast-dark": HIGH_CONTRAST_DARK,
            "high-contrast-light": HIGH_CONTRAST_LIGHT,
        }
        self._current: Theme = DARK_THEME
```

### Task 1.2: Create Theme Command
**File**: `src/henchman/cli/commands/theme.py` (new)
**Objective**: Implement `/theme` slash command for interactive theme management

**Command Features**:
1. `/theme list` - List all available themes with current theme highlighted
2. `/theme set <name>` - Set active theme
3. `/theme preview <name>` - Preview a theme with sample output
4. `/theme help` - Show help for theme command

**Implementation Steps**:
1. Create `theme.py` file in `src/henchman/cli/commands/`
2. Implement `ThemeCommand` class with Command interface
3. Register command in `builtins.py`
4. Add tests in `tests/cli/test_theme_command.py`

**Code Structure**:
```python
"""Theme management command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.cli.commands import Command, CommandContext

if TYPE_CHECKING:
    from henchman.cli.console import ThemeManager


class ThemeCommand(Command):
    """Manage UI themes."""
    
    @property
    def name(self) -> str:
        return "theme"
    
    @property 
    def description(self) -> str:
        return "Manage UI themes (list, set, preview)"
    
    async def execute(self, ctx: CommandContext) -> None:
        # Implementation here
        pass
    
    async def _list_themes(self, ctx: CommandContext) -> None:
        """List available themes."""
        pass
    
    async def _set_theme(self, ctx: CommandContext, theme_name: str) -> None:
        """Set the active theme."""
        pass
    
    async def _preview_theme(self, ctx: CommandContext, theme_name: str) -> None:
        """Preview a theme with sample output."""
        pass
```

**Registration in `builtins.py`**:
```python
# Add import at top
from henchman.cli.commands.theme import ThemeCommand

# Update get_builtin_commands
def get_builtin_commands() -> list[Command]:
    return [
        HelpCommand(),
        QuitCommand(),
        ClearCommand(),
        ToolsCommand(),
        ThemeCommand(),  # Add this line
        AgentCommand(),
        TeamCommand(),
        ChatCommand(),
        McpCommand(),
        ModelCommand(),
        PlanCommand(),
        RagCommand(),
        UnlimitedCommand(),
    ]
```

### Task 1.3: Apply Theme from Settings
**File**: `src/henchman/cli/app.py` and `src/henchman/cli/repl.py`
**Objective**: Load theme from settings and apply it to renderer

**Implementation Steps**:
1. In `app.py`, load theme from settings after loading settings
2. Create ThemeManager and set theme from settings
3. Create OutputRenderer with the selected theme
4. Pass themed renderer to REPL constructor
5. Update REPL to accept custom renderer parameter
6. Handle invalid theme name (fall back to default with warning)

**Code Changes**:

**In `app.py` (_run_interactive function)**:
```python
def _run_interactive(...):
    # ... existing code ...
    settings = load_settings()
    
    # Create theme-aware renderer
    from henchman.cli.console import ThemeManager, OutputRenderer
    theme_manager = ThemeManager()
    
    # Try to set theme from settings, fall back to default
    theme_name = settings.ui.theme if settings and settings.ui else "dark"
    if theme_name not in theme_manager.list_themes():
        console.print(f"[yellow]Warning: Theme '{theme_name}' not found. Using default theme.[/]")
        theme_name = "dark"
    
    theme_manager.set_theme(theme_name)
    theme = theme_manager.current
    
    # Create renderer with theme
    renderer = OutputRenderer(console=console, theme=theme)
    
    # Pass renderer to REPL
    config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
    repl = Repl(
        provider=provider,
        console=console,
        config=config,
        settings=settings,
        environment_context=env_block,
        renderer=renderer,  # Pass custom renderer
    )
    # ... rest of function ...
```

**In `repl.py` (update __init__ method)**:
```python
def __init__(
    self,
    provider: ModelProvider,
    console: Console | None = None,
    config: ReplConfig | None = None,
    settings: Settings | None = None,
    environment_context: str | None = None,
    renderer: UIRenderer | None = None,  # Add this parameter
) -> None:
    # ... existing code ...
    
    # Use provided renderer or create default
    if renderer:
        self.renderer = renderer
    else:
        self.renderer = UIRenderer(console=self.console)
    
    # ... rest of initialization ...
```

### Task 1.4: Theme Persistence
**File**: `src/henchman/cli/commands/theme.py` and settings system
**Objective**: Save theme changes to settings file

**Implementation Steps**:
1. In `ThemeCommand._set_theme`, update settings if available
2. Save settings to disk after theme change
3. Show confirmation message that theme will persist

**Code Changes**:
```python
async def _set_theme(self, ctx: CommandContext, theme_name: str) -> None:
    """Set the active theme."""
    from henchman.cli.console import ThemeManager
    
    manager = ThemeManager()
    
    if theme_name not in manager.list_themes():
        ctx.console.print(f"[red]Error: Theme '{theme_name}' not found[/]")
        ctx.console.print("Use '/theme list' to see available themes.")
        return
    
    manager.set_theme(theme_name)
    
    # Update renderer theme if available
    if hasattr(ctx.repl, 'renderer') and hasattr(ctx.repl.renderer, 'theme'):
        ctx.repl.renderer.theme = manager.get_theme(theme_name)
    
    ctx.console.print(f"[green]Theme set to '{theme_name}'[/]")
    
    # Save to settings if available
    if hasattr(ctx, 'settings') and ctx.settings:
        ctx.settings.ui.theme = theme_name
        # Save settings to disk
        try:
            from henchman.config.settings import save_settings
            save_settings(ctx.settings)
            ctx.console.print("[dim]Theme saved to settings.[/]")
        except Exception as e:
            ctx.console.print(f"[yellow]Warning: Could not save settings: {e}[/]")
```

## Testing Strategy

### Unit Tests
1. **New theme tests**: Verify all 8 themes exist and have correct properties
2. **ThemeCommand tests**: Test all command subcommands
3. **Settings integration**: Test theme loading from settings
4. **Fallback mechanism**: Test invalid theme name handling

### Integration Tests
1. **End-to-end theme switching**: `/theme set` changes appearance
2. **Settings persistence**: Theme persists across sessions
3. **Command registration**: `/theme` appears in help

### Test Files to Create/Update
1. `tests/cli/test_console.py` - Update for new themes
2. `tests/cli/test_theme_command.py` - New file for theme command tests
3. `tests/cli/test_app.py` - Add theme loading tests
4. `tests/cli/test_repl.py` - Add renderer theme tests

## Dependencies

### Runtime Dependencies
- **Rich**: Already used for console output
- **Prompt Toolkit**: Already used for input
- **Pydantic**: Already used for settings

### Development Dependencies
- **pytest**: Already used for testing
- **pytest-asyncio**: Already used for async tests

## Backward Compatibility

### Guarantees
1. Default theme remains "dark"
2. Existing API unchanged
3. Settings schema backward compatible (theme field already exists)
4. No breaking changes to command system

### Migration Path
1. Users with existing settings get "dark" theme by default
2. New themes are additive, not replacing existing ones
3. Invalid theme names fall back to default with warning

## Success Criteria

### Functional
1. All 8 themes available and usable
2. `/theme` command fully functional
3. Theme loaded from settings at startup
4. Theme changes persist across sessions
5. Invalid theme name handled gracefully

### Technical
1. 100% test coverage maintained
2. No performance regression
3. Code follows project conventions
4. All CI checks pass

### User Experience
1. Users can easily discover available themes
2. Theme switching is immediate and visible
3. Theme preview helps with selection
4. Theme persists automatically

## Risk Assessment

### Low Risk
- Adding new theme definitions
- Creating new command
- Reading theme from settings

### Medium Risk  
- Theme persistence (file I/O)
- Invalid theme name handling
- Settings file permissions

### Mitigations
- Thorough testing of all edge cases
- Graceful fallbacks for errors
- Clear error messages for users

## Implementation Order

1. **Day 1**: Task 1.1 (Add new themes)
2. **Day 2**: Task 1.2 (Create theme command)
3. **Day 3**: Task 1.3 (Apply theme from settings)
4. **Day 4**: Task 1.4 (Theme persistence)
5. **Day 5**: Testing and bug fixes

## Delegation Recommendation

**Primary Specialist**: Engineer
**Reasoning**: Implementation-focused task requiring code changes to existing components
**Secondary Support**: None needed for Phase 1
**Tech Lead Oversight**: Architecture review and code quality assurance

## Documentation Updates

### Required Documentation Updates
1. Update README.md with new theme features
2. Add theme command to help documentation
3. Update settings documentation with theme field
4. Create examples in documentation

### Documentation Files
1. `README.md` - Add theme system overview
2. `docs/commands.md` - Add theme command documentation
3. `docs/settings.md` - Update theme settings documentation
4. `examples/theme-usage.md` - Create usage examples

## Next Steps After Phase 1

1. **Phase 2**: Status bar enhancements (provider/model info, token percentage)
2. **Phase 3**: REPL refactoring (smaller components, better organization)
3. **Phase 4**: Interactive components (tab completion, form-based input)
4. **Phase 5**: Output visualization (tables, trees, diff views)

## Quality Metrics

1. **Test Coverage**: 100% maintained
2. **Code Quality**: Passes ruff and mypy
3. **Performance**: No noticeable impact
4. **User Feedback**: Positive response to theme variety
5. **Accessibility**: High-contrast themes provide better accessibility

## Exit Criteria

Phase 1 is complete when:
1. All 8 themes are available and working
2. `/theme` command is fully functional
3. Theme loads from settings at startup
4. Theme changes persist across sessions
5. All tests pass with 100% coverage
6. Documentation is updated