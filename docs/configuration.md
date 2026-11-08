# Configuration

Interrupted tool effects use the separate `operations.persistence` setting
(`process` by default, optionally `durable`). See [operation recovery](operation-recovery.md)
for authority, storage and explicit user decisions; usage persistence is independent.

Henchman-AI uses hierarchical configuration with settings files and environment variables.

## Configuration Hierarchy

Settings are loaded in this order (later overrides earlier):

1. **Defaults** - Built-in default values
2. **User settings** - `~/.henchman/settings.yaml`
3. **Workspace settings** - `.henchman/settings.yaml` in current directory
4. **Environment variables** - `HENCHMAN_PROVIDER`, `HENCHMAN_MODEL`
5. **Transient API overrides** - validated values passed to `load_settings_snapshot` or `load_settings`

## Inspecting effective settings

`henchman config get KEY` (also `config view`) reports the effective value and
its `resolved_scope`: `default`, `global`, `project`, `file`, `environment`, or `session`.
`henchman config list` reports the same origin labels for its sorted leaf keys.
Each command reads values and origins from one settings snapshot. A higher
priority layer remains the origin even when it supplies the same value. Group-valued
`get`/`view` use actual maps; `mixed` is an origin label for contributions from
different sources, not a new writable `--scope`. Lists remain leaf-only, secrets
masked, and the canonical writes/legacy read fallback remains unchanged.

```bash
henchman config get providers.default
henchman config get providers.deepseek.model --scope project
henchman config list
```

The default merged scope includes environment overrides. Explicit `--scope global`
or `--scope project` reads only values persisted in that file scope, so an
`HENCHMAN_MODEL` override does not replace the explicitly requested file value.
Existing secret masking applies to displayed values.
Explicitly saved values remain in their selected scope even when they equal a
built-in default. For example, project `ui.output_mode: rich` overrides global
`quiet`; `config unset ui.output_mode --scope project` removes that override.
File-based settings imports preserve these explicit defaults too.

CLI runtime preparation loads settings once and uses that same settings object
to construct its provider. Direct TUI startup reuses supplied settings or loads
them once when omitted, including when a provider is supplied separately.
Invalid settings stop
startup before provider construction. The TUI retains its presentation and
environment fallbacks, but no longer substitutes default settings for an invalid
configuration.

Transient Python-API overrides apply after environment values and are not
persisted. Their snapshot origins use the `session` label:

```python
from henchman.config.settings import load_settings_snapshot

snapshot = load_settings_snapshot(overrides={"tools": {"shell_timeout": 30}})
assert snapshot.settings.tools.shell_timeout == 30
assert snapshot.origins["tools.shell_timeout"].scope == "session"
```

REPL and Textual retain the startup snapshot and record validated session changes
in that same state. `/config view KEY` and `/config get KEY` inspect live values
and origins; `/doctor` uses that state for configuration diagnostics. Explicit
`--scope global|project` still inspects the selected file. Editing a file or
environment variable does not silently change an already running session.
Standalone CLI config/doctor invocations read a fresh startup snapshot.

Provider/model switches update live selection and context origins after provider
preflight succeeds, preserving history and cached/future specialist settings.
Constructor-supplied model defaults retain default provenance; an explicitly
injected provider is a session choice. Resuming a conversation keeps the active
runtime settings. A fresh process uses its new startup snapshot rather than
replaying saved credentials or policy overrides.

`/theme` persists only `ui.theme` globally and records the active session change.
`/mcp logging` is transient. `/context status` shows live values, while context
setters persist only their named global keys for new sessions. These shortcuts
never save the entire merged environment/session configuration. No writable
session scope or settings service is introduced.

An existing file selected by `HENCHMAN_SETTINGS_PATH` replaces normal user/project
file discovery; environment provider/model overrides still apply afterward. If
the selected path does not exist, normal file discovery remains the fallback.
Programmatic overrides still apply after the selected file and environment layers.

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
  theme: dark
  output_style: verbose
  output_mode: rich
  reduced_motion: false
  detail_density: normal
  keyboard_mode: standard
  mouse_capture: true
  layout:
    compact_tables: false
