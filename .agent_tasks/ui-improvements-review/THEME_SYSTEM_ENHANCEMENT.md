# Theme System Enhancement - Implementation Details

## Current State Analysis

### Existing Theme System
```python
# src/henchman/cli/console.py
class Theme:
    name: str = "dark"
    primary: str = "blue"
    secondary: str = "cyan"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    muted: str = "dim"

# Only 2 themes defined
DARK_THEME = Theme(name="dark")
LIGHT_THEME = Theme(name="light", primary="blue", secondary="dark_cyan", ...)

class ThemeManager:
    def __init__(self):
        self._themes: dict[str, Theme] = {
            "dark": DARK_THEME,
            "light": LIGHT_THEME,
        }
```

### Issues Identified
1. Only 2 built-in themes (dark, light)
2. No way to change themes interactively
3. Theme not persisted across sessions
4. Limited color customization
5. No theme preview capability

## Implementation Plan

### Step 1: Add More Built-in Themes

**File**: `src/henchman/cli/console.py`
**Changes**: Add new theme definitions

```python
# Add after LIGHT_THEME definition
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
```

**Update ThemeManager initialization**:
```python
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

### Step 2: Create Theme Command

**File**: `src/henchman/cli/commands/theme.py`
**New file**: Create theme management command

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
        """Command name.

        Returns:
            Command name string.
        """
        return "theme"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Manage UI themes (list, set, preview)"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/theme [list|set <name>|preview <name>|create <name>]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the theme command.

        Args:
            ctx: Command context.
        """
        args = ctx.args
        
        if not args:
            await self._show_help(ctx)
            return
        
        subcommand = args[0].lower()
        
        if subcommand == "list":
            await self._list_themes(ctx)
        elif subcommand == "set" and len(args) > 1:
            await self._set_theme(ctx, args[1])
        elif subcommand == "preview" and len(args) > 1:
            await self._preview_theme(ctx, args[1])
        elif subcommand == "create" and len(args) > 1:
            await self._create_theme(ctx, args[1])
        else:
            await self._show_help(ctx)

    async def _show_help(self, ctx: CommandContext) -> None:
        """Show help for theme command."""
        ctx.console.print("\n[bold blue]Theme Command[/]\n")
        ctx.console.print("  /theme list              - List available themes")
        ctx.console.print("  /theme set <name>        - Set active theme")
        ctx.console.print("  /theme preview <name>    - Preview a theme")
        ctx.console.print("  /theme create <name>     - Create custom theme")
        ctx.console.print("")

    async def _list_themes(self, ctx: CommandContext) -> None:
        """List available themes."""
        from henchman.cli.console import ThemeManager
        
        manager = ThemeManager()
        themes = manager.list_themes()
        current = manager.current.name
        
        ctx.console.print("\n[bold blue]Available Themes[/]\n")
        
        for theme_name in sorted(themes):
            if theme_name == current:
                ctx.console.print(f"  [green]• {theme_name}[/] (current)")
            else:
                ctx.console.print(f"  • {theme_name}")
        
        ctx.console.print("")

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
        if hasattr(ctx, 'settings'):
            ctx.settings.ui.theme = theme_name
            # TODO: Save settings to disk

    async def _preview_theme(self, ctx: CommandContext, theme_name: str) -> None:
        """Preview a theme with sample output."""
        from henchman.cli.console import ThemeManager, OutputRenderer
        
        manager = ThemeManager()
        
        if theme_name not in manager.list_themes():
            ctx.console.print(f"[red]Error: Theme '{theme_name}' not found[/]")
            return
        
        theme = manager.get_theme(theme_name)
        renderer = OutputRenderer(console=ctx.console, theme=theme)
        
        ctx.console.print(f"\n[bold]Preview of '{theme_name}' theme:[/]\n")
        
        renderer.success("This is a success message")
        renderer.info("This is an info message")
        renderer.warning("This is a warning message")
        renderer.error("This is an error message")
        renderer.heading("This is a heading")
        renderer.muted("This is muted text")
        
        ctx.console.print("")

    async def _create_theme(self, ctx: CommandContext, theme_name: str) -> None:
        """Create a custom theme interactively."""
        # TODO: Implement interactive theme creation
        ctx.console.print("[yellow]Theme creation not yet implemented[/]")
        ctx.console.print("Use '/theme set' to use existing themes.")
```

### Step 3: Register Theme Command

**File**: `src/henchman/cli/commands/builtins.py`
**Changes**: Add ThemeCommand to builtin commands

```python
# Add import at top
from henchman.cli.commands.theme import ThemeCommand

# Update get_builtin_commands function
def get_builtin_commands() -> list[Command]:
    """Get all built-in commands.
    
    Returns:
        List of Command instances.
    """
    return [
        HelpCommand(),
        QuitCommand(),
        ClearCommand(),
        ToolsCommand(),
        ThemeCommand(),  # Add this line
        AgentCommand(),
        TeamCommand(),
        PlanCommand(),
        RagCommand(),
        ChatCommand(),
        McpCommand(),
        ModelCommand(),
        UnlimitedCommand(),
    ]
```

