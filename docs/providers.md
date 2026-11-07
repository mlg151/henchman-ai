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
It also reports the actual recorded setting origin. `/config get
providers.default`, `/config get context.max_tokens` and `/doctor` inspect the
same active snapshot in REPL and Textual.
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

### Usage and cost provenance

`StreamChunk.usage` is a cumulative snapshot for one provider request, not a
per-chunk increment or a complete run total. `usage_source` distinguishes
`reported`, `estimated`, and `unknown`. Missing counts remain absent; explicit
zero counts remain zero. Compatible adapters merge partial and trailing snapshots.
Anthropic input counts include ordinary input plus cache reads and writes;
its output count is cumulative. `cached_tokens` and `cache_creation_tokens` are
subsets of `prompt_tokens`; `reasoning_tokens` is a subset of `completion_tokens`.
Do not add those subsets to the totals again.

Compatible requests ask for streaming usage by default. For servers that reject
the optional field, configure `providers.<name>.stream_options: null` to omit it.
An explicit `{"include_usage": false}` is also preserved. No automatic retry with
different request options occurs. These fields are supported by the documented
[OpenAI](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events),
[DeepSeek](https://api-docs.deepseek.com/api/create-chat-completion/),
[OpenRouter](https://openrouter.ai/docs/client-sdks/python/api-reference/chat), and
[Ollama](https://docs.ollama.com/api/openai-compatibility) compatible interfaces.

The Python `UsageReport` and `TokenPricing` records preserve nullable counts and
explicit input/output/cache rates, currency, price source and date.
`CostTrackingService.record_usage()` returns `float | None`: absent pricing stays
unknown, a configured zero rate is valid, and configured estimates remain separate
from explicitly supplied provider billing. Summaries keep currencies separate and
mark totals incomplete when any recorded cost is unknown. Historical synthetic
cost records lack trustworthy provenance and are treated as unknown.

Agent completion events retain `usage_source` whenever they include counts, so
an estimate cannot become reported usage by passing through the agent loop.
Configured providers also retain their exact configuration identity for price
lookup; aliases sharing one adapter do not silently share a price catalog.
Shared run aggregation and admission are described below; final qualification
remains tracked under [#24](https://github.com/mlg151/henchman-ai/issues/24).

### Explicit run budget scopes

`henchman.core.run_budget.RunBudgetLedger` is an in-memory accounting component.
Integrators
reserve a `RequestEstimate`, claim it with `start(request_id)` immediately before
dispatch, and reconcile cumulative `UsageReport` observations. Retries need new
request IDs under the same operation ID. Atomic admission checks request, token,
elapsed-time and optional monetary limits across callers. Duplicate reservation
IDs cannot claim a second dispatch. Cancellation releases an unstarted hold;
started attempts keep uncertain usage reserved until a final report resolves it.

Strict monetary admission requires known applicable rates in one currency.
Configured zero rates remain valid; configured estimates and reported billing
stay separate. Missing or inconsistent final usage, newly applicable unpriced
cache usage and unexpected currencies cannot release money for additional calls.
Cost arithmetic and aggregation preserve exact finite decimal values regardless
of the caller's decimal precision. Snapshots label accounting as `process` lifetime.
The ledger alone does not persist or restore reservations or guarantee the bill
for an already-started remote request. A durable adapter is available below.
`BudgetExceeded` propagates through agent preparation, streaming and legacy
delegation instead of becoming a recoverable provider error or delegation retry.

`henchman.providers.runtime_budget.use_run_budget(RunBudgetScope(...))` activates
accounting for compatible and Anthropic provider streams consumed inside its
scope. Use `run_budget_limits(settings)` and `model_pricing(settings, provider=...,
model=...)` from `henchman.config.usage` to bind the typed configuration. Child
tasks inherit the current scope; `current_run_budget()` captures it for later
activation, and `scope.for_agent(id)` attributes requests to an actor without
creating another ledger.

Active scopes snapshot request parameters and prices before any awaited capacity
check. They enforce the reserved output cap (default 4,096 only when absent),
disable hidden SDK retries, and count actual dispatches. Compatible requests make
one attempt; Anthropic's explicit rate-limit retries each claim another reservation
under the same operation. Usage is settled only after normal stream exhaustion
with a terminal reported snapshot. Cancellation and incomplete usage keep holds.
Summary calls drain trailing usage and cannot swallow budget exhaustion. Supported
adapters advertise `supports_run_budget`; uninstrumented custom providers are not
automatically accounted by this explicit scope. Requests outside a scope retain
their existing behavior. Public orchestrator and CLI entrypoints create scopes
automatically as described below.

### Durable accounting storage

`RunBudgetStore(path)` from `henchman.ops.run_budget_store` creates explicitly
owned runs with the same reservation/claim/reconciliation interface. Each change
loads authoritative state under a SQLite write transaction; dispatch permission
is returned only after its start claim commits. A crash after that commit retains
the consumed request and uncertain usage even if HTTP never started. Late final
usage can reconcile it; a retry requires a new attempt ID.

Prices, monetary limits and billing retain exact decimal strings. Records store
identities and accounting observations, never prompts, tool arguments or headers.
Session bindings commit with run creation, so an older transcript backup cannot
refund a known run. Session references are advisory; missing/corrupt stores,
wrong identities and unsupported schemas fail closed instead of creating a fresh
balance. Closing a run retains its history and uncertain consumption.

Snapshots label this adapter's lifetime `durable`. Time-capped runs can dispatch
only while their original monotonic clock domain can be verified: native clocks
resume within the original process, and injected clocks within their owning
store instance. Other processes can reconcile/inspect those runs, but cannot
restart their timer. Without a time cap, independent processes share the same
atomic request/token/money admission state.

### Automatic task accounting

`Orchestrator.run()` and `run_direct()` capture one shared scope for their primary
agent, delegates, explicit retries and compaction summaries. An enclosing scope
is retained; a supplied different ledger cannot replace it. Agent tool-result
continuations retain the original scope even when consumed outside the caller's
context. Budget control failures propagate through background workers and stop
further primary/delegate dispatch instead of becoming ordinary retry messages.

CLI, REPL and Textual bind scopes to their selected session. `usage.persistence`
selects process or durable accounting; see [configuration](configuration.md#usage-limits-and-explicit-prices)
for task boundaries and explicit goal transitions. Changing settings during an
active task does not refund consumption or replace its original limits. Within
one runtime, the run retains its captured price catalog for the actual
provider/model. After runtime recreation, future attempts use the current exact
provider/model catalog; previously recorded prices and consumed amounts remain
unchanged. A new currency must remain compatible with the original money cap.

`/usage` presents aggregate consumption, remaining limits and stop reasons, with
estimated cost, held estimates and reported billing labeled separately. Unknown
amounts are unavailable rather than zero. Headless completion/failure evidence
includes the shared aggregate, with decimal amounts serialized as strings.
These are admission bounds and accounting observations: already-started remote
requests can incur billing that differs from estimates, especially after a
disconnect or cancellation. No automatic paid-model fallback occurs.

The [standalone HTTP API](api.md#http-chat-and-task-usage) uses isolated process
runs and caller-owned continuation IDs. Durable API session binding is not yet
implemented; requesting it fails before model dispatch.

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
