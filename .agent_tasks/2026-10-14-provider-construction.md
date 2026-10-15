# Coding-agent goal: configured provider construction

Continuation of `2026-10-14-provider-reliability.md`. Goal remains active:
reliable coding loops and provider portability first, with OpenRouter emphasis.
No claim of industry-leading performance or full operating-system portability.

## Implemented

- Shared `providers/factory.py` used by CLI startup, slash/TUI switching,
  API startup, chat agents, and specialist overrides. Explicit provider selection
  wins over unrelated credentials. Saved credentials, `${VARIABLE}` references,
  provider-specific environment variables, and generic fallback resolve consistently.
- Registered the OpenAI alias; normalized public compatible `model` settings;
  validated invalid/missing options; kept generic local endpoints keyless.
- Ollama uses configured endpoint, OLLAMA_HOST, then adapter default. Root URLs
  normalize to `/v1`; custom proxy paths remain intact.
- Compatible request defaults survive construction and per-call overrides without
  mutating saved settings. Reserved conversation fields cannot be defaults.
  OpenRouter and DeepSeek forward request options; DeepSeek permits endpoint override.
- In-place switches refresh model/context budgets, preserve histories/session/tool
  bindings, and update inherited specialist providers while respecting explicit
  provider overrides. Model-only clones retain live connection/request settings,
  including native Anthropic token/retry/rate limits.
- Status reports configuration, not an unperformed connection test.
- Docs, changelog, FEATURE_TODO, TODOS updated. Two non-Git context tests now explicitly
  isolate their intended branch from host Git markers (both /tmp and desktop temp
  ancestors contain .git here); production context discovery unchanged by this slice.

## Verification

Fresh combined suite: **818 passed, 1 skipped (819 collected)**:

```sh
UV_CACHE_DIR=/tmp/henchman-uv-cache PYTHONDONTWRITEBYTECODE=1 uv run --extra dev python -m pytest --no-cov tests/providers tests/core tests/config tests/cli/test_provider_selection.py tests/cli/test_provider_switch.py tests/cli/commands/test_model.py tests/cli/commands/test_model_integration.py tests/cli/test_textual_app.py tests/cli/test_textual_mixins.py tests/agents/test_pool_provider_settings.py tests/chat/test_configured_provider.py tests/api/test_configured_provider.py tests/contracts/test_provider_registry_contracts.py tests/testing/test_tier9_documentation.py -q --tb=short
```

Ruff passed for touched production and test files. Mypy passed for 17 production
modules: factory, registry, provider utils, compatible/OpenRouter/Ollama/DeepSeek,
schema, CLI app/switch/model/Textual mixins, core Agent, pool/orchestrator init,
API server, chat manager. Scoped `git diff --check` passed.

Additional focused worker checks passed for existing pool/delegation/chat suites
and the legacy pool registry fixture (104 tests). Red/green regressions reproduced
wrong startup provider selection, dropped request options, invalid models, Ollama
root URLs, and DeepSeek model-only cloning before their fixes.
Independent read-only review found the DeepSeek cloning failure and native clone
preservation gap; both are fixed with regressions. Final review reported no
additional material correctness findings from inspected paths.

Broader Starlette TestClient runs stalled entering AnyIO's thread portal. An
outside-sandbox retry was interrupted before returning evidence; it is not a pass.
Direct async API lifespan tests pass. No full repository suite, live inference,
or Windows/macOS run is claimed. No known test processes remain running.

## Next work

Verify complete repository edit/test/recover workflows across adapters, then
cancellation and session resume. Follow with Linux/macOS/Windows installation and
coding-tool CI, and reproducible success/regression/latency/cost evaluations.
Preserve the extensive preexisting dirty workspace. Do not reset or broadly format.