```

`ui.output_style` accepts `verbose` (the default), `concise`, `minimal`, or
`json`. Blank values and unsupported names fail validation at `ui.output_style`;
replace an invalid existing value with one of these supported names. This uses
the same schema when loading settings and validating configuration writes.

### Terminal UI controls

The settings schema accepts these terminal UI controls. Runtime support is
described below; defaults preserve existing behavior:

| Key | Values | Purpose |
|----------|--------|---------|
| `ui.output_mode` | `rich` (default), `plain`, `quiet` | Classic REPL rendering mode; Textual consumer pending |
| `ui.reduced_motion` | `true`/`false` (default `false`) | Suppress non-essential animation and redraws |
| `ui.detail_density` | `compact`, `normal` (default), `detailed` | Density of presented information |
| `ui.keyboard_mode` | `standard` (default), `vim` | Keyboard behavior profile |
| `ui.mouse_capture` | `true` (default) / `false` | Enable application mouse reporting when the next Textual driver starts |
| `ui.layout.compact_tables` | `true`/`false` (default `false`) | Render denser tables and lists where supported |

All are validated with field attribution on error. `ui.mouse_capture` is applied
when the Textual driver starts. Set it to `false` to disable application mouse
reporting; an explicit Python `run`/`run_async` argument `mouse=False` also disables
it. Changes during a running TUI take effect on the next launch. Alt+Page Up/Down
reads transcript history and Alt+End returns to live output without replacing the
composer draft. Host selection, scrollback, clipboard and remote-terminal behavior
still depend on the terminal and require native testing.

`ui.reduced_motion: true` is also captured at Textual driver startup. Transitions
complete immediately, loading indicators remain static, and the composer and
focused dialog editors use steady cursors. Streaming, status changes, approval
prompts, cancellation and evidence freshness checks remain active. Changes take
effect on the next launch; `false` preserves the framework and caller defaults.
These rendered checks do not establish native assistive-technology support.

`ui.detail_density` is captured at the same startup boundary. `compact` reduces
transcript spacing while keeping tool summaries visible; `normal` preserves the
default layout; `detailed` starts new tool rows expanded to show existing bounded,
redacted evidence. Thinking stays collapsed. Manual expansion/collapse remains
your choice for that row through streaming and resizing. Changes require a new
TUI and do not alter evidence retention, approvals or execution.

`ui.output_mode` is captured when the classic REPL renderer starts. `plain`
produces an unstyled, append-only transcript with literal Markdown, code and
diffs, textual status labels, static progress and no bottom toolbar. `quiet`
also suppresses routine thinking, tool-success and delegation chatter. Answers,
explicit command output, permission/question prompts, warnings, failed or unknown
tool results and cancellation feedback stay visible. All modes retain the same
session evidence and execution policy. Changes take effect in a new REPL.
Transcript rendering adds no ANSI styling or animation; line editing and native
screen-reader behavior require separate qualification. JSON modes retain their
existing contracts, and explicit `--tui` still opens Textual.

`ui.layout.compact_tables` currently affects the classic REPL's `OutputRenderer`
tables. Its Textual consumer, Textual output-mode behavior and keyboard mode
remain pending in the UI workstream.

Unknown fields in typed groups are rejected rather than silently ignored. Remove
obsolete or misspelled fields from existing files; entries inside the declared
provider options, UI keybindings, and style dictionaries remain customizable.
Remove previously ignored keys including `tools.auto_approve`,
`session.auto_save` and `session.sessions_dir` from existing files.

## Repository search settings

`rag.top_k` accepts integers from 1 through 20; existing values above 20 must be
reduced before startup. `rag.chunk_size` must stay positive and
`rag.chunk_overlap` must be nonnegative and smaller than the chunk size.

RAG caches now use a versioned identity derived from the resolved worktree path.
Clones and linked worktrees have separate indexes even when they share a remote;
commits and remote changes keep the same workspace cache. Old remote/revision
and project-local caches are left untouched and are not imported automatically.
Use `/rag reindex` to populate current source provenance. Cache manifests are
limited to 4 MiB and replaced atomically. Standalone `GitFileIndexer` uses the
same canonical cache by default; an explicit manifest path remains the caller's
choice.

The manifest binds the backing collection, index generation and embedding model.
Indexing marks that generation unavailable before changing stored chunks and
publishes readiness only after success. Queries reject missing collections,
interrupted indexing, changed generations and incompatible embedding models;
they recheck readiness before returning evidence. Inherited Git repository/index
overrides cannot replace the bound worktree's provenance.

Queries require an explicitly bound workspace and return
[bounded current-file evidence](tools.md#rag_search), including diagnostics for
stale or unsupported sources. This does not establish full-index enumeration
bounds or native responsiveness of synchronous embedding/store/filesystem work.

## Session project boundaries

Session selection uses the resolved working-directory identity. `resume`,
`session switch/delete`, `/chat resume`, and `/session` export, branch, merge and
template operations enforce the current project for tags, full IDs and prefixes.
A stale current-session pointer cannot activate another project's transcript or
memory; context lookup falls back only to sessions in the current project.
Prefix collisions in another project do not make a local selector ambiguous.
Existing templates are scoped using the project identity embedded in their saved
session, so they need no migration to acquire this check.

`session list --all-projects` remains an explicit administrative metadata listing;
it does not authorize reading or modifying those sessions from this project.
Run the command from the owning directory to access a session there. Explicit
file import/export is still the way to transfer a user-managed copy. The `/session
import` command creates a new ID in the destination project and leaves the source
session unchanged. Low-level Python session APIs accept `project_hash=` for scoped access and retain unscoped
administrative access when it is omitted. These are application access checks,
not OS isolation: processes with filesystem access can still read saved files.
Restricted shell/network enforcement remains tracked separately under issue #20.

## Session evidence redaction

Session JSON, Markdown exports, new playback recordings and saved templates use
the shared `EvidenceRedactor` policy. It masks known credential values with
`[REDACTED]`, including their JSON-escaped forms, standard authentication header
lines, and values in explicitly credential-bearing fields such as `api_key`,
`api_keys`, `password`, `authorization` and names ending in `_secret` or `_token`.
Token counts and ordinary dictionary `key` fields are not credential markers.
The same policy covers summaries, compaction-retained messages, stored memories
and nested session metadata. Template names, descriptions and parameters are
included; backups are redacted before rotation or retention during recovery.
Fixed field names, generated identities, timestamps, correlation IDs, provenance
digests, roles and lifecycle flags retain their protocol meaning. Short credential
values therefore cannot rename session keys or change the project identity.
Memory text, kinds and sources remain evidence fields and are redacted.
Unexpected structured objects in identity fields fail validation before saving.

Credential-named environment variables are discovered automatically. REPL and
Textual initialization also register credentials from effective settings and the
active provider; provider switches retain old keys in the runtime policy and
register the replacement key. `${ENV_VAR}` references in credential settings
track changes to the referenced variable. Embedded Python callers can pass an
`EvidenceRedactor` to `SessionManager(evidence_redactor=...)` to register other
known values. This policy does not discover arbitrary secrets or every possible
encoding. Revocation at the provider remains a separate action.

Redaction produces an independent evidence copy: it does not change live provider
credentials, tool arguments or in-memory messages used for execution. A resumed
session contains the redacted evidence; it cannot restore removed secret values.
Reading a legacy file does not rewrite it; its next save sanitizes the current
and retained prior copy. Previously exported files and recordings are not scanned
or rewritten automatically.
Both valid disk generations supply marked credentials before a save, including a
credential present only in the old backup. Literal redaction-marker text inside a
credential and whitespace in recognized Bearer headers do not exempt its echoes.

Headless `json`, `stream-json` and `json-complete` output shares the session's
credential registry. Content and reasoning have separate stream buffers for each
agent, so a known value split across chunks remains private. Marked tool arguments
register their credentials before display; execution still receives the original
arguments. Tool previews are derived from redacted full results. Validated
completion controls and generated correlation IDs retain their protocol meaning.
JSON consumers must concatenate content chunks rather than rely on chunk sizes:
an ambiguous suffix can be delayed until a later chunk or the terminal event.
Successful completion resolves unmatched prefixes as ordinary text; failure or
cancellation masks unresolved credential prefixes. Buffered output precedes the
terminal event, and cancellation still propagates without claiming completion.
An unfinished authentication-header prefix over 1,024 characters is conservatively
masked through its next newline to bound retained whitespace. Complete JSON
collects marked fields before projection; streaming cannot retract text emitted
before a value was first identified as sensitive.

REPL agent streams and Textual event messages now use the same per-agent
projection, including tool arguments, results, completion and cancellation.
Tool approvals display copies; the original arguments and user answers still
reach execution. Textual command output redacts strings before Rich markup and
line wrapping, retaining buffers across partial writes and ANSI controls.
Direct Textual input echoes, public messages, context-file displays, status/search
labels, context-tree labels, workspace panels and bridge descriptions use the
same policy; raw lookup IDs and selected paths still reach their original services.
Both REPL and Textual redact new command-history
entries before writing. Live editable input and the underlying context file remain
unchanged; old command histories are not rewritten. Context-file previews redact
the complete content before truncation so a cut cannot expose part of a credential.
Interactive worker, tool-cleanup and MCP failures format diagnostic tracebacks
without locals, then redact them before passing text to the CLI logger or renderer.
Plugin loading, slash-command errors, provider setup and session-resume failures
also project their diagnostics before output. Textual export contents and success
or failure messages use the active runtime policy.
Exception chains, notes and stack locations remain available; raw exceptions are
not attached to those log records. Non-JSON objects such as paths and exceptions
are projected before display conversion.

Metric storage projects known credentials and marked metadata before SQLite
insertion without changing the caller's metric object. Reads project legacy rows
under the current policy without rewriting old database bytes. JSON/CSV/Prometheus
exports, export filters, session summaries and exporter failure diagnostics use
the same policy. Fixed schema keys, correlation identities and numeric measurements
retain their meaning. Malformed stored metadata fails explicitly before export.
Python embedders can pass the runtime's `EvidenceRedactor` to `MetricsStorage`;
its exporter inherits that object, including later rotations. Defaults discover
credential-named environment values. Existing database files and earlier exports
are not retroactively sanitized, and endpoint authorization is separate from
evidence redaction. See the [metrics API](api.md#metrics).

This work does not establish full privacy or OS isolation. Remaining subsystem and
third-party logging, handoffs and additional command outputs require the work and
qualification in issue #20. Configuration exports and restricted tool access have
their separate contracts below.

## Restricted tool access

`tools.auto_approve_read: false` requires confirmation even for effective read-only
operations in preset auto-approval lists. Parent requirements apply to scoped
registries; explicit user approval and unchanged session grants still work.
`tools.sandbox: docker` is rejected at runtime setup because this build has no
enforced Docker backend. The default `none` remains supported.

Trusted settings can restrict filesystem operations and disable network tools:

```yaml
tools:
  filesystem_read_roots: ["."]
  filesystem_write_roots: ["."]
  network_access: disabled
