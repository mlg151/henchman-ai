# Managed local runtime: reuse map

Static inspection on 2026-10-14. Target: 16 GB whole-system RAM, CPU operation,
optional GPU acceleration. This is an extension-point report, **not a selected
default, a model-quality result, or evidence of laptop memory fit**. No production
code changed, downloads performed, or model processes started for this task.
Pinned candidate/runtime metadata and prior failed probes are in
[the research report](2026-10-14-local-model-16gb.md). Model selection remains
dependent on the separate live probes and unchanged behavioral acceptance checks.

## Existing mechanisms to reuse

Paths below are repository-relative; symbols are more stable than line numbers in
this active worktree.

| Concern | Existing source and extension point | What it supplies / current limit |
|---|---|---|
| Compatible transport | `src/henchman/providers/openai_compat.py`, `OpenAICompatibleProvider`, `_build_request_params` | Native streamed tool calls over an OpenAI-compatible endpoint. Request defaults support sampling and `extra_body`; per-call options override defaults. Reuse for llama-server; no new provider protocol required. |
| Provider construction | `src/henchman/providers/factory.py`, `create_configured_provider` | Shared settings/model/key resolution used by CLI and specialists. Explicitly configuration-only: no network probe or settings mutation. Keep download/start/readiness outside this factory. |
| Existing local provider | `src/henchman/providers/ollama.py`, `OllamaProvider` | Existing-server client, `OLLAMA_HOST`, `/v1` normalization, dummy key. `list_models` returns a static example catalog, not installed model discovery. No pull, process startup, readiness or shutdown. |
| Model UI | `src/henchman/cli/commands/model.py`, `ModelCommand`, `_set_provider` | `/model list` and `/model set` enumerate/select providers and construct a connection; selection explicitly says connection was not tested. Extend this surface if managed acquire/status/select becomes needed, rather than creating a second model command system. |
| Runtime switching | `src/henchman/cli/provider_switch.py`, `switch_runtime_provider` | Updates pool, active agent, orchestrator, UI handlers and core context while preserving history/session/tools. Stage a healthy replacement before invoking this path. |
| Team reuse | `src/henchman/agents/pool.py`, `_resolve_provider`, `_provider_with_model`, `set_default_provider`, `get_agent` | Reuses the default provider, preserves explicit role overrides, propagates switches to cached agents. One application-owned local server should serve these clients; avoid one server per specialist. |
| Settings | `src/henchman/config/schema.py`, `ProviderSettings`; `config/settings.py`; `config/repository.py`, `SettingsRepository` | Existing provider dictionaries, global/project precedence, environment selection, validated get/set/unset and file import/export. Preserve explicit user choices and canonical `.henchman`. Runtime executable/artifact/backend options need their own validated fields rather than leaking through provider request defaults. |
| Shared construction | `src/henchman/cli/app.py`, `RuntimeContext`, `_prepare_runtime_context`, `_run_interactive`, `_run_textual_tui`, `_run_headless`; `cli/core_init.py`, `CoreContext`, `create_core_context` | Existing application/session boundaries where a managed-runtime handle can be prepared and retained. Constructors currently receive an already constructed provider. They do not own a general asynchronous resource lifecycle. |
| Native cache lock | `src/henchman/utils/file_lock.py`, `FileLock` | Cross-platform lock without importing RAG/Chroma. Reuse for artifact publication coordination; avoid holding a blocking lock acquisition on the event loop. |

Searches for `LocalModelManager`, model-manager classes and model pull/download
operations found no existing managed model service in production code. Existing
Ollama install/pull guidance is manual documentation. A narrow acquisition and
process owner would fill a real gap; a parallel provider/agent/config framework
would duplicate working mechanisms.

## Acquisition and lifecycle boundaries

`extensions/plugin_installer.py::_download_archive` validates its URL but calls
`await response.read()` before writing the archive. Reusing it unchanged for a
4.28 GB GGUF adds a multi-gigabyte allocation. Its archive extractor is also an
extension installer, not a pinned runtime artifact validator. Use bounded chunks,
incremental SHA-256 and byte counts, a temporary file, and atomic publication only
after verification. Reuse the existing lock and path conventions. Preserve pinned
runtime/model provenance and licenses from the research report. Keep weight files
in a user cache, not in each source checkout; current config paths do not provide
a dedicated model-cache resolver.

