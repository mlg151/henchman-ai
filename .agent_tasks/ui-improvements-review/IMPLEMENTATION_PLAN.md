# UI Improvements Implementation Plan

## Phase 1: Theme System Enhancement (Week 1)

### 1.1 Add More Built-in Themes
**Current Issue**: Only dark and light themes available
**Solution**: Add popular terminal themes
```python
# New themes to add
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
```

### 1.2 Theme Configuration Command
**Current Issue**: No way to change themes interactively
**Solution**: Add `/theme` command
```python
class ThemeCommand(Command):
    """Manage UI themes."""
    
    @property
    def name(self) -> str:
        return "theme"
    
    @property
    def description(self) -> str:
        return "Manage UI themes (list, set, preview)"
    
    async def execute(self, ctx: CommandContext) -> None:
        # /theme list - Show available themes
        # /theme set <name> - Change theme
        # /theme preview <name> - Preview theme
        # /theme create <name> - Create custom theme
        pass
```

### 1.3 Theme Persistence
**Current Issue**: Theme not saved across sessions
**Solution**: Store in settings.yaml
```yaml
ui:
  theme: "dracula"
  show_line_numbers: true
```

## Phase 2: Enhanced Status Bar (Week 2)

### 2.1 Improved Status Information
**Current Issue**: Limited status information
**Solution**: Add more metrics and real-time updates
```python
def _get_toolbar_status(self) -> list[tuple[str, str]]:
    """Get enhanced status bar content."""
    status = []
    
    # Plan Mode
    session = self.session_manager.current
    plan_mode = session.plan_mode if session else False
    if plan_mode:
        status.append(("bg:yellow fg:black bold", " PLAN "))
    else:
        status.append(("bg:blue fg:white bold", " CHAT "))
    
    # Provider/Model
    provider_name = self.provider.__class__.__name__.replace("Provider", "")
    model_name = getattr(self.provider, "model", "default")
    status.append(("", f" {provider_name}:{model_name} "))
    
    # Tokens with percentage
    try:
        msgs = self.agent.get_messages_for_api()
        tokens = TokenCounter.count_messages(msgs)
        max_tokens = self.settings.context.max_tokens if self.settings else 128000
        percent = (tokens / max_tokens) * 100
        color = "green" if percent < 50 else "yellow" if percent < 75 else "red"
        status.append((f"fg:{color}", f" Tokens: {tokens}/{max_tokens} ({percent:.0f}%) "))
    except Exception:
        pass
    
    # Active Tools
    active_tools = len(self.tool_registry.list_tools())
    status.append(("", f" Tools: {active_tools} "))
    
    # MCP Connections
    if hasattr(self, 'mcp_manager') and self.mcp_manager:
        connected = sum(1 for client in self.mcp_manager.clients.values() if client.connected)
        total = len(self.mcp_manager.clients)
        if total > 0:
            status.append(("", f" MCP: {connected}/{total} "))
    
    return status
```

### 2.2 Progress Indicators
**Current Issue**: No progress feedback for long operations
**Solution**: Add progress bars for file operations, indexing, etc.
```python
class ProgressManager:
    """Manage progress indicators for long operations."""
    
    def __init__(self, console: Console):
        self.console = console
        self.tasks: dict[str, Progress] = {}
    
    def start_task(self, task_id: str, description: str, total: int = 100):
        """Start a new progress task."""
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console
        )
        task = progress.add_task(description, total=total)
        self.tasks[task_id] = (progress, task)
        return progress
    
    def update_task(self, task_id: str, advance: int = 1):
        """Update progress for a task."""
        if task_id in self.tasks:
            progress, task = self.tasks[task_id]
            progress.update(task, advance=advance)
    
    def complete_task(self, task_id: str):
        """Complete and remove a task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
```

## Phase 3: Interactive Components (Week 3)

### 3.1 Form-based Input
**Current Issue**: Complex tool parameters require manual JSON
**Solution**: Interactive forms for tool parameters
```python
class ToolForm:
    """Interactive form for tool parameter input."""
    
    def __init__(self, tool: Tool, console: Console):
        self.tool = tool
        self.console = console
        self.parameters = self._parse_parameters(tool.parameters)
    
    async def prompt(self) -> dict[str, object]:
        """Prompt user for tool parameters."""
        results = {}
        
        for param_name, param_schema in self.parameters.items():
            param_type = param_schema.get("type", "string")
            description = param_schema.get("description", "")
            required = param_name in param_schema.get("required", [])
            
            # Use appropriate prompt based on type
            if param_type == "boolean":
                from rich.prompt import Confirm
                value = await anyio.to_thread.run_sync(
                    lambda: Confirm.ask(f"{param_name}? {description}", console=self.console)
                )
            elif param_type == "integer":
                from rich.prompt import IntPrompt
                value = await anyio.to_thread.run_sync(
                    lambda: IntPrompt.ask(f"{param_name}: {description}", console=self.console)
                )
            else:  # string
                from rich.prompt import Prompt
                value = await anyio.to_thread.run_sync(
                    lambda: Prompt.ask(f"{param_name}: {description}", console=self.console)
                )
            
            results[param_name] = value
        
        return results
```