```

Roots must already exist. Relative roots bind to the runtime project directory;
absolute roots are also supported. `null` leaves that operation unrestricted;
`[]` denies it. Configure both read and write roots to confine both operations.
Scoped registries intersect their restrictions with all parent restrictions.
Replacing the bound project or root requires trusted runtime rebinding.

With any restriction enabled, only the qualified builtin `read_file`,
`write_file` and `web_fetch` implementations execute when their required backend
capabilities are available. Other tools, including shell,
Python, MCP, search and delegation tools, fail explicitly even when trusted or
auto-approved. Restricted writes bypass automatic Python formatting. Reads and
writes use directory-relative handles, reject symlink substitution and hardlink
aliases, and check targets when opening them. Platforms without the required
directory-handle primitives, including Windows, reject restricted file operations.

This is mediated tool access, not OS isolation against hostile host processes or
mount changes. `network_access: disabled` applies to tool dispatch, not model SDK
traffic. Other network tools and OS enforcement remain separate work.

### Exact network host restrictions

```yaml
tools:
  network_access: unrestricted
  network_allowed_hosts: ["docs.example.com", "api.example.com"]
```

`network_allowed_hosts: null` adds no host filter; `[]` denies all destinations.
The list accepts at most 128 distinct exact DNS/IDNA names or canonical IP
addresses. Names normalize case and a single terminal DNS dot; duplicate
normalized names, wildcard patterns, URLs, ports, userinfo, zones and ambiguous
numeric aliases are rejected. A DNS name does not grant its subdomains, and an
allowed IP address does not grant names that resolve to it. Parent policies
intersect, and `network_access: disabled` takes precedence. Allowlisting never
permits private, loopback or special IP destinations.

Restricted `web_fetch` requires aiohttp's public `socket_factory` capability
(available in 3.12+); older versions reject restricted fetch before DNS. The
qualified implementation rechecks authority before/after DNS, before each numeric
connection attempt, before sending headers and after awaited responses. Redirects
receive their own checked connection. Live registry checks include project,
ancestor policy, approval grants and the registered implementation. Revoked
authorization stays revoked in inherited task contexts after the call finishes.

The existing unrestricted aiohttp 3.9 path remains supported. It can block header
dispatch after revocation but cannot prevent every already scheduled numeric TCP
attempt. Revocation cannot undo bytes already sent. Trusted embedders using
`use_access_policies` directly receive immutable policy checks; live registry
revocation applies to registry-dispatched calls. This boundary does not filter
provider traffic or qualify MCP, shell, Python, search or custom network tools.

## Required project checks

Set `verification.checks` in `.henchman/settings.yaml` to include required checks
in every newly created verification plan:

```yaml
verification:
  checks:
    - kind: pytest
      path: tests/test_total.py
      inputs: [src/total.py, tests/test_total.py, pyproject.toml]
      requirement_ids: [REQ-total]
    - kind: command
      argv: [python, -m, ruff, check, src/total.py]
      inputs: [src/total.py, pyproject.toml]
      timeout: 60
