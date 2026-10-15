# Configuration

Henchman-AI uses hierarchical configuration with settings files and environment variables.

## Configuration Hierarchy

Settings are loaded in this order (later overrides earlier):

1. **Defaults** - Built-in default values
2. **User settings** - `~/.henchman/settings.yaml`
3. **Workspace settings** - `.henchman/settings.yaml` in current directory
4. **Environment variables** - `HENCHMAN_PROVIDER`, `HENCHMAN_MODEL`

## Settings File

Create a YAML file at `~/.henchman/settings.yaml`:

```yaml
# Provider configuration
providers:
  default: deepseek
  
  deepseek:
    model: deepseek-chat
    
  openai_compat:
    model: gpt-4
    api_key: ${OPENAI_API_KEY}  # Environment variable expansion
    
  anthropic:
    model: claude-3-opus-20240229

# Tool settings
tools:
  auto_approve_read: true
  shell_timeout: 60

# UI settings
ui:
  theme: default
  markdown_rendering: true
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HENCHMAN_PROVIDER` | Override default provider |
| `HENCHMAN_MODEL` | Override model for default provider |
| `HENCHMAN_API_KEY` | Fallback API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENAI_API_KEY` | OpenAI or OpenAI-compatible API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `TOGETHER_API_KEY` | Together AI API key |
| `GROQ_API_KEY` | Groq API key |
| `FIREWORKS_API_KEY` | Fireworks AI API key |

## Provider Settings

### DeepSeek

```yaml
providers:
  deepseek:
    model: deepseek-chat  # or deepseek-coder
    base_url: https://api.deepseek.com  # Optional
```

### OpenAI

```yaml
providers:
  openai_compat:
    model: gpt-4  # or gpt-3.5-turbo, gpt-4-turbo
    base_url: https://api.openai.com/v1  # Optional
```

### Anthropic

```yaml
providers:
  anthropic:
    model: claude-3-opus-20240229
```

### Ollama (Local)

```yaml
providers:
  ollama:
    model: llama2
    base_url: http://localhost:11434
```

## Tool Settings

```yaml
tools:
  # Auto-approve read-only tools (no confirmation needed)
  auto_approve_read: true
  
  # Timeout for shell commands in seconds
  shell_timeout: 60
  
  # Auto-approve specific tools by name
  auto_approve:
    - read_file
    - ls
    - glob
```

## Context Management Settings

Configure intelligent context management to reduce token usage while preserving important information.

```yaml
context:
  # Enable intelligent context management (default: false)
  intelligent_context: false
  
  # Maximum tokens before compaction (default: 8000)
  max_tokens: 8000
  
  # Start compaction at this percentage of max_tokens (default: 0.75)
  compaction_threshold: 0.75
  
  # Minimum importance score to preserve a message (0.0-1.0, default: 0.5)
  importance_threshold: 0.5
  
  # Similarity threshold for clustering related messages (0.0-1.0, default: 0.7)
  cluster_similarity_threshold: 0.7
  
  # Use adaptive compression based on conversation type (default: true)
  adaptive_compression: true