`advanced/tasks.py::TaskService` already owns subprocess handles, log readers and
terminate/kill/wait logic, but represents user background jobs with project-local
status/log files. It has no model readiness, artifact validation, backend selection,
server lease or bounded log retention. Its argv coercion strips argument strings,
so it is not an exact transparent model launcher. Do not pretend that starting a
background task makes a model ready.

`tools/subprocess_utils.py::run_bounded_subprocess` provides bounded capture and
cancellation cleanup for finite commands; it waits for completion. It cannot be
used unchanged as a persistent model server supervisor. Reuse the cleanup pattern
or extract a small shared helper only when implementation requires it. The MCP
client's `AsyncExitStack` is another ownership precedent, not a model transport.

A small application-owned asynchronous handle should start an argv-only server,
drain bounded diagnostics, wait for readiness with a deadline, and clean up its
own child on startup failure, cancellation, normal exit and replacement. External
Ollama/OpenAI-compatible servers remain externally owned. Attach cleanup around
all interactive/TUI/headless execution paths, not just one renderer; current
`ModelProvider` has no close contract, and closing a streamed response is not
equivalent to closing the client or terminating a server. Shared ownership matters
when multiple cached agents use the same provider. Keep CPU and optional
CUDA/Metal/Vulkan choices in the same pinned runtime profile with explicit backend
status; unsupported assets/prerequisites must be reported, not treated as a
successful acceleration selection.

## Budget and credential gaps that affect a local profile

- `agents/orchestrator_init.py::_create_pool` reads `settings.context` but forwards
  only intelligent-context/compression knobs. `agents/pool.py::ContextConfig` and
  `get_agent` omit `max_tokens` and `compaction_threshold`. Merely saving
  `context.max_tokens` does **not** currently bound team agents. Propagate an
  effective runtime budget through this existing path, including cached agents
  after switching.
- `core/agent.py::_resolve_max_tokens` uses an explicit agent budget or 85% of a
  model lookup; `utils/tokens.py` defaults unknown models to 8000 tokens and uses
  approximate tokenization. Align the local profile's actual server context with
  prompt, tool-schema and response headroom. Output `max_tokens` in provider
  request defaults is a separate control. The proposed 4096/3072/512 probe values
  are experiment settings, not proof that every production tool schema fits.
- `config/schema.py::RagSettings` enables RAG by default. In a Git repository,
  `cli/app.py::_setup_repl_rag(..., index=False)` still constructs `RagSystem`,
  its FastEmbed provider and vector store. Skipping indexing does not eliminate
  those resources. Whole-app 16 GB evaluation must include RAG, OS/editor and
  tool/test children, or clearly state the explicitly selected reduced profile.
- `providers/factory.py::resolve_api_key` falls back to provider/generic
  environment credentials when configured key is empty. A managed loopback
  profile should use a dedicated local credential, not inherit
  `HENCHMAN_API_KEY` accidentally. The existing Ollama adapter already uses its
  own literal key.

## Smallest evidence-led implementation sequence

1. Retain live probe results before choosing any included model. Keep the current
   provider factory/transport and native structured-call contract.
2. Add a pinned artifact/profile representation and bounded verified acquisition
   at the existing settings/cache boundary; test interrupted/corrupt downloads,
   concurrent publication, and platform asset selection without real weights.
3. Add one owned-server lifetime around existing application entrypoints. Test
   readiness failure, cancellation, bounded logs, cleanup, external-server
   non-ownership and reuse across specialists using a small fake subprocess.
4. Thread the effective context budget through pool creation and provider
   switching. Test new/cached agents, explicit role overrides and separate output
   caps before exposing a managed profile through the existing model command.
5. Measure real coding-loop correctness and total resource use on the target
   hardware; an optional RTX 3090 host experiment is not 16 GB laptop acceptance.

Existing focused regression anchors: `tests/providers/test_factory.py`,
`tests/providers/test_ollama.py`, `tests/agents/test_pool_provider_settings.py`,
`tests/cli/test_provider_switch.py`, `tests/cli/test_core_init.py`,
`tests/config/test_settings_repository_core.py`,
`tests/integration/test_context_limits.py`, `tests/tools/test_bounded_subprocess.py`
and `tests/utils/test_file_lock.py`. No tests were run for this read-only map;
these are future implementation gates, not claimed results.
