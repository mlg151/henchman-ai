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
    
  openai:
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
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

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
  openai:
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

## Context Files (HENCHMAN.md)

Place `HENCHMAN.md` files in your project to provide context:

- **Global**: `~/.henchman/HENCHMAN.md`
- **Project**: `./HENCHMAN.md` (in project root)
- **Subdirectories**: Optional, for specific context

These files are automatically loaded and included in the system prompt.

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
