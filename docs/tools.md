# Tools

Henchman-AI includes a set of built-in tools that the AI agent can use to interact with your system.

## Built-in Tools

### File Operations

#### read_file

Read the contents of a file.

```json
{
  "name": "read_file",
  "kind": "READ",
  "parameters": {
    "path": "string (required) - Path to the file"
  }
}
```

**Example:**

```
Read the file src/main.py
```

#### write_file

Write content to a file (creates or overwrites).

```json
{
  "name": "write_file",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to the file",
    "content": "string (required) - Content to write"
  }
}
```

#### edit_file

Make surgical edits to a file using search and replace.

```json
{
  "name": "edit_file",
  "kind": "WRITE",
  "parameters": {
    "path": "string (required) - Path to the file",
    "old_text": "string (required) - Text to replace",
    "new_text": "string (required) - Replacement text"
  }
}
```

### Directory Operations

#### ls

List directory contents.

```json
{
  "name": "ls",
  "kind": "READ",
  "parameters": {
    "path": "string (optional) - Directory path, defaults to current"
  }
}
```

#### glob

Find files matching a pattern.

```json
{
  "name": "glob",
  "kind": "READ",
  "parameters": {
    "pattern": "string (required) - Glob pattern (e.g., **/*.py)"
  }
}
```

#### grep

Search file contents with regular expressions.

```json
{
  "name": "grep",
  "kind": "READ",
  "parameters": {
    "pattern": "string (required) - Regex pattern",
    "path": "string (optional) - Path to search",
    "include": "string (optional) - File pattern to include"
  }
}
```

### Shell Execution

#### shell

Execute shell commands.

```json
{
  "name": "shell",
  "kind": "EXECUTE",
  "parameters": {
    "command": "string (required) - Command to execute"
  }
}
```

!!! warning "Security Note"
    Shell commands require user confirmation by default. The `HENCHMAN_CLI=1` environment variable is set during execution.

### Web Operations

#### web_fetch

Fetch content from a URL.

```json
{
  "name": "web_fetch",
  "kind": "NETWORK",
  "parameters": {
    "url": "string (required) - URL to fetch"
  }
}
```

## Tool Kinds

Tools are classified by kind, which determines confirmation behavior:

| Kind | Description | Auto-Approve |
|------|-------------|--------------|
| `READ` | Read-only operations | Yes (by default) |
| `WRITE` | File modifications | No |
| `EXECUTE` | Shell commands | No |
| `NETWORK` | Network requests | No |

## Configuration

### Auto-Approve Read Tools

```yaml
tools:
  auto_approve_read: true  # Default
```

### Auto-Approve Specific Tools

```yaml
tools:
  auto_approve:
    - read_file
    - ls
    - glob
    - grep
```

### Shell Timeout

```yaml
tools:
  shell_timeout: 60  # seconds
```

## Creating Custom Tools

Extend the `Tool` class to create custom tools:

```python
from henchman.tools import Tool, ToolKind, ToolResult

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }
    
    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ
    
    async def execute(self, **params) -> ToolResult:
        result = process(params["input"])
        return ToolResult(content=result)
```

### Registering Custom Tools

```python
from henchman.tools import ToolRegistry

registry = ToolRegistry()
registry.register(MyTool())
```

## Tool Registry

The `ToolRegistry` manages tool registration and execution:

```python
from henchman.tools import ToolRegistry

registry = ToolRegistry()

# Get tool declarations for LLM
declarations = registry.get_declarations()

# Execute a tool
result = await registry.execute("read_file", {"path": "README.md"})
```
