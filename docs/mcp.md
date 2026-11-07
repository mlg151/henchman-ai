# MCP Integration

Henchman-AI supports the Model Context Protocol (MCP) for connecting to external tool servers.

MCP is classified as runtime-wired only when both the `mcp` and `mcp_auth` tools are registered. A configuration entry or installed MCP dependency alone does not make the surface live; use help or doctor to inspect the current runtime classification. Auth status reporting indicates whether credentials are present without printing their values.

The client pins MCP SDK 2.3.0 and tests stdio revisions 2024-11-05, 2025-03-26,
2025-06-18, 2025-11-25 and 2026-07-28. Streamable HTTP supports the latter four
revisions with JSON and SSE responses through an owned bounded transport. The SDK
negotiates modern discovery or legacy initialization. Explicit resource and prompt
previews and explicit session attachment are available in interactive frontends;
OAuth remains [roadmap work](standards.md#mcp-adoption-details). These tested subsets do
not establish complete protocol conformance.

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
| `transport` | string | `stdio` (default) or `streamable_http` |
| `command` | string | Required for stdio; forbidden for HTTP |
| `args` | list | Stdio command arguments |
| `env` | dict | Stdio environment variables |
| `url` | string | Required HTTP endpoint; forbidden for stdio |
| `trusted` | bool | If true, skip tool confirmation; other policy still applies |
| `request_timeout_seconds` | number | Per-request deadline, default 30 |
| `negotiation_timeout_seconds` | number | Total negotiation deadline, default 40 |
| `catalog_timeout_seconds` | number | Total paginated catalog deadline, default 60 |

Timeouts must be finite, positive and at most 3,600 seconds. Settings validation
rejects mixed transport configuration before starting a process or request.

### Credentials and connection lifetime

An `env` value of exactly `${NAME}` resolves the named environment variable once,
just before starting that server. Missing or empty variables and partial references
such as `prefix-${NAME}` fail before startup. Literal values remain literal;
resolved values are not expanded recursively. The settings file retains the
reference. Only explicitly configured values supplement the MCP SDK's normal
process-environment allowlist.

Changing or clearing a managed token, changing a referenced environment value,
or changing the transport, endpoint, command, arguments, environment, timeouts or trust setting invalidates
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
HTTP authentication remains separate roadmap work. Context retrieval uses the
same connection and access guards described below.

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
The adapter rejects continuation fields before the pinned SDK can strip fields
from a later revision, including mixed results and omitted `resultType` tags.
This applies to tools, resources and prompts without replaying a request.

SDK 2.3 has no public telemetry-off switch. A configured tracer provider or active
outbound trace/baggage propagation therefore blocks connection and dispatch with
an explicit diagnostic. Henchman leaves application-global tracing state intact.
Known credentials remain projected from server stderr and SDK diagnostics. See the
[pinned SDK implementation](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/src/mcp/shared/_otel.py).

### Streamable HTTP

```yaml
mcp_servers:
  local_service:
    transport: streamable_http
    url: http://127.0.0.1:8080/mcp
    trusted: false
    request_timeout_seconds: 30
```

Use HTTPS for remote endpoints. Plain HTTP requires a literal loopback IP address;
`http://localhost` is not accepted. URLs cannot include credentials, query strings
or fragments. The client verifies TLS, ignores environment proxy/TLS settings,
rejects redirects and sends no inherited cookies, arbitrary headers or stdio
credentials. HTTP authentication is currently unsupported: a 401 produces an
explicit diagnostic without retrying or fetching advertised OAuth metadata.

Each request rechecks its configured destination and active access policy. MCP
is unavailable under restricted filesystem roots or disabled network access,
including previously connected clients. Connection cleanup also checks current
access policy. A legacy session uses its negotiated session header and bounded
DELETE cleanup; a cleanup failure leaves remote state unknown.

JSON messages and each SSE event are limited to 1 MiB; an SSE response is limited
to 4 MiB in total, with the shared JSON depth/node limits. Compressed responses
and server-initiated requests are unsupported. A response must match its request
ID. Modern parameter-header maps change only with a complete validated catalog.
HTTP internals that could expose endpoints or session headers are suppressed only
within owned MCP requests; transport failures use value-free diagnostics.

Requests are sent once. Disconnection, timeout or a response without a result
can leave the outcome unknown; there is no automatic GET resumption, reconnect
or effect replay. Cancellation settles owned request tasks and session cleanup.
The per-request/negotiation/catalog settings above apply to both transports.
Independent loopback HTTP/TLS fixtures cover the supported revisions, JSON/SSE,
headers, cancellation, bounds and policy changes. These fixtures do not qualify remote production servers;
final native artifact qualification remains pending.

### OAuth configuration and storage foundation

An optional `oauth` group is accepted only for Streamable HTTP servers. It binds
an exact HTTPS `issuer`, a pre-registered public `client_id`, an optional canonical
`resource` URI (defaulting to the server endpoint), and up to 16 additional HTTPS
`allowed_endpoint_origins`. The resource must contain the endpoint under the same
origin and path. Configuring this group alone currently refuses connection:
interactive login and normal manager connection activation are not yet wired.
Python embedders can use the explicit authenticated transport described below.

The library's `discover_oauth` performs credential-free metadata discovery under
a caller-supplied authorization guard. It checks exact issuer/resource identity,
configured destination origins and S256/public-client support. Each request has
a 10-second deadline and discovery a 30-second deadline; documents are limited
to 64 KiB with bounded JSON structure. Redirects, cookies, inherited proxy/auth
settings and compressed metadata are refused. One unambiguous Bearer challenge
is supported; remote metadata cannot add approved origins.

The library's explicit `login_oauth` and `refresh_oauth` flows use an owned literal
loopback callback, S256 PKCE and generation-checked one-shot token exchange. Login
requires an injected asynchronous browser opener and a current authorization guard;
it does not launch a browser by default. The callback validates its exact host,
path, state and issuer, consumes one code and joins accepted connections on cleanup.
Login has a 300-second total deadline; token exchange has a 30-second deadline and
64 KiB response limit. Refresh uses the persisted endpoint and scopes, without
discovery substitution or automatic retry. Missing expiry remains distinct from
an already expired token. Logout or policy changes reject late publication.

Discovery and token exchange use the same pinned HTTP/1.1 pre-header guard as
authenticated MCP requests. It rechecks caller/configuration/policy and the
current claim after TCP/TLS setup, validates the actual method and destination,
and permits one header attempt. Unknown transport extensions and runtime versions
are refused. Token expiry starts at that boundary. Failure or cancellation before
it leaves the owned token claim needing a fresh login, without restoring an old
rotating token. Crossing the boundary does not prove that bytes reached the peer:
a later write failure conservatively retains `login_started`/`refresh_started`
uncertainty and never triggers automatic replay. Logout and newer generations
remain authoritative.

`McpManager.create_from_settings` binds OAuth to the captured project root and
the live settings owner. Direct embedders can call `bind_oauth_runtime` once.
The explicit `oauth_status`, `oauth_login`, `oauth_refresh` and `oauth_logout`
methods require a trusted caller guard that returns `None` or raises; server
tool trust does not grant login authority. Login also requires the caller's
asynchronous browser opener. Network operations retain the initial policy and
recheck live settings, policy and credential generations before effects and
publication. Local status and logout remain available under network restrictions;
logout also works after server configuration removal.

Manager teardown invalidates pending OAuth operations before awaiting transport
cleanup and blocks new login/refresh admission until cleanup settles. The caller
still owns each flow's cancellation and deadline; teardown does not join those
caller tasks. These manager APIs do not connect or replay MCP requests, and
configured OAuth connections remain refused pending normal manager activation and
interactive integration.

### Owned browser handoff helper

The explicit `henchman.cli.oauth_browser.open_oauth_browser(url, authorize=guard)`
helper supports a bounded HTTPS authorization URL and a current caller guard.
It starts an isolated Python child with fixed arguments, waits for READY, rechecks
authority, cancellation and the deadline, then sends the URL through stdin. The
helper's arguments and diagnostics never contain the URL. Its environment retains
required desktop variables but excludes provider keys and browser command templates.

Linux uses an absolute `xdg-open` with a configured graphical desktop; macOS uses
`/usr/bin/open`; Windows invokes the native URL handler in the owned child. Unix
launchers replace that child's PID and receive null standard streams. The platform
launcher necessarily receives the URL as an argument or native-handler parameter.
The helper waits at most five seconds for READY and ten seconds for handoff, with
bounded terminate/kill cleanup of its owned launcher. It cannot close an existing
browser or revoke a page already handed off. A later failure reports that the page
may have opened and never retries automatically. Successful handoff does not mean
authentication succeeded.

Owned synthetic-launcher tests cover cancellation, stale guards, deadlines, output
bounds and cleanup. No real browser/account or native Windows/macOS desktop flow is
qualified. This helper is not yet wired into interactive commands; ordinary OAuth
connections remain refused until the controller and frontend integration lands.

### Explicit authenticated HTTP client

`manager.capture_oauth_http(server, authorize=guard)` reads matching local ready
credentials and captures their authority without a network request or returning
a token. Pass it explicitly as `McpClient(..., oauth_authority=authority)`; ordinary
manager connections still refuse OAuth configurations. No browser, refresh or
RPC replay is triggered by connection or authentication failure.

Each request acquires owned capacity before checking caller authority, exact
configuration, initial/live policy, credential generation and expiry. The pinned
`httpx2==2.16.0`/`httpcore2==2.16.0` HTTP/1.1 profile rechecks after connection/TLS
setup, immediately before header transmission. Other stack versions and HTTP/2
are refused for authenticated clients. This cannot revoke bytes already sent or
make cross-process credential changes atomic with a socket write. Request metadata
cannot override authentication or routing headers; redirects, cookies and inherited
proxy credentials remain unsupported.

A 401 rejects only the dispatched credential generation and access-token digest,
retaining its refresh material for a later explicit refresh. An older 401 cannot
invalidate a rotated credential. A 403 reports denied scope without automatic
login or retry. Legacy session cleanup permits one exact client/session/resource
DELETE after local connection invalidation, while still enforcing current
configuration, policy and stored credentials. Logout, expiry or rotation can deny
that cleanup, leaving remote state explicitly unknown; the 2026 revision has no
session DELETE.

Response cleanup is bounded and preserves the original cancellation or rejection.
Failed or timed-out cleanup makes the transport unavailable, blocks further
dispatch and requires an explicit fresh connection. Manager teardown also revokes
normal permits captured by direct clients. Local TLS fixtures cover these
boundaries; they do not qualify a real authorization service or browser flow.

### Retained OAuth credentials

Bind `register_evidence` before credential access. The retained store registers old
and rotated credentials, plus credential fields from parsed responses, with bound
evidence policies before credential validation or replacement; historical values
remain in runtime memory only.
Callback responses and flow errors omit credential values. Local TLS/browser
fixtures exercise these library flows; they do not enable interactive login or
qualify a remote authorization service.

`McpAuthService.oauth_store()` uses a separate versioned
`.henchman/mcp/oauth.json`; legacy stdio tokens are never promoted. Project/server/
issuer/resource/client binding and persistent generations reject stale completions
after logout or configuration changes. Login/refresh claims are committed before
their authority is returned. A refresh claim removes the old token from reusable
storage before returning it; an interrupted refresh requires login again. Status
contains no token values. This foundation makes no remote logout/revocation claim.

The store is plaintext, bounded to 1 MiB/128 server records, with atomic replacement
and retained revocation tombstones. POSIX storage uses private files and pinned
directory descriptors. Windows rejects existing reparse points and checks opened
file identities; confidentiality depends on directory ACLs, and a concurrent
parent-directory swap is not prevented. Filesystem rollback is outside this store's
authority. Interactive login and transport integration remain tracked under #25.

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

### Resource and prompt previews

The REPL and Textual share explicit commands for a currently connected server:

```text
/mcp resources <server>
/mcp templates <server>
/mcp read <server> <uri>
/mcp prompts <server>
/mcp prompt <server> <name> {"argument":"value with spaces"}
```

The three list commands refresh only the selected catalog. Resource URIs are
passed to that server as opaque identifiers; Henchman does not open local files,
follow links, fetch icons or expand templates. Prompt retrieval requires an
explicitly fetched current declaration and validates required/unknown arguments
before dispatch. Argument values must be strings; JSON string whitespace is
preserved. Resource-only and prompt-only servers need not expose tools.

Previews show untrusted data with source, negotiated protocol, connection/catalog
generation and retrieval arguments. Native typed content remains available to
the API caller; interactive output redacts registered credentials, summarizes
binary media and renders markup literally. Prompt roles are displayed as data.
Preview does not append messages, change instructions, invoke a model, or attach
content to a session. Attaching a reviewed result is a separate explicit action.

Catalogs retain at most 32 pages, 1,024 entries and 4 MiB, with the configured
catalog deadline including lock waits (default 60 seconds). Results retain at
most 256 blocks and pass the 1 MiB contract bound; requests use the configured
deadline (default 30 seconds). Invalid pages preserve the previous catalog.
Retrieval rechecks connection, credentials and access policy, without implicit
connection, refresh, subscriptions, completion or multi-round replay.

### Attach a reviewed context result

When a resource or prompt preview belongs to the current interactive session,
the command shows `/mcp attach <preview_id>`. Run that command to append the
captured text and metadata as an ordinary user message. It saves the session
before updating live history and does not retrieve the result again or start a
model turn. Prompt roles remain quoted source data; binary media remains an
explicit summary. Existing assistant signatures and tool exchanges are preserved.

Attachment requires idle execution, settled tool/delegation work and no incomplete
tool exchange. Pause any active goal and resolve workflow recovery before attachment.
The handle belongs to the exact session and agent that requested the preview;
switching either during retrieval cannot redirect the result into another session.
Reconnection, catalog refresh, credential/configuration changes and policy
revocation invalidate the capture. Retrieve a fresh preview after those changes.

The manager retains at most 16 preview handles and 4 MiB of captured data for ten
minutes. A successful attachment consumes its handle. An ordinary save failure
leaves it available for retry; an uncertain commit is subject to the existing
session conflict check and cannot append a duplicate. Handles are process-local;
identifiers retained in imported or restored messages confer no attachment rights.

Session retention, branch/merge and playback preserve typed source evidence.
Compaction keeps attachment-derived summaries in user messages and marks omitted
payloads, arguments and oversized source identifiers. Repeated summaries retain
at most eight source records plus an omission digest when more records were
present. Captured digests identify earlier evidence; they do not certify the
server's statements or grant instruction authority.

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
