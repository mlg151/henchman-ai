# Getting Started

For API-created content captures, `henchman checkpoint` and interactive
`/checkpoint` share file/hunk review, preview, apply and interrupted-restore
recovery. See [commands and current platform limits](checkpoints.md#user-commands).
Automatic agent capture remains pending.

## Textual input and reading history

In the Textual UI, Enter or Ctrl+Enter submits a draft; Shift+Enter or Ctrl+J
inserts a newline. Multiline paste stays in the composer until submission.
Escape requests cancellation during work and preserves an unsent draft.

Scrolling into history, searching or expanding a card holds the reading
position while new output arrives. The navigation row shows new activity.
Use **Return to live**, Alt+End, or End with the transcript focused to resume
following. Alt+Page Up/Down scrolls history from the composer without changing
the draft. If the terminal intercepts an extended key, Tab to the visible button.
See the [interaction contract](ui-interaction-contract.md) for supported states
and the remaining native/accessibility qualification.

## Prerequisites

- **Python 3.11–3.14**: These are the currently supported and CI-tested Python versions
- **API Key**: For your chosen LLM provider (DeepSeek, OpenAI, Anthropic, etc.)
- **Git** (optional): For installing from source
- **uv** (optional): For faster dependency management

## Installation

### From PyPI (Recommended)

```bash
pip install henchman-ai
```

### From Source

```bash
git clone https://github.com/mlg151/henchman-ai.git
cd henchman-ai
pip install -e ".[dev]"
```

### With uv (Fastest)

```bash
uv pip install henchman-ai
```

The normal install resolves `chromadb>=1.5.9` for RAG storage and `scipy>=1.11.2` for NetworkX-backed PageRank queries. If an upgraded environment cannot import Chroma or run knowledge-graph importance queries, reinstall Henchman-AI with dependencies instead of using `--no-deps`.

### Platform verification

CI runs full Linux tests and installed-wheel checks on Linux, macOS and Windows
for Python 3.11–3.14. Candidate `4940cc9` passed
[all 20 required jobs](https://github.com/mlg151/henchman-ai/actions/runs/41808758654).
The wheel checks run outside the checkout and cover both CLI aliases, local RAG,
native file/shell behavior, bounded Python verification, question input and
cancellation, and small scripted coding workflows through five provider adapters.

This is automated installed-runtime evidence. Later feature changes, live coding
quality, native interactive usability and exact publication artifacts still need
their checks under #13, #30 and #36. See the
[roadmap](../FEATURE_TODO.md#coding-agent-reliability-and-portability) and
[shell behavior](tools.md#shell) for outstanding work and terminal limits.
For v0.4.2 strict-field migration and transient Python API notes, see
[configuration](configuration.md).

## API Key Setup

Henchman-AI requires an API key for your chosen LLM provider.

### DeepSeek (Default)

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### OpenAI-Compatible Providers

Henchman-AI supports multiple OpenAI-compatible providers. Each has its own API key environment variable:

#### OpenAI
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

#### Together AI
```bash
export TOGETHER_API_KEY="your-together-api-key"
```

#### Groq
```bash
export GROQ_API_KEY="your-groq-api-key"
```

#### Fireworks AI
```bash
export FIREWORKS_API_KEY="your-fireworks-api-key"
```

**Note**: For OpenAI specifically, use `openai_compat` provider with `base_url: https://api.openai.com/v1`. For other providers, use their specific provider names (`together`, `groq`, `fireworks`).

### Anthropic

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### Ollama (Local Models)

Ollama allows you to run models locally without an API key:

1. Install Ollama from [ollama.ai](https://ollama.ai/)
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve`
4. No API key needed - Henchman-AI will connect to `http://localhost:11434` by default

### Other Providers

Henchman-AI also supports OpenRouter, Together AI, Groq, Fireworks AI, and other OpenAI-compatible services. See [Providers](providers.md) for complete setup instructions for these services.

## First Run

### Project instruction files

Henchman loads project instructions before the first message. `HENCHMAN.md` stays the primary file; portable `AGENTS.md` (per the cross-tool convention) is also discovered by default, along with `.henchman/HENCHMAN.md`, `.github/copilot-instructions.md` and `.gemini/GEMINI.md`. In a Git repository, files load from the repository root down to the current directory; deeper directories take precedence by position, and sibling directories never leak into each other. Outside Git, only the current directory is read. Attached sessions record which instruction files were in force (paths, scopes, order and digests — never the text), so resumed sessions and audits can see the same provenance. See [configuration](configuration.md#context-files-henchmanmd-and-agentsmd) for the full precedence rules and boundaries.

### Interactive Mode

Start the interactive REPL:

```bash
henchman
```

You'll see a welcome message and prompt. By default, you are talking to the **Tech Lead** of a multi-agent team.

```
Henchman-AI - /help for commands, /quit to exit

❯ 
```

### Headless Mode

Run with a single prompt:

```bash
henchman chat --prompt "What is 2 + 2?"
```

Or reference a file in the prompt:

```bash
henchman chat -p "Explain @file.py"
henchman chat --prompt "Review the Python code in @file.py"
```

For scripts, `--output-format json` or `stream-json` produces one JSON event per
line without terminal-width wrapping or emoji substitution. `json-complete`
produces an indented array; see [the output contract](api.md#headless-json-output).

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/quit` | Exit the CLI |
| `/clear` | Clear conversation history |
| `/tools` | List available tools |
| `/agent` | Multi-agent management (list, config, or talk directly to specialists) |
| `/goal <objective>` | Keep working across turns until the goal is completed or paused |
| `/goal status/pause/resume/complete/clear` | Inspect or control the session goal |
| `/team` | Show team status or reset all agents |
| `/mcp` | Manage configured MCP servers when the runtime registers both MCP tools |
| `/model` | Show or change the model and provider |
| `/chat save [tag]` | Save current session |
| `/chat list` | List saved sessions |
| `/chat resume <tag>` | Resume a session |

`/chat resume` also accepts a full session ID. It restores assistant/tool history
and supported provider continuation envelopes without displaying opaque payloads.
Incompatible or unavailable continuation stops dispatch explicitly. See
[provider continuation](providers.md#provider-continuation) for supported profiles
and the distinction from visible reasoning.

Shell and Python tool calls run in the background by default. You can keep
submitting messages while the agent works; they run in order at turn boundaries.
The agent can track multiple jobs using their individual task IDs. See
[background execution and goal controls](tools.md#background-execution).

## Special Input Syntax

### File References

Use `@filename` to include file contents:

```
❯ Explain the code in @src/main.py
```

### Shell Commands

Prefix with `!` to run shell commands:

```
❯ !ls -la
```

## Current Capability Scope

- `web_search` is live only when it appears in the runtime registry.
- Skills are local-only discovery and inspection surfaces.
- Integration commands export local blueprints; the Slack blueprint does not provide a Slack runtime.
- `schedule_cron` stores and manages schedule metadata but does not execute jobs in the background.
- Remote plugin marketplace and agent registry installs are unavailable in this variant. Local plugin loading and local agent list/show/publish flows remain available.

Run `henchman help`, `henchman doctor`, or the in-session tool discovery surfaces for classifications derived from the shared capability matrix.

## Next Steps

- [Configuration](configuration.md) - Customize settings
- [Providers](providers.md) - Set up different LLM providers
- [Tools](tools.md) - Learn about built-in tools
