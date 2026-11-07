# MCP Integration

Henchman-AI supports the Model Context Protocol (MCP) for connecting to external tool servers.

MCP is classified as runtime-wired only when both the `mcp` and `mcp_auth` tools are registered. A configuration entry or installed MCP dependency alone does not make the surface live; use help or doctor to inspect the current runtime classification. Auth status reporting indicates whether credentials are present without printing their values.

The stdio client uses the exactly pinned MCP SDK 2.3.0 and tests revisions
2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 and 2026-07-28. It negotiates modern
discovery or legacy initialization through the SDK. Streamable HTTP, OAuth,
resources and prompts remain [roadmap work](standards.md#mcp-adoption-details).
This tested stdio subset is not a claim of complete protocol conformance.

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
      # Optional: Backend selection: "lsp" or "jetbrains" (if plugin installed)
      SERENA_BACKEND: "lsp"
      # Optional: Language server configuration
      SERENA_LSP_PYTHON_PATH: "/usr/bin/python3"
      # Optional: Logging level
      SERENA_LOG_LEVEL: "INFO"
      # Optional: Enable JetBrains plugin backend if available (deprecated, use SERENA_BACKEND instead)
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

### Credentials and connection lifetime

An `env` value of exactly `${NAME}` resolves the named environment variable once,
just before starting that server. Missing or empty variables and partial references
such as `prefix-${NAME}` fail before startup. Literal values remain literal;
resolved values are not expanded recursively. The settings file retains the
reference. Only explicitly configured values supplement the MCP SDK's normal
process-environment allowlist.

Changing or clearing a managed token, changing a referenced environment value,
or changing the server command, arguments, environment or trust setting invalidates
the connection. Retained tool handles then reject new dispatch until the server
is reconnected. This does not undo a call already dispatched, and external edits
to the auth file are not watched automatically.

Tokens set through `mcp_auth` are stored in `.henchman/mcp/auth.json` using a
private atomic replacement (mode `0600` on POSIX); symlink auth files are rejected.
Windows permissions follow the directory's existing ACL. Configured and resolved
credentials, including earlier values after rotation, are registered with the
session/display evidence policy and redacted from process and SDK diagnostics.
Execution still receives the original credential values.

The native stdio connection owns its SDK contexts in one lifecycle task, so
startup, calls and shutdown may originate from different application tasks.
Failed or cancelled startup and shutdown join owned transport cleanup. This is
part of the [stdio compatibility foundation](standards.md#implemented-compatibility-foundation-v042-work);
modern transports and resource/prompt retrieval remain separate roadmap work.

### Stdio wire limits and telemetry

UTF-8 stdio frames are limited to 1 MiB before decoding or parsing. The canonical
depth/node limits also apply; oversized, deeply nested or unterminated frames end
the connection. Malformed individual JSON lines produce value-free diagnostics and
may be followed by valid messages. Each native request has a 30-second outer
deadline including transport handoff; negotiation has a 40-second total deadline.
A complete catalog walk has a 60-second deadline and remains capped at 32 pages.
These deadlines include waits before the SDK's response timer starts.
After cancellation, the pinned SDK may spend up to five additional seconds
settling its courtesy cancellation write; bounded process shutdown follows.
The exact SDK pin qualifies private process/shutdown helpers
used by this bounded framing adapter.

Tool dispatch uses one typed request. It does not enter SDK automatic header
mismatch replay or multi-round input continuation; `input_required` is explicitly
unsupported. An ambiguous transport failure reports that the outcome may be
unknown. It does not establish that effects were undone.

SDK 2.3 has no public telemetry-off switch. A configured tracer provider or active
outbound trace/baggage propagation therefore blocks connection and dispatch with
an explicit diagnostic. Henchman leaves application-global tracing state intact.
Known credentials remain projected from server stderr and SDK diagnostics. See the
[pinned SDK implementation](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/shared/_otel.py).

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

### Refresh a connected catalog

```
/mcp refresh <server>
```

The `mcp` management tool also accepts `action="refresh"` with `server`.
Refresh follows all discovery pages and publishes only a complete validated
catalog. Invalid schemas, repeated cursors, duplicate names, collisions with
separately registered tools, or cancellation leave the previous catalog intact.
Successful refresh replaces owned registry entries and invalidates retained
wrappers and their confirmation grants. Scoped agents retain their allowlists.
Custom injected clients without atomic refresh support report that limitation.

Catalogs are bounded to 32 pages, 1,024 tools and 4 MiB in total; each accepted SDK
payload is also subject to the 1 MiB local contract bound. Input/output schemas,
annotations and typed result data are detached from the SDK models. Annotations
never grant execution authority. Arguments are validated before transport and
successful structured results against their captured output schema afterwards.
Error results remain errors rather than being checked as successful output.

The native result and `ToolResult` preserve content blocks, structured content,
presence separately from null, and metadata. Text compatibility output labels
non-text blocks. Modern revision 2026-07-28 retains scalar, array and null
structured output. Legacy revisions retain their narrower wire schema/result
restrictions and fail explicitly on unsupported forms. Results accept at most
256 blocks within the payload bound.
Agent, CLI/headless, chat and session paths now retain these typed fields. All five
builtin provider adapters send an explicit JSON text projection; image/audio data
and binary resource blobs are described rather than sent as binary. Original
typed data remains in raw agent history and redacted saved history where those
consumers retain it. Context truncation identifies omitted payloads and their
digests even when a text result remains. Exports, VCR, merge and restored sessions
preserve typed meaning. API caller-supplied continuation inputs remain text-only.
The native stdio adapter also enforces the pre-parse wire bound described above.
Custom injected clients must qualify their own transport bounds.

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

The entries below are external server examples, not services bundled or operated by Henchman-AI. In particular, configuring a third-party Slack MCP server is separate from Henchman's export-only Slack integration blueprint.

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

#### Serena Configuration Options:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `SERENA_WORKSPACE` | string | Current directory | Workspace directory to analyze |
| `SERENA_BACKEND` | string | `"lsp"` | Backend selection: `"lsp"` or `"jetbrains"` (if plugin installed) |
| `SERENA_LSP_PYTHON_PATH` | string | System Python | Path to Python interpreter for LSP backend |
| `SERENA_LOG_LEVEL` | string | `"INFO"` | Logging level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` |
| `SERENA_USE_JETBRAINS` | boolean | `"false"` | Deprecated: Use `SERENA_BACKEND: "jetbrains"` instead |

**Example configuration:**
```yaml
serena:
  command: uvx
  args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
  env:
    SERENA_WORKSPACE: "/path/to/your/project"
    SERENA_BACKEND: "lsp"
    SERENA_LSP_PYTHON_PATH: "/usr/bin/python3"
    SERENA_LOG_LEVEL: "INFO"
  trusted: true
```

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

## Troubleshooting

### Common Issues

#### Serena Connection Issues

| Issue | Solution |
|-------|----------|
| **"uvx not found"** | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Connection failed** | Check `uvx --version` and internet connectivity |
| **No tools discovered** | Verify Serena starts correctly: `uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help` |
| **Performance issues** | Consider using JetBrains plugin backend for better analysis: `SERENA_BACKEND: "jetbrains"` |

#### General MCP Issues

| Issue | Solution |
|-------|----------|
| **Server won't start** | Check command path and arguments in configuration |
| **Tools not appearing** | Verify server is trusted or confirm tool execution |
| **Connection timeout** | Increase timeout in settings or check server logs |
| **Permission errors** | Ensure server has appropriate file system permissions |

### Debugging Tips

1. **Enable verbose logging**:
   ```bash
   henchman --verbose
   ```

2. **Check MCP server status**:
   ```
   /mcp status
   ```

3. **View available tools**:
   ```
   /tools
   ```

4. **Test server manually**:
   ```bash
   # Test Serena server directly
   uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help
   ```

5. **Check environment variables**:
   ```bash
   echo $SERENA_WORKSPACE
   echo $SERENA_BACKEND
   ```

### Getting Help

- **GitHub Issues**: [Henchman-AI Issues](https://github.com/mlg151/henchman-ai/issues)
- **MCP Documentation**: [Model Context Protocol](https://modelcontextprotocol.io/)
- **Serena Repository**: [oraios/serena](https://github.com/oraios/serena)