### 3.2 Tab Completion
**Current Issue**: No command/tool name completion
**Solution**: Add tab completion for commands and tool names
```python
def create_session_with_completion(history_file: Path, bottom_toolbar: Callable[[], list[tuple[str, str]]]) -> PromptSession:
    """Create prompt session with tab completion."""
    
    # Build completion list from commands and tools
    completions = [
        "/help", "/quit", "/clear", "/tools", "/theme", "/model",
        "/chat", "/mcp", "/rag", "/plan", "/agent", "/team"
    ]
    
    # Add tool names (would need access to tool registry)
    # tool_completions = [f"!{tool}" for tool in tool_registry.list_tools()]
    # completions.extend(tool_completions)
    
    word_completer = WordCompleter(completions, ignore_case=True)
    
    return PromptSession(
        history=FileHistory(str(history_file)),
        completer=word_completer,
        complete_while_typing=True,
        bottom_toolbar=bottom_toolbar,
        key_bindings=create_key_bindings(),
    )
```

## Phase 4: Output Visualization (Week 4)

### 4.1 Enhanced Table Views
**Current Issue**: Limited table formatting
**Solution**: Rich table rendering for structured data
```python
class TableRenderer:
    """Render structured data as tables."""
    
    def __init__(self, console: Console, theme: Theme):
        self.console = console
        self.theme = theme
    
    def render_table(self, data: list[dict], title: str | None = None) -> None:
        """Render data as a table."""
        if not data:
            self.console.print("[dim]No data to display[/]")
            return
        
        # Create table
        table = Table(title=title, show_header=True, header_style=f"bold {self.theme.primary}")
        
        # Add columns from first row keys
        for key in data[0].keys():
            table.add_column(str(key))
        
        # Add rows
        for row in data:
            table.add_row(*[str(value) for value in row.values()])
        
        self.console.print(table)
    
    def render_tree(self, root_name: str, items: list[tuple[str, str]]) -> None:
        """Render hierarchical data as a tree."""
        tree = Tree(f"[bold {self.theme.primary}]{root_name}[/]")
        
        for path, value in items:
            current = tree
            parts = path.split("/")
            
            for i, part in enumerate(parts[:-1]):
                # Find or create branch
                found = False
                for child in current.children:
                    if child.label == part:
                        current = child
                        found = True
                        break
                
                if not found:
                    current = current.add(f"[{self.theme.secondary}]{part}[/]")
            
            # Add leaf with value
            current.add(f"{parts[-1]}: [bold]{value}[/]")
        
        self.console.print(tree)
```

### 4.2 Diff Visualization
**Current Issue**: No visual diff for file comparisons
**Solution**: Add diff viewer for file changes
```python
class DiffRenderer:
    """Render file differences."""
    
    def render_diff(self, old_content: str, new_content: str, filename: str) -> None:
        """Render diff between old and new content."""
        from rich.syntax import Syntax
        import difflib
        
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        
        diff_text = "".join(diff)
        if diff_text:
            syntax = Syntax(diff_text, "diff", theme="monokai")
            self.console.print(syntax)
        else:
            self.console.print("[green]No changes[/]")
```

## Phase 5: Accessibility & Keyboard Shortcuts (Week 5)

### 5.1 Keyboard Shortcut System
**Current Issue**: Limited keyboard navigation
**Solution**: Add configurable keyboard shortcuts
```python
class ShortcutManager:
    """Manage keyboard shortcuts."""
    
    def __init__(self):
        self.shortcuts: dict[str, Callable] = {
            "ctrl+c": self._exit_app,
            "ctrl+l": self._clear_screen,
            "ctrl+r": self._reload_config,
            "ctrl+t": self._toggle_theme,
            "ctrl+p": self._toggle_plan_mode,
        }
    
    def register_shortcut(self, key: str, handler: Callable) -> None:
        """Register a new keyboard shortcut."""
        self.shortcuts[key] = handler
    
    def handle_keypress(self, key: str) -> bool:
        """Handle a keypress, return True if handled."""
        if key in self.shortcuts:
            self.shortcuts[key]()
            return True
        return False
```

### 5.2 High Contrast Themes
**Current Issue**: No accessibility themes
**Solution**: Add high contrast themes
```python
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

## Implementation Order & Dependencies

### Week 1-2: Foundation
1. Add more built-in themes
2. Implement `/theme` command
3. Add theme persistence
4. Enhance status bar

### Week 3-4: Interactive Features
5. Add progress indicators
6. Implement form-based input
7. Add tab completion
8. Create table/tree renderers

### Week 5: Polish
9. Add diff visualization
10. Implement keyboard shortcuts
11. Add accessibility themes
12. Create documentation

## Testing Strategy

### Unit Tests
- Theme system tests
- Command tests
- Renderer tests
- Form input tests

### Integration Tests
- End-to-end theme switching
- Status bar updates
- Interactive form workflows
- Keyboard shortcut handling

### Accessibility Tests
- Screen reader compatibility
- Keyboard navigation
- High contrast mode

## Success Criteria

### Functional
- All new features work as designed
- No breaking changes to existing API
- 100% test coverage maintained

### User Experience
- Themes can be changed interactively
- Status bar shows relevant information
- Complex tool parameters easier to input
- Output is more readable and structured

### Performance
- No noticeable performance degradation
- Memory usage remains stable
- Responsive UI even during long operations

## Risks & Mitigations

1. **Performance Impact**: Profile and optimize rendering
2. **Complexity Creep**: Keep features optional/configurable
3. **Breaking Changes**: Maintain backward compatibility
4. **Maintenance Burden**: Design for extensibility

## Next Steps

1. Create detailed design for each component
2. Implement Phase 1 (Theme System)
3. Gather user feedback
4. Iterate based on feedback
5. Continue with subsequent phases