```

The default is an empty list. The normal settings precedence applies; bound tools
use the active runtime Settings snapshot, while a directly constructed service
loads project settings. Apply or reload changed settings in an active session.
Commands are explicit argv arrays and run only through the existing `verify`
action and execution approval. No commands are guessed from project files.

Configured checks are combined with caller checks and exact duplicates are
removed, with a combined maximum of 20. The existing
[check contract and limits](tools.md#declared-input-freshness) apply, including
declared files for current command/pytest evidence. Baselines are captured by the
service; config cannot supply them. Changing or removing configured checks makes
earlier bound evidence stale. Newly required checks leave older unbound plans
unverified. Create a new plan and review its checks before verifying again.

## Usage limits and explicit prices

`usage.limits` accepts `max_requests`, `max_tokens`, `max_seconds`, `max_cost`
and `currency` (default `USD`). Omitted limits are unlimited; zero is an explicit
limit. Counts must be nonnegative integers, time must be finite and nonnegative,
and money is stored as an exact decimal string.

`usage.prices` is a list of entries keyed by exact `provider` configuration name
and effective `model`. Each entry can set `input_per_1k`, `output_per_1k`,
`cache_read_per_1k`, `cache_write_per_1k`, `currency`, `source` and `as_of`
(`YYYY-MM-DD`). Rates use decimal strings. Duplicate provider/model pairs are
rejected; missing entries or applicable rates remain unknown. No wildcard price,
implicit local-free rate or currency conversion applies. Accounting configuration
is separate from `providers.*` and is never sent as SDK request options.

Public orchestrator runs and CLI turns capture these settings into one shared
task budget for the primary agent, delegates, retries and summary calls. Supported
providers account even without limits. Uninstrumented provider extensions remain
usable only without configured limits or prices; bounded runs reject them before
dispatch. Context-window capacity and task-token limits are separate controls.

`usage.persistence` defaults to `process`: accounting lasts only for the current
process. `durable` enables authoritative SQLite accounting for CLI sessions in
the session data directory's sibling `ops.db` (normally `~/.henchman/ops.db`).
Goal continuation, pause/resume, interruptions and unfinished background work
retain the same budget. Successful ordinary tasks close their run. Explicit user
`/goal set`, a shorthand objective replacement and `/goal clear` authorize a new task;
saved goal metadata cannot reset consumed accounting. A process exit between
saving a goal change and applying that transition requires repeating the user
action. Missing or conflicting accounting state fails before dispatch.

`/usage` inspects the selected task's request/token/time/money limits, retained
uncertain usage, per-agent requests and price provenance. Headless terminal
events include an aggregate `budget` with exact decimal strings; unknown amounts
stay null and currencies remain separate. A time-capped durable run cannot
resume dispatch after its original monotonic clock domain is lost.

See [run accounting](providers.md#automatic-task-accounting) for lifecycle and
billing limits. The standalone HTTP API currently supports process accounting
only and rejects `durable` before dispatch. Explicit control import/export can
transfer usage configuration as described below; it never transfers accounting state.

## Local import/export sync

`henchman config import` / `henchman config export` move a narrow **sync payload**
between local files. By default it contains only `ui.output_style`, `ui.theme`,
`ui.keybindings`, `ui.output_mode`, `ui.reduced_motion`, `ui.detail_density`,
`ui.keyboard_mode`, `ui.mouse_capture` and `ui.layout`.

To transfer nonsecret operational controls, use explicit flags:

```bash
henchman config export controls.yaml --scope project --include-controls
henchman config import controls.yaml --scope project --accept-control-changes
```

`--include-controls` adds `usage.limits`, `usage.prices`, `usage.persistence`,
`operations.persistence` and `verification.checks`. Importing any of these groups
requires `--accept-control-changes`, including tightening changes. This records
explicit intent to replace settings that may remove a limit, lower a price,
select process persistence or remove required checks. A flag stored inside the
payload cannot supply that acceptance.

- Supplied mapping leaves merge with the selected persisted scope; omitted leaves
  remain unchanged. Supplied price/check lists replace the entire old list.
  Explicit zero, null, default values and empty lists retain their meanings.
  Decimal values remain exact, although their string spelling may canonicalize.
- Typed validation checks the complete candidate before one canonical write.
  Unsupported groups and fields reject the whole import without partial UI changes.
  Providers, credentials, tools, MCP and agents are outside the transfer contract.
- Writes target `.henchman` for the chosen scope; legacy casing is a read-only
  fallback. Partial imports do not persist inherited environment/session values.
- Known credential echoes in freeform UI values are redacted on export. Operational
  values require lossless transfer: if credential projection would alter a model
  name, price source, check argument, path, text or requirement identifier, the
  entire transfer is refused. No redacted placeholder becomes executable input.
  This does not detect arbitrary unknown secrets.
- Transfers contain configuration only. They cannot import grants, verification
  observations, run budgets already consumed, or recovery journal authority.
  They do not reload a held runtime; normal startup/reload rules still apply.
  Text and JSON command responses use the existing credential projection.

There is no backend or cloud sync. The payload is for explicit file-based transfer
between machines or teammates. New UI keys and operational groups require
Henchman v0.4.2 or newer; older binaries reject unsupported keys rather than
partially applying them. The repository API uses keyword-only
`export_settings(..., include_controls=True)` and
`import_settings(..., accept_control_changes=True)` with defaults of `False`.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HENCHMAN_SETTINGS_PATH` | Select an existing YAML/JSON settings file |
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