### Step 4: Apply Theme from Settings

**File**: `src/henchman/cli/app.py`
**Changes**: Apply theme from settings when creating REPL

```python
# In _run_interactive function, after creating settings:
settings = load_settings()

# Create theme-aware renderer
from henchman.cli.console import ThemeManager, OutputRenderer
theme_manager = ThemeManager()
theme_manager.set_theme(settings.ui.theme)
theme = theme_manager.current

# Create renderer with theme
renderer = OutputRenderer(console=console, theme=theme)

# Pass renderer to REPL (need to update REPL constructor)
config = ReplConfig(system_prompt=system_prompt, auto_approve_tools=yes)
repl = Repl(
    provider=provider,
    console=console,
    config=config,
    settings=settings,
    environment_context=env_block,
    renderer=renderer,  # Pass custom renderer
)
```

**File**: `src/henchman/cli/repl.py`
**Changes**: Update REPL to accept custom renderer

```python
class Repl:
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

### Step 5: Update Tests

**File**: `tests/cli/test_console.py`
**Changes**: Add tests for new themes

```python
def test_theme_manager_has_new_themes(self) -> None:
    """Test that ThemeManager includes new themes."""
    manager = ThemeManager()
    themes = manager.list_themes()
    
    assert "dark" in themes
    assert "light" in themes
    assert "solarized-dark" in themes
    assert "solarized-light" in themes
    assert "monokai" in themes
    assert "dracula" in themes
    assert "high-contrast-dark" in themes
    assert "high-contrast-light" in themes

def test_get_new_themes(self) -> None:
    """Test getting new theme instances."""
    manager = ThemeManager()
    
    solarized_dark = manager.get_theme("solarized-dark")
    assert solarized_dark.name == "solarized-dark"
    assert solarized_dark.primary == "cyan"
    
    dracula = manager.get_theme("dracula")
    assert dracula.name == "dracula"
    assert dracula.primary == "purple"
```

**New File**: `tests/cli/test_theme_command.py`
**Create tests for theme command**

```python
"""Tests for theme command."""

from unittest.mock import AsyncMock, Mock

import pytest

from henchman.cli.commands.theme import ThemeCommand


class TestThemeCommand:
    """Tests for ThemeCommand class."""
    
    @pytest.fixture
    def command(self) -> ThemeCommand:
        """Create a ThemeCommand instance."""
        return ThemeCommand()
    
    @pytest.fixture
    def mock_context(self) -> Mock:
        """Create a mock command context."""
        context = Mock()
        context.args = []
        context.console = Mock()
        context.repl = Mock()
        context.settings = Mock()
        return context
    
    def test_command_name(self, command: ThemeCommand) -> None:
        """Test command name property."""
        assert command.name == "theme"
    
    def test_command_description(self, command: ThemeCommand) -> None:
        """Test command description property."""
        assert "theme" in command.description.lower()
    
    async def test_execute_no_args_shows_help(self, command: ThemeCommand, mock_context: Mock) -> None:
        """Test executing with no arguments shows help."""
        await command.execute(mock_context)
        mock_context.console.print.assert_called()
    
    async def test_execute_list_themes(self, command: ThemeCommand, mock_context: Mock) -> None:
        """Test listing themes."""
        mock_context.args = ["list"]
        await command.execute(mock_context)
        mock_context.console.print.assert_called()
```

## Implementation Order

1. **Day 1**: Add new theme definitions to console.py
2. **Day 2**: Create theme command (theme.py)
3. **Day 3**: Register theme command in builtins.py
4. **Day 4**: Update REPL to use theme from settings
5. **Day 5**: Write tests for new functionality
6. **Day 6**: Test and debug
7. **Day 7**: Documentation and polish

## Testing Checklist

- [ ] New themes appear in theme list
- [ ] Theme command shows help correctly
- [ ] Theme switching works interactively
- [ ] Theme preview shows sample output
- [ ] Settings are loaded and applied
- [ ] All existing tests still pass
- [ ] No performance regression

## Documentation Updates Needed

1. Update README.md with new theme features
2. Add theme command to help text
3. Create examples in documentation
4. Update settings documentation

## Potential Issues & Solutions

1. **Issue**: Theme not applying to existing renderer instances
   **Solution**: Update renderer theme property when changing theme

2. **Issue**: Settings file doesn't exist
   **Solution**: Create default settings if not present

3. **Issue**: Invalid theme name in settings
   **Solution**: Fall back to default theme with warning

4. **Issue**: Theme changes not persisting
   **Solution**: Save settings after theme change

## Success Metrics

1. Users can list all available themes
2. Users can switch themes interactively
3. Theme changes persist across sessions
4. No breaking changes to existing functionality
5. 100% test coverage maintained