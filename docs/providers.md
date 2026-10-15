# Providers

Henchman-AI supports multiple LLM providers through a unified interface.

## Supported Providers

| Provider | Status | API Compatibility | Configuration Name | Notes |
|----------|--------|-------------------|-------------------|-------|
| DeepSeek (`deepseek`) | ✅ Default | OpenAI-compatible | `deepseek` | Default provider |
| Anthropic (`anthropic`) | ✅ | Native SDK | `anthropic` | Claude models via native SDK |
| Ollama (`ollama`) | ✅ | OpenAI-compatible | `ollama` | Local models, no API key required |
| OpenRouter (`openrouter`) | ✅ | OpenAI-compatible | `openrouter` | Access to hundreds of models |
| OpenAI (`openai`) | ✅ | OpenAI-compatible | `openai` | OpenAI endpoint default; configure a model |
| OpenAI-Compatible (`openai_compat`) | ✅ | OpenAI-compatible | `openai_compat` | Generic provider for ANY OpenAI-compatible API (OpenAI, Together, Groq, Fireworks, etc.) |
| Together AI (`together`) | ✅ | OpenAI-compatible | `together` | Alias for `openai_compat` with Together base URL |
| Groq (`groq`) | ✅ | OpenAI-compatible | `groq` | Alias for `openai_compat` with Groq base URL |
| Fireworks AI (`fireworks`) | ✅ | OpenAI-compatible | `fireworks` | Alias for `openai_compat` with Fireworks base URL |

**Note**: The `openai_compat` provider is a generic provider for any OpenAI-compatible API. Specific providers like `together`, `groq`, and `fireworks` are aliases for `openai_compat` that require you to configure the appropriate base URL (see examples below). For OpenAI specifically, use `openai_compat` with `base_url: https://api.openai.com/v1` and `api_key: ${OPENAI_API_KEY}`.

**Configuration Names**: Use these names in `settings.yaml` (for example, `providers.default: deepseek`) or with `henchman config set providers.default <name> --scope project`.

## Provider selection and credentials

Startup, runtime switching, API/chat agents, and agent overrides use the shared
`create_configured_provider()` factory. The configured provider is authoritative;
having another provider's API key does not select that provider. `HENCHMAN_PROVIDER`
and `HENCHMAN_MODEL` override the saved selection through the settings loader.

Credentials are resolved in this order:

1. An explicit factory override, when supplied by a caller.
2. The selected provider's `api_key` setting.
3. Its provider-specific environment variable.
4. `HENCHMAN_API_KEY` as a fallback.

An `api_key: ${VARIABLE_NAME}` setting resolves that environment variable at
construction time without writing the secret into settings. A missing referenced
variable is an error; it does not silently select another account. Together, Groq,
and Fireworks use `TOGETHER_API_KEY`, `GROQ_API_KEY`, and `FIREWORKS_API_KEY`
respectively before the generic fallback.

For OpenRouter, select it explicitly:

```bash
export OPENROUTER_API_KEY="your-api-key"
export HENCHMAN_PROVIDER=openrouter
export HENCHMAN_MODEL="your-provider/your-model"
henchman
```

Replace the model placeholder with an identifier supported by your account.
The equivalent persistent configuration belongs in `.henchman/settings.yaml`.
OpenRouter, DeepSeek, and generic compatible configurations can include request options such
as `temperature`, `max_tokens`, and SDK `extra_body` options. Per-call options
override those defaults without modifying the saved configuration. Request
defaults cannot replace agent-owned `messages`, `tools`, or `stream` fields.

For a compatible endpoint configured without an API key, the transport supplies a
non-secret placeholder (`not-required`) to SDK versions that require a nonempty
credential. The configured key remains empty. This placeholder does not provide
authentication for endpoints that require a real key.

Compatible providers accept the public `model` setting; legacy `default_model`
is also supported. Configure `base_url` for generic compatible endpoints and
aliases; `openai` defaults to `https://api.openai.com/v1`. A generic local endpoint
can run without credentials. Ollama needs no cloud key and uses its configured
endpoint, then `OLLAMA_HOST`, then `http://localhost:11434/v1`.
Ollama endpoint origins with no path (or `/`) receive the `/v1` API path;
explicit proxy paths remain intact. Ollama forwards compatible request defaults,
including output caps and sampling options, with per-call values taking precedence.

`/model set <provider> [model] [--context-length <tokens>]` retains saved endpoint
and credential settings. For example:

```text
/model set openrouter your-selected-model --context-length 32768
```