With `context.auto_compact: true` (the default), the agent removes complete older
conversation turns until the request estimate fits. With `false`, it retains all
history and suppresses automatic summaries, ignoring the softer compaction
threshold while still enforcing the hard capacity before dispatch. Primary,
specialist, dynamic child and HTTP API agents use this setting. When a full tool catalog still cannot fit and bound `tool_search` is
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
Standalone agents with `context_window=None` retain legacy compaction behavior
when automatic compaction is enabled; disabling it does not introduce an explicit
hard capacity where none was configured. Intelligent-context strategy settings
apply to the legacy compactor, not the deterministic explicit-capacity path.

Tokenizers and server chat templates differ, so these are estimates, not an exact
server guarantee; opaque provider extensions are not fully accounted for. Even
with a smaller tool catalog, large prompts, results or output caps may require a
larger model-supported capacity. This setting does not resize a local server's
context window or establish a whole-application RAM bound.

For detailed information on intelligent context management, see the [Intelligent Context Management](intelligent-context-management.md) documentation.

## Context Files (HENCHMAN.md and AGENTS.md)

Place instruction files in your project to provide context:

- **Global**: `~/.henchman/<filename>` for any supported filename (defaults include `~/.henchman/HENCHMAN.md` and `~/.henchman/AGENTS.md`)
- **Project**: `./HENCHMAN.md`, `./AGENTS.md`, or the other supported filenames (in project root)
- **Subdirectories**: Optional, for specific context

