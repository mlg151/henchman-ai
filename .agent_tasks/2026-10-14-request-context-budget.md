# Request context budgeting and live switch repair

Goal remains active. This milestone does not establish industry-leading coding
performance, native platform verification, or a qualified 16GB laptop model.

## User-visible repair

The user reproduced `/model set openrouter xiaomi/mimo-v2.6-pro --context-length
700000` failing because the switcher passed `context_window` before the Agent
setter accepted it. The setter now accepts and validates both values before
mutation. An exact-command regression uses real leader/cached/future agents and
verifies capacity700000, default-threshold budget525000, selected model/provider,
and retained histories. No live OpenRouter request or model capacity claim.

The global `/home/matthew/anaconda3/bin/henchman` Python environment imports
`/home/matthew/mlg-cli/src/henchman/core/agent.py`; signature inspected and includes
`context_window`. Restart is required for a process that loaded the old class.

## Implementation

- Core AgentConfig and pool ContextConfig retain optional raw context_window,
  separate from max_tokens conversation target. Production team settings and
  explicit switches propagate both to live/cached/future agents. Standalone None
  keeps legacy behavior.
- Provider budget hooks are concrete defaults, preserving custom-provider ABI.
  Compatible adapters estimate actual message/tool JSON and known structured
  schema options, applying extra_body precedence. Explicit output caps are
  preserved, invalid/ambiguous caps rejected. Unset compatible caps explicitly
  request min4096/quartercapacity. Anthropic reserves its configured cap.
- The core projects each request before sending, snapshotting tools and reserving
  output. System messages and the complete current turn (including stall nudges)
  stay intact. Complete older user-turn prefixes may be omitted from the request;
  original history is retained. Required input that cannot fit fails locally.
- Guarded requests bypass legacy model summarization and body truncation. Counts
  remain estimates: tokenizer/templates and opaque extensions are limitations.
- Eval metadata records raw capacity; the probe explicitly passes server capacity.

## Evidence

- Core tests observed9fail1pass before integration, then18passed covering mandatory
  prompt/schema/reasoning/tool-result overflow, pruning/history safety, dynamic
  tool scopes, output options, invalid updates and standalone compatibility.
- Provider tests observed36fail before hooks;93provider tests passed after.
- Source integration gate:170passed23.21s in request-budget-source.log.
- Ruff21files clean; mypy14source/helper files clean. Some legacy test files have
  unrelated existing type errors recorded by workers; no whole-tree clean claim.
- Independent review: no concrete defect,56focused tests passed before added tests.
- Installed wheel: 694 passed in 42.44s, outside checkout; CLI aliases and RAG smoke passed.
  Full log: request-budget-wheel-linux.log.
- Wheel artifact: request-budget-wheel/henchman_ai-0.3.17-py3-none-any.whl,
  forceinstalled in portable-wheel-env (Python3.12; source checks Python3.14).

Initial integration failures identified provider MagicMock fixtures returning
mock budget values. Fixtures now bind real base accounting methods, preserving
assertions. E2E team fixtures declare16K capacity after measured6319+2000 overflow
at8K. Full-UI clarification fixture declares32K after measured13164input tokens;
these tests previously depended on input-only accounting. No production default
capacity was silently increased. Docs warn default8K is inadequate for full scopes.

## Local evidence

Pinned Qwen3-4B-Instruct-2507 Q8_0, same hash/runtime/sampling/independent oracles as
prior probes. RTX3090 development host, not a physical16GB laptop test.

- 8K engineer: all4 rejected locally before inference; estimated input8047–8071
  plus explicit1024output exceeds8192. This is guard evidence, not model quality.
- 16K engineer:2/4pass(counter,rename); class modifies existingclear method;
  multi-file hits10rounds. No context-overflow error. Full reports/logs retained
  under local-model-16gb-probe/qwen3-4b-engineer-request-budget-{8,16}k-vulkan.*.
- Owned server PIDs2811616 and2812636 exited0 and were confirmed absent. User's
  unrelated Ollama process was not changed.

No commit, staging, push, deployment, or cloud model call. Remaining objectives
include dependable live coding/team outcomes, DevOps/reuse evidence, context
behavior during longer coding turns, native Windows/macOS runs and 16GB hardware
validation. Do not convert this checkpoint into a completion claim.
