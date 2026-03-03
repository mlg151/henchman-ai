# Extensions

Henchman-AI supports extensions for adding custom functionality. Extensions allow third parties to add tools, commands, and additional context to the system.

## Extension Types

Extensions can provide:

| Type | Description |
|------|-------------|
| **Tools** | Custom tools for the agent to use |
| **Commands** | Custom slash commands for the CLI |
| **Context** | Additional system prompt context |

**Note**: Custom provider extensions are not currently supported. Use the built-in provider system instead.

## Creating Extensions

### Extension Base Class

Create an extension by subclassing `Extension` and implementing the required properties:

```python
from henchman.extensions import Extension
from henchman.tools import Tool, ToolKind, ToolResult
from henchman.cli.commands import Command, CommandContext

class MyExtension(Extension):
    """My custom extension."""
    
    @property
    def name(self) -> str:
        return "my_extension"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Adds custom tools and commands"
    
    def get_tools(self) -> list[Tool]:
        """Return tools provided by this extension."""
        return [MyCustomTool()]
    
    def get_commands(self) -> list[Command]:
        """Return slash commands provided by this extension."""
        return [MyCustomCommand()]
    
    def get_context(self) -> str:
        """Return additional system prompt context."""
        return "Additional context for the system prompt"
```

## Installing and Loading Extensions

### Package Installation (Entry Points)

Extensions can be distributed as Python packages and discovered automatically via entry points:

1. **Install the package**:
   ```bash
   pip install henchman-my-extension
   ```

2. **Package configuration** (`pyproject.toml`):
   ```toml
   [project.entry-points."henchman.extensions"]
   my_extension = "my_package.extension:MyExtension"
   ```

The extension will be automatically discovered and loaded when Henchman-AI starts.

### Local Development

For local development, place extensions in `~/.henchman/extensions/` directory structure:

```
~/.henchman/extensions/
└── my_extension/
    └── extension.py
```

The `extension.py` file should contain your `Extension` subclass:

```python
# ~/.henchman/extensions/my_extension/extension.py
from henchman.extensions import Extension
from henchman.tools import Tool
from henchman.cli.commands import Command

class MyExtension(Extension):
    @property
    def name(self) -> str:
        return "my_extension"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "My custom extension"
    
    def get_tools(self) -> list[Tool]:
        # Return your tools
        return []
    
    def get_commands(self) -> list[Command]:
        # Return your commands  
        return []
    
    def get_context(self) -> str:
        # Return additional context
        return ""
```

### Adding Custom Tools

```python
from henchman.tools import Tool, ToolKind, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "My custom tool"
    
    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to process"
                }
            },
            "required": ["query"]
        }
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ
    
    async def execute(self, **params: object) -> ToolResult:
        query = str(params["query"])
        # Process the query
        result = f"Processed: {query}"
        return ToolResult(content=result)

# In your extension's get_tools() method:
def get_tools(self) -> list[Tool]:
    return [MyTool()]
```

### Adding Custom Commands

```python
from henchman.cli.commands import Command, CommandContext

class MyCommand(Command):
    @property
    def name(self) -> str:
        return "mycommand"
    
    @property
    def description(self) -> str:
        return "Do something custom"
    
    @property
    def usage(self) -> str:
        return "/mycommand [args]"
    
    async def execute(self, ctx: CommandContext) -> None:
        ctx.console.print("Hello from my command!")

# In your extension's get_commands() method:
def get_commands(self) -> list[Command]:
    return [MyCommand()]
```

### Adding Context

Extensions can also provide additional context that gets added to the system prompt:

```python
def get_context(self) -> str:
    """Return additional system prompt context."""
    return """
    # My Extension Context
    
    This extension provides additional capabilities:
    - Custom tool: my_tool for processing queries
    - Custom command: /mycommand for custom operations
    
    Use these when appropriate for the task.
    """
```

## Managing Extensions

### List Extensions

Use the `/extensions` command to list all loaded extensions:

```
/extensions
```

Example output:
```
Loaded Extensions (2):
  • greeting_extension v1.0.0 - Adds greeting tools and commands
  • another_extension v2.0.0 - Another useful extension
```

This shows:
- Extension name (in cyan)
- Version
- Description

**Note**: The extensions system automatically discovers and loads extensions. There are currently no enable/disable commands - all discovered extensions are loaded automatically when Henchman-AI starts.

### Automatic Discovery

Henchman-AI automatically discovers extensions in two ways:

1. **Entry Points**: When installed via pip, extensions are discovered through Python entry points in the `henchman.extensions` group.

2. **Local Directory**: Extensions placed in `~/.henchman/extensions/` are discovered automatically.

The discovery happens automatically when Henchman-AI starts. You don't need to manually register extensions unless you're developing or testing them programmatically.

## Extension Manager API

The `ExtensionManager` class provides the following methods:

| Method | Description |
|--------|-------------|
| `register(extension)` | Register an extension instance |
| `unregister(name)` | Unregister an extension by name |
| `get(name)` | Get an extension by name |
| `list_extensions()` | List all registered extension names |
| `get_all_tools()` | Get all tools from all extensions |
| `get_all_commands()` | Get all commands from all extensions |
| `get_combined_context()` | Get combined context from all extensions |
| `discover_entry_points()` | Discover extensions from entry points |
| `discover_directory(path)` | Discover extensions from a directory |

## Packaging and Distribution

### Package Structure

A typical extension package structure:

```
my_extension/
├── pyproject.toml
├── README.md
└── src/
    └── my_package/
        ├── __init__.py
        ├── extension.py    # Contains MyExtension class
        └── tools.py        # Optional: Custom tools
```

### pyproject.toml Configuration

```toml
[project]
name = "henchman-my-extension"
version = "1.0.0"
description = "My custom extension for Henchman-AI"
authors = [{name = "Your Name", email = "your.email@example.com"}]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.8"
dependencies = [
    "henchman-ai>=0.1.0",
    # Add your extension's dependencies here
]

[project.entry-points."henchman.extensions"]
my_extension = "my_package.extension:MyExtension"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Building and Publishing

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Upload to PyPI
twine upload dist/*
```

## Complete Example

Here's a complete example of a simple extension:

```python
# my_package/extension.py
from henchman.extensions import Extension
from henchman.tools import Tool, ToolKind, ToolResult
from henchman.cli.commands import Command, CommandContext

class GreetTool(Tool):
    @property
    def name(self) -> str:
        return "greet"
    
    @property
    def description(self) -> str:
        return "Greet someone by name"
    
    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet"
                }
            },
            "required": ["name"]
        }
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ
    
    async def execute(self, **params: object) -> ToolResult:
        name = str(params["name"])
        return ToolResult(content=f"Hello, {name}!")

class GreetCommand(Command):
    @property
    def name(self) -> str:
        return "greet"
    
    @property
    def description(self) -> str:
        return "Greet from command"
    
    @property
    def usage(self) -> str:
        return "/greet <name>"
    
    async def execute(self, ctx: CommandContext) -> None:
        args = ctx.args
        if args:
            ctx.console.print(f"Hello, {args[0]}!")
        else:
            ctx.console.print("Hello, world!")

class MyExtension(Extension):
    @property
    def name(self) -> str:
        return "greeting_extension"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Adds greeting tools and commands"
    
    def get_tools(self) -> list[Tool]:
        return [GreetTool()]
    
    def get_commands(self) -> list[Command]:
        return [GreetCommand()]
    
    def get_context(self) -> str:
        return "This extension provides greeting functionality."
```
