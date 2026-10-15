# Coding-loop reliability checkpoint

Goal remains active: an industry-leading, platform-agnostic coding agent with
OpenRouter emphasis. User prioritizes reliable coding loops and provider portability.
This is an engineering milestone, not evidence of industry-leading model performance
or full platform certification. Prior checkpoints cover provider stream safety and
shared construction/switching.

## Implemented behavior

- Core and provider adapters close nested streams deterministically on completion,
  errors, cancellation, and explicit close. Original exceptions take priority over
  secondary cleanup failures. Generic AsyncIterator providers remain supported.
- Continuations emit FINISHED with their own reason/usage; preparation failure cannot
  reuse stale usage. Cancellation does not emit successful completion. Partial text
  and reasoning retain a [Response interrupted.] marker without unfinished calls.
- Tool batches require nonempty IDs/names and unique IDs within each response before
  persistence or dispatch.
- Headless JSON modes share bounded iterative execution, correlated tool results,
  one terminal event, nonzero failure exits, and cancellation of queued work.
- Orchestrator/public delegation streams propagate closure. Pending batches are
  settled from actual agent history even when a consumer saw only one request.
  Full tool/delegation results survive presentation previews.
- Interactive errors stop queued work. Cancellation reconciles already completed
  results exactly once, including buffered events and rendering failures after role
  reminders. Lookup stops at the current assistant declaration so repeated IDs from
  earlier rounds cannot masquerade as completed work.
- REPL cancellation joins the running agent task before saving. REPL and Textual
  persist settled turns on completion/cancellation; Textual initializes a session
  when absent and autosaves on shutdown. Direct-role paths use the chosen specialist.
- Agent.current_turn_messages retains independent, uncompressed current-turn
  evidence. Core and all six orchestration insertion sites record messages there.
  Session saving replaces only the current suffix, retaining older conversation.
- Restore retains reasoning and independent tool arguments, reconstructs configured
  system prompt, removes previous-session summaries, and avoids duplicate prompts.
  Actual compaction -> disk -> resumed Agent.run test validates call/result pairing,
  both original 23000-character tool results, reasoning, and new user input.

## Verification

Regressions were reproduced before fixes for lifecycle closure, missing continuation
completion, stale usage, invalid identities, partial preservation, unsafe queued
execution, duplicate results, missing declarations, context-compaction evidence
loss, summary leakage, and orchestration-generated messages absent from the archive.

Worker checks: 287 core tests; 336 provider tests with one skip; 255 focused
orchestrator/archive tests; 51 session-related tests. These counts overlap and must
not be summed. Root's first combined gate caught the orchestration reminder/archive
integration while it was still landing; the stable rerun is recorded below.

Ruff passes for all 21 touched production modules and the relevant new/updated test
files. Mypy passes for the 21 production modules. Scoped git diff --check passes.
Final combined test result: **902 passed, 1 skipped, 10 deselected**, 53.54 seconds
on Python 3.14.4. The skip is an existing Anthropic rate-limit timing test; the ten
deselections are the explicitly unverified real coding-loop cases below. One
third-party Chroma asyncio deprecation warning remains.

Combined gate includes tests/providers, tests/core, provider registry contracts,
orchestrator/interruption/turn-transcript/delegation suites, output/executor and
stream interruption, headless, session roundtrip, REPL persistence/session/chat UI,
Textual mixins/session management, app coverage/extended, and malformed OpenRouter
E2E cases. All final sessions are terminal; no test process remains running.

## Subsequent unrestricted verification

After the environment changed, root ran all 12 cases in
tests/e2e/test_coding_loop.py successfully on Linux/Python3.14.4. The fresh
Linux/Python3.12 installed-wheel smoke also passed all82 staged tests after a
fixture-specific stale-bytecode repair. See the platform checkpoint for evidence.
Local CPU inference probes now exercise the actual compatible SDK/HTTP path;
behavioral results and limitations are in the local-default-model checkpoint.
Native Windows/macOS and live remote-provider verification remain open.

## Remaining verification at the original checkpoint

- Ten real coding-loop cases in tests/e2e/test_coding_loop.py cover five factory
  adapters x two output modes with real read_file/edit_file/ShellTool pytest calls.
  They remain UNVERIFIED. The current sandbox stalls on the first AnyIO file-thread
  dispatch; even a minimal anyio.to_thread.run_sync(lambda: 42) times out.
  Do not replace actual tools with fakes and claim the end-to-end workflow passed.
- SDK+httpx transport integration also stalled in thread-dependent setup. Lifecycle
  suites use SDK response-interface fakes with real SDK chunk/event types, not live
  HTTP or inference. No external API credits were used.
- Linux/macOS/Windows installation and coding-tool CI, interactive terminal-driver
  checks, and reproducible quality/cost/latency evaluations remain open. Broad
  workflow and benchmark roadmap items intentionally remain unchecked.
- An earlier unrelated test failed:
  tests/empty_message_validation/test_empty_messages.py::TestInputValidationInREPL::test_repl_processes_valid_input
  expects renderer.info. It was not repaired in this scoped slice. No claim of
  full-repository clean tests.

## Process state and next steps

Previous blocked SDK/test sessions 92288, 10883, 88534 were stopped with exit 130;
28125 and 61038 were confirmed absent. Latest outside-sandbox thread diagnostic was
aborted by user after 450 seconds with no execution evidence. No auto-review rejection
occurred; do not assume it executed or repeat escalation indefinitely.

Stable combined verification is complete. Next independent work can prepare cross-platform verification and
reproducible evaluation infrastructure while the real-tool runtime check awaits a
working execution environment. Keep the broad goal active.

Preserve the extensive preexisting dirty workspace. No reset, broad formatting,
staging, commits, pushes, or publication occurred in this slice.
