# Coding-agent goal: provider reliability checkpoint

User goal: an industry-leading coding agent that is entirely platform agnostic,
with OpenRouter emphasis. User chose reliable coding loop and provider portability
as the first priority. Interpret platform independence as both provider independence
and eventual Linux/macOS/Windows verification. Do not change provider defaults solely
to prefer OpenRouter. Goal remains active; no benchmark or cross-platform certification
has been completed.

## Completed first slice

- Shared object-only JSON tool argument parsing in providers/utils.py, including
  rejection of NaN/Infinity literals; both compatible and native Anthropic adapters use it.
- Compatible adapter only assembles tool calls for tool_calls completion. Truncated
  or filtered calls do not become fabricated calls in assistant history.
- Compatible transport/protocol errors propagate to the agent error event.
- Empty-choice usage chunks preserved; repeated finish metadata does not duplicate calls.
- Core streaming preserves content on the finish chunk and reports missing finish reasons.
- Core agent stops stall detection/retries after an error event.
- Realistic offline SDK-model regression fixtures across OpenRouter, generic compatible,
  DeepSeek, Ollama, and Anthropic. Fixed older fixtures previously hiding exceptions
  behind fabricated success responses; removed live-network Anthropic validation calls.
- Updated providers documentation, changelog, FEATURE_TODO, and TODOS.

## Verification

Fresh combined check: 533 passed, 1 existing skip (534 collected), covering tests/providers,
tests/core, six provider contract files, and tests/testing/test_tier9_documentation.py.
Ruff passed across touched source/tests. Mypy passed for the five touched production
modules (providers/utils.py, openai_compat.py, anthropic.py, core/agent_streaming.py,
core/agent.py). New Anthropic suite independently passes mypy.

Test-contract mypy has a preexisting imported-test issue in
tests/contracts/verify_provider.py: ModelProviderContract cannot be resolved from
tests.contracts.schemas.providers. Production mypy is clean for the touched scope.

Red/green evidence: original compatible regressions reproduced 48 failures; the four
provider-specific error-finish cases were separately demonstrated failing after correcting
their SDK parser fixture. Failed-stream stall retries reproduced four failures; nonstandard
numeric literals reproduced 12 failures. Native Anthropic initially reproduced six failures.
All now pass. Independent review found the numeric-literal gap; it is fixed and covered.

No full-repository test suite, live inference, or non-Linux verification was claimed.
Initial HTTP-mock tests stalled in SDK async metadata work; final tests isolate external SDK
calls while exercising actual response models and production adapters. Initial broader
provider baseline also stalled on old live Anthropic validation calls; those are repaired.

## Next slice: configured provider construction

Read nearby tests before changes. Audit already identified:

1. cli/app.py _get_provider checks environment first; _get_provider_from_environment
   always constructs DeepSeek from DEEPSEEK_API_KEY or HENCHMAN_API_KEY. This can
   override explicitly selected OpenRouter (or other) settings.
2. cli/commands/model.py passes api_key/model uniformly and omits saved settings.
   Ollama doesn't accept api_key; the generic provider expects default_model/base_url.
3. config/schema.py defines an openai provider block absent from provider registry.
4. Configured Ollama URL lacks the /v1 default used by its actual adapter.
5. OpenRouter constructor silently ignores extra kwargs; cover supported options honestly.

Prefer one coherent provider construction path respecting explicit provider selection,
canonical settings, provider-specific credentials, and local providers without credentials.
Preserve all unrelated workspace changes: hundreds of files were dirty before this task.
Do not reset or broadly format them.

Later milestones: edit/test/recover evaluations, cancellation/session resume, OS CI, measured
success/regression/cost/latency baselines. See FEATURE_TODO.md for durable roadmap state.