The optional positive integer sets the session's `context.max_tokens` capacity.
The configured compaction threshold determines the effective conversation budget
(32768 × 0.75 = 24576 with the default threshold). The leader and all cached and
future specialists receive that budget, including specialists with their own
provider/model selections. Omitting the option preserves the current context
policy. `/model` shows the configured length and effective conversation budget.
The change takes effect for subsequent requests without discarding conversation
history. It is session-local; use `henchman config set context.max_tokens 32768
--scope project` to change the saved startup setting.

Runtime switches preserve conversation history and session/tool bindings, update
the effective model and automatic context budget, and preserve explicit agent
overrides. Switching configures the client locally; it does not prove network
connectivity or account access. Invalid configuration leaves the active runtime
unchanged.

Before each request, the selected capacity bounds estimated serialized input,
including tools, plus a reserved output cap. Older turns can be omitted from the
request while history is retained; oversized required inputs fail locally.
Configured output caps remain unchanged, and an unset compatible-provider cap
receives a bounded default. Tokenizer estimates and server limits can differ;
see [context configuration](configuration.md#context-management-settings).

## DeepSeek (Default)

DeepSeek is the default provider, offering high-quality responses at competitive prices.

### Setup

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: deepseek
  deepseek:
    model: deepseek-chat  # or deepseek-coder
```

### Models

- `deepseek-chat` - General purpose chat model
- `deepseek-coder` - Optimized for code generation

## OpenAI-Compatible Providers

The `openai_compat` provider works with any API that follows the OpenAI chat completions format. This includes OpenAI itself, Together AI, Groq, Fireworks AI, and other compatible services.

### OpenAI

To use OpenAI models, configure the `openai_compat` provider with OpenAI's base URL:

#### Setup

```bash
export OPENAI_API_KEY="your-api-key"
```

#### Configuration

```yaml
providers:
  default: openai_compat
  openai_compat:
    model: gpt-4
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
```

#### Models

- `gpt-4` - Most capable model
- `gpt-4-turbo` - Faster, cheaper GPT-4
- `gpt-3.5-turbo` - Fast and economical

### Together AI

```yaml
providers:
  default: together
  together:
    model: meta-llama/Llama-3-70b-chat-hf
    base_url: https://api.together.xyz/v1
    api_key: ${TOGETHER_API_KEY}
```

### Groq

```yaml
providers:
  default: groq
  groq:
    model: llama3-70b-8192
    base_url: https://api.groq.com/openai/v1
    api_key: ${GROQ_API_KEY}
```

### Fireworks AI

```yaml
providers:
  default: fireworks
  fireworks:
    model: fireworks-ai/llama-v3-70b-instruct
    base_url: https://api.fireworks.ai/inference/v1
    api_key: ${FIREWORKS_API_KEY}
```

## Anthropic

### Setup

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: anthropic
  anthropic:
    model: claude-3-opus-20240229
```

### Models

- `claude-3-opus-20240229` - Most capable
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-haiku-20240307` - Fast and efficient

## Ollama (Local)

Run models locally with Ollama.

### Setup

1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama2`
3. Start the server: `ollama serve`

### Configuration

```yaml
providers:
  default: ollama
  ollama:
    model: llama2
    base_url: http://localhost:11434
```

### Models

Any model available in Ollama:

- `llama2`, `llama3`
- `codellama`
- `mistral`, `mixtral`
- `phi3`
- And many more...

## OpenRouter

Access hundreds of models through [OpenRouter](https://openrouter.ai/).

### Setup

```bash
export OPENROUTER_API_KEY="your-api-key"
```

### Configuration

```yaml
providers:
  default: openrouter
  openrouter:
    model: "anthropic/claude-3.5-sonnet"
```

### Models

OpenRouter supports hundreds of models from various providers. Refer to the [OpenRouter Model List](https://openrouter.ai/models) for specific model identifiers.

## Basic Usage

### Streaming reliability

All providers feed the same agent event loop. OpenRouter, DeepSeek, Ollama,
and other OpenAI-compatible endpoints share the compatible streaming adapter;
Anthropic uses its native adapter.

- Tool arguments must decode to a JSON object. Malformed JSON, arrays, scalar
  values, and `null` raise a validation error instead of becoming empty arguments.
  An empty argument string is accepted for argumentless tools.
- Before the agent records or dispatches a tool batch, each call must have a
  nonempty ID and name, IDs must be unique within the response, and a
  `tool_calls` finish must contain at least one request.
- The compatible adapter emits assembled tool calls only when the provider
  finishes with `tool_calls`. Token-limit and content-filter endings do not
  persist partial tool calls as completed requests.
- Transport and provider errors propagate to the agent's `ERROR` event; they
  are not saved as successful assistant replies. A stream that ends without
  a finish reason is reported as interrupted. The agent does not retry failed
  partial replies through its stall-detection mechanism.
- Text on the finish chunk is displayed, and usage-only trailing chunks are
  retained even when their `choices` array is empty. Repeated finish metadata
  does not dispatch a tool twice.
- Compatible text reasoning accepts both `reasoning_content` and OpenRouter's
  `reasoning` field, preferring nonempty `reasoning_content` when both appear.
  Text is retained through tool turns and sent back using `reasoning_content`,
  which OpenRouter accepts as an alias. This does not preserve structured or
  encrypted `reasoning_details` blocks; models requiring those blocks need
  additional adapter support. See [OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
- Closing a partial agent stream releases the nested provider stream immediately.
  Task cancellation propagates without emitting a completion event. Cleanup
  failures are logged without replacing cancellation or generator closure.
  Visible partial text and reasoning are retained with a `[Response interrupted.]`
  marker; unfinished tool calls are not persisted as executable requests.

Code consuming `chat_completion_stream()` directly should handle exceptions.
Code consuming agent events should check for `ERROR`; `FINISHED` marks the end
of event delivery and does not by itself prove success.
Both `Agent.run()` and `Agent.continue_with_tool_results()` emit a final response
event with the finish reason and available usage. A `tool_calls` finish still
requires tool execution and continuation. Consumers that stop iterating early
should explicitly close their stream, for example with `contextlib.aclosing`.

The offline regression suites in `tests/providers/test_stream_safety.py` and
`tests/providers/test_anthropic_stream_safety.py` exercise these boundaries.
They do not certify live model quality or operating-system compatibility.

### Headless coding workflows

The `json`, `stream-json`, and `json-complete` CLI modes use the configured team
orchestrator, including `--agent` routing and bounded tool rounds. Tool results
include `tool_call_id`, `tool_name`, `result`, and `success`; `source_agent` identifies
the agent when available. Correlate requests and results by agent and call ID.
Intermediate provider finishes are suppressed. One terminal `finished` event
reflects the outer `agent_completed` event marked with `scope: "run"`; only
`completed` or `responded` is successful. A recovered specialist error does not
invalidate a later successful outer outcome. Missing or unsuccessful outer
completion produces an error event and nonzero exit. Cancellation propagates
without fabricating a successful terminal event.

Every JSON `finished` event includes top-level `"task_verified": false`. For
orchestrated runs its `data` contains the outer status, role, scope, execution
evidence, and `finish_reason` (`stop` or `error`). The `json-complete` output remains
an event array. Standalone evaluation runtimes without an orchestrator retain
the bounded single-agent loop and its provider-finish payload. This runtime field
does not inherit verification claims from event data: normal termination alone
cannot prove the requested task was accomplished. Orchestrator
`agent_completed` events carry their `task_verified` field and execution evidence
inside `data`. In the interactive UI, `responded` is neutral and `completed`
is displayed as “finished execution”; neither certifies the task outcome.

Queued tools are cancelled after an owning provider error, and interrupted
transcripts are balanced with failure results for outstanding requests. A cancelled
JSON consumer is not guaranteed further rendered events. Interactive stream handling likewise
stops queued work on an owning agent's error and records interrupted requests.
The loop respects configured tool confirmation policies. A successful test-tool
result is evidence about that command; the final model summary is not an independent
verification of the repository's correctness.

```python
from henchman.providers import DeepSeekProvider, Message

# Create provider
provider = DeepSeekProvider(
    api_key="your-key",
    model="deepseek-chat"
)

# Stream responses
async for chunk in provider.chat_completion_stream(
    messages=[Message(role="user", content="Hello!")],
):
    if chunk.content:
        print(chunk.content, end="")
```

## Provider Registry

Access providers programmatically:

```python
from henchman.providers import get_default_registry

registry = get_default_registry()

# Create provider by name
provider = registry.create(
    "deepseek",
    api_key="...",
    model="deepseek-chat"
)
```

## Switching Providers

### Via Environment Variable

```bash
HENCHMAN_PROVIDER=anthropic henchman
```

### Via Settings

```yaml
providers:
  default: anthropic
```

### At Runtime

Use the `/model` command (if implemented) or restart with different settings.