Default discovery filenames, in priority order: `HENCHMAN.md`, `.henchman/HENCHMAN.md`, `.github/copilot-instructions.md`, `.gemini/GEMINI.md`, `AGENTS.md`. `AGENTS.md` is the portable cross-tool convention; Henchman-specific `HENCHMAN.md` remains the primary, first-loaded file. Existing custom `filenames=` settings keep their configured priority and work unchanged.

**Deterministic precedence:**

1. Explicit user task constraints (your messages and approvals) remain authoritative over any instruction file.
2. Global files from `~/.henchman/` load first, in filename priority order.
3. Repository instructions load from the Git root down to the current directory; inside one directory, files follow filename priority order.
4. Deeper-scope instructions render after broader-scope instructions, so the most specific guidance applies by position. Sibling directories never leak into each other.
5. Same-scope ties break by filename priority: `HENCHMAN.md` before `.henchman/HENCHMAN.md` before `.github/copilot-instructions.md` before `.gemini/GEMINI.md` before `AGENTS.md`.

**Boundaries and safety:**

- Inside a Git repository, context files are discovered from the repository root down to the current directory. Optional immediate-subdirectory discovery is available only when a Git root establishes the project boundary. Outside Git, Henchman reads project context only from the current working directory: it does not walk into subdirectories or inherit instruction files from parent directories. This boundary prevents unrelated parent context from being pulled into a non-repository session.
- The global file `~/.henchman/HENCHMAN.md` is handled separately and may still be loaded for either kind of session.
- Instruction files are deduplicated by physical path (aliases and symlinks resolve once). Sources resolving outside the global home or repository boundary are rejected before any read.
- Instruction text is data, never authorization: it cannot widen tool scope, approvals, plan-mode policy or access controls, however it is worded.

