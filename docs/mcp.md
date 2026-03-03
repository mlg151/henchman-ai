# MCP Integration

Henchman-AI supports the Model Context Protocol (MCP) for connecting to external tool servers.

## What is MCP?

MCP (Model Context Protocol) is a standard for connecting AI assistants to external tools and data sources. MCP servers provide tools that can be discovered and invoked by the AI agent.

## Configuration

Configure MCP servers in your settings file:

```yaml
mcp_servers:
  # File system access
  filesystem:
    command: npx
    args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
    trusted: false
  
  # GitHub integration
  github:
    command: uvx
    args: ["mcp-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    trusted: true
  
  # Serena - Semantic code retrieval and editing (RECOMMENDED)
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
    env:
      # Optional: Set workspace directory (defaults to current directory)
      SERENA_WORKSPACE: "${PROJECT_ROOT}"
      # Optional: Enable JetBrains plugin backend if available
      SERENA_USE_JETBRAINS: "false"
    trusted: true
    # Note: Serena requires uv to be installed: https://docs.astral.sh/uv/
  
  # Optional: Add more MCP servers as needed
  # postgres:
  #   command: npx
  #   args: ["@modelcontextprotocol/server-postgres", "postgresql://user:pass@localhost/db"]
  #   trusted: false
```

## Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `command` | string | Command to run the server |
| `args` | list | Command arguments |
| `env` | dict | Environment variables |
| `trusted` | bool | If true, skip tool confirmation |

## Trust Levels

### Trusted Servers

```yaml
mcp_servers:
  my_server:
    trusted: true
```

- Tools execute without confirmation
- Use for servers you control
- Exercise caution with untrusted code

### Untrusted Servers (Default)

```yaml
mcp_servers:
  my_server:
    trusted: false  # or omit
```

- All tool calls require confirmation
- Safe for third-party servers
- Default behavior

## Commands

### List Servers

```
/mcp list
```

Shows configured servers and their connection status.

### Server Status

```
/mcp status
```

Shows detailed status including available tools.

### Logging Control

```
/mcp logging on     # Enable MCP logging messages
/mcp logging off    # Disable MCP logging messages  
/mcp logging status # Show current logging status
```

Controls visibility of MCP server log messages.

## Available MCP Servers

### Official Anthropic Servers

| Server | Description |
|--------|-------------|
| `@anthropic-ai/mcp-filesystem-server` | File system access |
| `@anthropic-ai/mcp-memory-server` | Persistent memory |

### Community Servers

| Server | Description |
|--------|-------------|
| `mcp-github` | GitHub API integration |
| `mcp-slack` | Slack workspace access |
| `mcp-postgres` | PostgreSQL database |

### Serena - Semantic Code Analysis (RECOMMENDED)

**Serena** is a powerful coding agent toolkit that provides semantic code retrieval and editing capabilities via MCP. It enhances coding agents with IDE-like tools for efficient code navigation and manipulation.

#### Key Features of Serena:
- **Semantic Code Retrieval**: Find symbols, functions, classes by name with context
- **Precise Code Editing**: Insert, replace, or delete code at symbol level
- **Cross-Reference Analysis**: Find referencing symbols and dependencies
- **Multi-Language Support**: 30+ programming languages via LSP backends
- **JetBrains Integration**: Optional plugin for enhanced analysis capabilities

#### Setting Up Serena:
1. **Install uv** (required for Serena):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Configure in settings.yaml** (as shown above)

3. **Start Henchman-AI** - Serena will auto-connect if configured

4. **Verify connection**:
   ```bash
   henchman
   /mcp status  # Check if Serena is connected
   /tools       # List available tools including Serena's
   ```

#### When to Use Serena:
- **Large codebases**: Efficient navigation without reading entire files
- **Refactoring tasks**: Precise symbol-level edits
- **Code understanding**: Cross-reference analysis and dependencies
- **Complex implementations**: Semantic search for relevant code patterns

#### Performance Benefits:
- **Reduces token usage**: Semantic retrieval vs. reading entire files
- **Improves accuracy**: Symbol-level precision over string matching
- **Enhances productivity**: IDE-like capabilities in the CLI
- **Scales with codebase**: Efficient even in large, complex projects

## Programmatic Usage

### Single Server

```python
from henchman.mcp import McpServerConfig, McpClient

# Configure MCP servers (filesystem, github, serena, etc.)
filesystem_config = McpServerConfig(
    command="npx",
    args=["@anthropic-ai/mcp-filesystem-server", "/home/user"],
    trusted=False,  # Untrusted servers require tool confirmation
)

github_config = McpServerConfig(
    command="uvx",
    args=["mcp-github"],
    env={"GITHUB_TOKEN": "your-token-here"},
    trusted=True,
)

# RECOMMENDED: Serena for semantic code analysis
serena_config = McpServerConfig(
    command="uvx",
    args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
    trusted=True,  # Serena tools are safe for auto-approval
)

# Connect to a single server
client = McpClient(name="serena", config=serena_config)
await client.connect()
tools = await client.discover_tools()

# Use Serena's semantic tools
result = await client.call_tool("find_symbol", {
    "name": "authenticate_user",
    "kind": "function"
})

await client.disconnect()
```

### Multiple Servers

```python
from henchman.mcp import McpManager, McpServerConfig

# Or manage multiple servers
configs = {
    "filesystem": filesystem_config,
    "github": github_config,
    "serena": serena_config,  # Highly recommended for coding tasks
}
manager = McpManager(configs)
await manager.connect_all()
all_tools = manager.get_all_tools()  # List[McpTool]
await manager.disconnect_all()
```

### Serena Tool Examples

```python
# Example Serena tool usage
result = await client.call_tool("find_symbol", {
    "name": "authenticate_user",
    "kind": "function"
})

result = await client.call_tool("find_referencing_symbols", {
    "symbol_id": "function:authenticate_user:42"
})

result = await client.call_tool("insert_after_symbol", {
    "symbol_id": "function:authenticate_user:42",
    "content": "    # Added logging\n    logger.info(f\"User authenticated: {username}\")"
})
```

### Example Workflow with Serena:

```python
# Without Serena: Read entire files, grep for patterns
files = await glob("**/*.py")
for file in files:
    content = await read_file(file)  # Inefficient for large codebases
    if "authenticate" in content:
        # Manual analysis needed

# With Serena: Semantic search
symbols = await serena_client.call_tool("find_symbol", {
    "name": "authenticate",
    "kind": ["function", "method"]
})
# Returns precise locations and contexts
```

## Creating MCP Servers

MCP servers can be written in any language. Here's a Python example:

```python
from mcp.server import Server
from mcp.types import Tool

server = Server("my-server")

@server.tool()
async def my_tool(input: str) -> str:
    """Process the input."""
    return f"Processed: {input}"

if __name__ == "__main__":
    server.run()
```

See the [MCP specification](https://modelcontextprotocol.io/) for full details.
