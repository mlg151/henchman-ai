# Configured leader and protected execution lifecycle

Previous turn was progress: the exact reported OpenRouter command and installed
entrypoint import were verified. This turn fixes live leader configuration,
direct-role UI routing and active execution state. The full coding-agent goal
remains active; no industry-leading or live-model competence claim is supported.

## Implementation

Raw partial builtin-role settings merge canonical preset metadata before normal
validation. Explicit fields/lists replace defaults; programmatic typed configs
remain explicit; unknown custom roles retain required metadata. Real canonical
.henchman repository load/set/import/export coverage preserves unrelated fields.

The orchestrator now obtains its leader via pool.get_agent('tech_lead'). Normal
and direct leadership share the cached instance, identity, scoped tools, history
and reset behavior. Existing provider resolution handles saved provider overrides
and model-only live connection/options copying. Prompt precedence is nonempty
runtime override, configured prompt (including intentional empty), generated
team/environment prompt. Legacy empty runtime argument means no override.

Shared actor resolution drives REPL/Textual toolbar/provider/model labels and
slash commands. Textual provider picker also changes its active direct role.
Explicit provider/model selection overrides the active role for the session;
other pinned roles and saved overrides remain unchanged. Explicit context 700000
retains raw capacity and a 525000 conversation budget. Toolbar percentages honor raw
capacity instead of unrelated default-model metadata.

Independent review reproduced active cached leader self/ancestor delegation
clearing parent history and producing orphan tool responses. AgentPool now owns
identity-based execution claims. Delegation reserves before resetting history or
yielding AGENT_STARTED; the exact AgentLoopParams instance owns its controller
handoff. Running owners cannot reenter; reservations release on failure, retry,
cancellation and consumer closure. Balanced failed tool results let parents
continue after rejecting active self/ancestor or aliased targets.

Further review reproduced concurrent public runs replacing the active ledger
before controller rejection. Per-orchestrator public admission now precedes
validation/resolution/preparation, while root target reservation precedes the
initial event. Shared ledger/runner/metrics/status/cache remain unchanged on
rejection. Independent delegated specialists remain able to run concurrently.

Fixture drift repaired without weakening production checks or assertions: provider
MagicMocks bind concrete token-accounting methods; standalone controller tests
have real pools; MCP setup has real Settings; session-recording test explicitly
grants its custom tool to the acting scope. Broad legacy test-file mypy findings
remain outside this slice (no whole-tree static-clean claim).

## Evidence

- Leader worker: 26 red tests before implementation, final 123 focused passed.
- Schema worker: 8 red failures before implementation, all 196 config tests passed.
- Root switch tests: 4 original failures; all 4 pass after shared construction.
- Root real-adapter requests: 10 variants across OpenRouter, generic compatible,
  DeepSeek, Ollama and native Anthropic, saved-provider and live-model-only modes.
  Assertions inspect outgoing model, prompt, schemas, output cap and request
  options. Only SDK transport replies are scripted; no network calls.
- Display/command worker: 7 display and 5 direct-command red regressions; final 18
  new cases pass. Real CommandProcessor tests cover show/set and context700000.
- Instance guard: 5 failures/2 existing passes before repair; public admission
  extension 6 failures/1 existing pass before repair. Final 16 guard cases cover
  alias/self/ancestor, startup gaps, all public normal/direct pairs, state
  preservation, concurrent owners, cancellation, closure, retries and reuse.
- Independent final review: 42 focused tests pass, original concurrent blocked
  provider reproduction rejected without state mutation, invalid inputs release
  admission; no outstanding actionable review findings in requested scope.
- Final root source gate: 549 passed in 47.97s, Python 3.14 on Linux.
  Log: leader-configuration-final-source.log. One existing Chroma deprecation
  warning remains. Source gate includes real subprocess edit/test recovery for
  all five adapters, original positive and denied-leader-edit team workflows.
- Ruff: 21 source/test/helper targets clean; mypy: 17 source/test/helper targets
  clean. New SDK test also passes mypy with follow-imports=silent, avoiding
  unrelated preexisting typing errors in imported transport test fixtures.

Fresh wheel built and forceinstalled into portable-wheel-env (Python 3.12), rather
than trusting same-version pip installation. Artifact:
leader-configuration-wheel/henchman_ai-0.3.17-py3-none-any.whl.
Installed-wheel verification completed outside the checkout: 1089 passed in
62.34s. Log: leader-configuration-wheel-linux.log. Package origin checks, both CLI
aliases (version/help/invalid command), and local RAG smoke also passed. Isolated
pytest marker registration now includes anyio; no pytest warnings were reported.

## Remaining scope

Native Windows/macOS hosted results, live cross-provider Python task quality,
reuse and DevOps outcomes, long-turn memory/context behavior, physical 16 GB laptop
validation, model selection/distribution and comparative performance remain open.
The earlier local-model engineer probe remains 2/4 at 16K; it was not rerun here.
Generated leader prompt delegation inventory still merits a separate audit
(it advertises the leader role even though active self-delegation is rejected).
No cloud model calls, model servers, staging, commits, pushes or deployments.