**Provenance and diagnostics:**

- `ContextLoader.load_snapshot()` returns an immutable `ContextSnapshot` with each source's original path, applicable scope, kind (`global`/`repository`), discovery order, captured content, original size and truncation state.
- `snapshot.diagnostics()` reports per-source sizes and truncation; `snapshot.truncated_sources` lists truncated sources.
- Pass `max_source_chars=N` to `ContextLoader` to bound per-source capture. Truncated sources carry an explicit `[truncated: showing N of M characters]` marker and report the original size in diagnostics.
- `ContextLoader.load_for_path(target)` re-resolves instructions for a different subtree; targets outside the project boundary are rejected before any instruction file is read. Use it when acting on a different part of the repository.
- Sessions attached through the CLI record instruction provenance in the session's `export_metadata["instruction_sources"]`: paths, scopes, kinds, order, sizes, truncation state and SHA-256 digests — never instruction text. Superseded records move to a bounded `instruction_sources_history` (last five) so resumed sessions keep earlier evidence. Delegated agents (dynamic background subagents and team/legacy delegation inputs) receive a bounded "Project instruction provenance" appendix listing the same sources, restating that instruction text cannot widen tool policy or approvals.

The provenance record is content-free by design, so resuming a session or auditing a delegation shows exactly which instruction files were in force without duplicating their text.

**Runtime refresh:**

Each primary or delegated agent refreshes its active snapshot before a provider
request. Supported file tools refresh their structured targets, including generated
test destinations, import-graph scan directories and all files in a parsed patch.
Directory formatting uses the formatter's bounded file resolver to collect affected
instruction scopes. A newly applicable or changed snapshot defers a mutation until
a subsequent model request has received it. A read followed by a write in the same
tool batch cannot skip that review. Fresh scoped messages replace earlier sibling
messages while preserving custom filenames, capture limits and conflict precedence.

Checks repeat after awaited approval and formatter waits, immediately before
dispatch. An instruction-only deferral retains the existing approval grant, while
ordinary Plan Mode and tool policies remain binding. When runtime instructions are
attached, `lint_check(path=<directory>, fix=True)` requires explicit file targets:
inspect without fixing, then fix named files. This avoids assuming a linter's
configured recursive scope matches the formatter's file selection.

Shell/Python execution refreshes its declared `cwd`; paths embedded in arbitrary
code and unknown plugin/MCP parameter conventions are not inferred. Outside-boundary
instructions are never read, and instruction discovery does not authorize access.
Session provenance records the latest active scopes, including after resume and
after a delegated agent visits another subtree. Delegation appendices include
actual digests, original/captured sizes and truncation markers.

## MCP Server Configuration

MCP SDK 2.3.0 supports configured stdio and unauthenticated Streamable HTTP; see
[transport options and limits](mcp.md#configuration-options) and the
[tested protocol profiles](standards.md#implemented-compatibility-foundation-v042-work).
Verbose logging changes filtering, not credential redaction. Configured
credential-named environment values are masked in process stderr and SDK
malformed-stdout diagnostics. Descendants retaining stderr cannot indefinitely
block diagnostic cleanup; this does not provide process isolation.

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
