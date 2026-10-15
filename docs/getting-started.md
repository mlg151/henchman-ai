# Getting Started

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

The CI configuration includes a Python 3.12 installed-wheel job on Linux, macOS,
and Windows. It checks both CLI aliases, local RAG storage and native file locking,
shell behavior, bounded Python quality scans, real REPL/Textual question input and interruption, and an offline
five-provider read/edit/test/recover workflow outside
the source checkout. The broader Python 3.11–3.14 test matrix runs on Linux.

The Linux Python 3.12 wheel workflow has also passed locally in a fresh environment,
including both CLI aliases, question channels, and all five scripted-provider coding loops. This
verifies installed runtime behavior, not live model task quality.

Native Windows/macOS results must pass before treating those platforms as verified.
The current local development checks do not establish that result. See
[`FEATURE_TODO.md`](../FEATURE_TODO.md#coding-agent-reliability-and-portability)
for outstanding verification and [shell behavior](tools.md#shell) for host syntax
and interactive-terminal limits.

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
and retained provider text reasoning for continuation without printing that
reasoning in the chat display. See [provider streaming limits](providers.md#streaming-reliability)
for the distinction between text and structured reasoning support.

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
