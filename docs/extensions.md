# Extensions

Henchman-AI supports extensions for adding custom functionality.

## Extension Types

| Type | Description |
|------|-------------|
| **Providers** | Custom LLM providers |
| **Tools** | Custom tools for the agent |
| **Commands** | Custom slash commands |

## Installing Extensions

### From PyPI

```bash
pip install henchman-my-extension
```

### Entry Points

Extensions register via Python entry points in `pyproject.toml`:

```toml
[project.entry-points."henchman.extensions"]
my_extension = "my_package.extension:MyExtension"
```

### Local Extensions

Place extension files in `~/.henchman/extensions/`:

```python
# ~/.henchman/extensions/my_extension.py
from henchman.extensions import Extension

class MyExtension(Extension):
    name = "my_extension"
    version = "1.0.0"
    
    def activate(self, context):
        # Register tools, commands, etc.
        pass
```

## Creating Extensions

### Extension Base Class

```python
from henchman.extensions import Extension

class MyExtension(Extension):
    """My custom extension."""
    
    name = "my_extension"
    version = "1.0.0"
    description = "Does something useful"
    
    def activate(self, context):
        """Called when extension is loaded."""
        # Register your tools, commands, providers
        context.register_tool(MyTool())
        context.register_command(MyCommand())
    
    def deactivate(self):
        """Called when extension is unloaded."""
        pass
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
    def parameters(self) -> dict:
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
    
    async def execute(self, **params) -> ToolResult:
        query = params["query"]
        result = await process_query(query)
        return ToolResult(content=result)

# In extension activate:
def activate(self, context):
    context.register_tool(MyTool())
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
    
    async def execute(self, context: CommandContext) -> None:
        context.console.print("Hello from my command!")

# In extension activate:
def activate(self, context):
    context.register_command(MyCommand())
```

### Adding Custom Providers

```python
from henchman.providers import ModelProvider, Message, StreamChunk

class MyProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "my_provider"
    
    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list | None = None,
        **kwargs
    ):
        # Your implementation
        response = await call_my_api(messages)
        yield StreamChunk(content=response)

# In extension activate:
def activate(self, context):
    context.register_provider("my_provider", MyProvider)
```

## Managing Extensions

### List Extensions

```
/extensions list
```

Shows installed and active extensions.

### Enable/Disable

```
/extensions enable my_extension
/extensions disable my_extension
```

## Extension Context

The context object provides access to:

| Method | Description |
|--------|-------------|
| `register_tool(tool)` | Register a custom tool |
| `register_command(cmd)` | Register a slash command |
| `register_provider(name, cls)` | Register a provider |
| `get_settings()` | Access configuration |
| `get_console()` | Access Rich console |

## Packaging Extensions

### pyproject.toml

```toml
[project]
name = "henchman-my-extension"
version = "1.0.0"
dependencies = ["henchman-ai>=0.1.0"]

[project.entry-points."henchman.extensions"]
my_extension = "my_package:MyExtension"
```

### Publishing

```bash
pip install build twine
python -m build
twine upload dist/*
```
