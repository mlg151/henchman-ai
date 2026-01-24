# MCP Integration

Henchman-AI supports the Model Context Protocol (MCP) for connecting to external tool servers.

## What is MCP?

MCP (Model Context Protocol) is a standard for connecting AI assistants to external tools and data sources. MCP servers provide tools that can be discovered and invoked by the AI agent.

## Configuration

Configure MCP servers in your settings file:

```yaml
mcp_servers:
  # Filesystem access
  filesystem:
    command: npx
    args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
    trusted: false
    
  # GitHub integration
  github:
    command: uvx
    args: ["mcp-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
    trusted: true
    
  # Custom Python server
  custom:
    command: python
    args: ["-m", "my_mcp_server"]
    env:
      MY_API_KEY: ${MY_API_KEY}
    trusted: false
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

## Programmatic Usage

### Single Server

```python
from henchman.mcp import McpServerConfig, McpClient

config = McpServerConfig(
    command="npx",
    args=["@anthropic-ai/mcp-filesystem-server", "/tmp"],
    trusted=False
)

client = McpClient(name="filesystem", config=config)
await client.connect()

# Discover available tools
tools = await client.discover_tools()

# Call a tool
result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})

await client.disconnect()
```

### Multiple Servers

```python
from henchman.mcp import McpManager, McpServerConfig

configs = {
    "filesystem": McpServerConfig(
        command="npx",
        args=["@anthropic-ai/mcp-filesystem-server", "/home/user"],
    ),
    "github": McpServerConfig(
        command="uvx",
        args=["mcp-github"],
        env={"GITHUB_TOKEN": "..."},
    ),
}

manager = McpManager(configs)
await manager.connect_all()

# Get all tools from all servers
all_tools = manager.get_all_tools()

# Call a tool on any connected server
result = await manager.call_tool("filesystem", "read_file", {"path": "..."})

await manager.disconnect_all()
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