```

The team leader and specialists use `max(1, int(max_tokens *
compaction_threshold))` as their effective conversation budget. The defaults
therefore give each agent a 6000-token budget. Cached agents retain that configured
budget when their provider changes. Standalone agent pools without a configured
budget continue to derive their limit from the selected model.

To change this session's capacity during a model switch, use
`/model set <provider> [model] --context-length <tokens>`. It updates the live
leader, cached specialists and future specialists using the same compaction
threshold. `/model` reports both the selected capacity and effective budget.
Omitting the option retains the current policy; invalid or nonpositive values
leave the model and context settings unchanged. This does not save settings to
disk. Use the `config set context.max_tokens` command for a persistent startup
value.

The selected capacity also enables request accounting: before each model call,
the agent estimates serialized messages (including reasoning), tool declarations,
and supported structured-response schemas, then reserves the provider's output
cap. OpenAI-compatible providers preserve an explicitly configured `max_tokens`
or `max_completion_tokens`, including `extra_body` precedence; ambiguous or
invalid caps are rejected. When neither cap is configured, they request
`min(4096, max(1, context_window // 4))` output tokens. Native Anthropic retains
its configured output cap.

The agent removes complete older conversation turns until the request estimate
fits. When a full tool catalog still cannot fit and bound `tool_search` is
available, it exposes discovery and core coding schemas within the same limit.
Search by an exact tool name to prioritize its real schema on the next request;
the latest search prioritizes up to five matching registered tools from its page.
Search results default to five entries; use `offset` for subsequent pages or set
`limit` from 1 to 100. A new user turn resets priorities. `/tools` and paginated
discovery retain access to the full inventory,
and execution retains the same agent allowlists and approval policies.

System instructions and the entire current turn remain intact, even when they
exceed the softer conversation target. If these required inputs, discovery,
explicitly searched or provider-required schemas and output cannot fit, the call fails locally with
counts and guidance. Custom scopes without discovery retain the explicit overflow
error. History remains available for persistence. This path uses deterministic
history pruning rather than the legacy summarizer or content truncation.
Standalone agents with `context_window=None` retain legacy compaction behavior.

Tokenizers and server chat templates differ, so these are estimates, not an exact
server guarantee; opaque provider extensions are not fully accounted for. Even
with a smaller tool catalog, large prompts, results or output caps may require a
larger model-supported capacity. This setting does not resize a local server's
context window or establish a whole-application RAM bound.

For detailed information on intelligent context management, see the [Intelligent Context Management](intelligent-context-management.md) documentation.

## Context Files (HENCHMAN.md)

Place `HENCHMAN.md` files in your project to provide context:

- **Global**: `~/.henchman/HENCHMAN.md`
- **Project**: `./HENCHMAN.md` (in project root)
- **Subdirectories**: Optional, for specific context

Inside a Git repository, context files are discovered from the repository root down to the current directory. Optional immediate-subdirectory discovery is available only when a Git root establishes the project boundary. Outside Git, Henchman reads project context only from the current working directory: it does not walk into subdirectories or inherit instruction files from parent directories. This boundary prevents unrelated parent context from being pulled into a non-repository session.

The global file `~/.henchman/HENCHMAN.md` is handled separately and may still be loaded for either kind of session.

## MCP Server Configuration

Configure Model Context Protocol servers:

```yaml
mcp_servers:
  filesystem:
    command: npx
    args: ["@anthropic-ai/mcp-filesystem-server", "/home/user"]
    trusted: false
    
  github:
    command: uvx
    args: ["mcp-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
    trusted: true
```

## Session Settings

```yaml
session:
  auto_save: true  # Save sessions on exit
  sessions_dir: ~/.henchman/sessions  # Session storage location
```

## Multi-Agent Settings

Configure the team of specialist agents.

```yaml
agents:
  # Which preset team to use (default: "default")
  team_preset: "default"

  # Max recursive delegation depth (default: 3)
  max_delegation_depth: 3

  # Max tokens for shared context between agents (default: 4000)
  shared_context_max_tokens: 4000

  # Agent overrides and custom agents
  agents:
    # Example: give Engineer a more powerful model and extra tools
    engineer:
      provider: "anthropic"
      model: "claude-3-5-sonnet-20240620"
      tools:
        - read_file
        - write_file
        - edit_file
        - ls
        - glob
        - grep
        - shell
        - web_fetch  # Allow Engineer to search docs directly

    # Example: disable Data Engineer agent
    data_engineer:
      enabled: false

    # Example: fully custom agent
    security_auditor:
      name: "Security Auditor"
      role: "security_auditor"
      description: "Audits code for security vulnerabilities"
      system_prompt: "You are a security expert. Analyze code for OWASP Top 10..."
      tools:
        - read_file
        - grep
        - glob
        - web_fetch
      can_delegate_to: ["explorer"]
```
