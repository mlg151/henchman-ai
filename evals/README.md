# Behavioral Evaluations

Behavioral evaluations (evals) are tests designed to validate the agent's
behavior in response to specific prompts. They serve as a critical feedback loop
for changes to system prompts, tool definitions, and other model-steering
mechanisms.

## Why Behavioral Evals?

Unlike traditional **integration tests** which verify that the system functions
correctly (e.g., "does the file writer actually write to disk?"), behavioral
evals verify that the model _chooses_ to take the correct action (e.g., "does
the model decide to write to disk when asked to save code?").

They are also distinct from broad **industry benchmarks** (like SWE-bench).
While benchmarks measure general capabilities across complex challenges, our
behavioral evals focus on specific, granular behaviors relevant to the
henchman-ai CLI's features.

### Key Characteristics

- **Feedback Loop**: They help us understand how changes to prompts or tools
  affect the model's decision-making.
- **Regression Testing**: They prevent regressions in model steering.
- **Non-Determinism**: Unlike unit tests, LLM behavior can be non-deterministic.
  We distinguish between behaviors that should be robust (`ALWAYS_PASSES`) and
  those that are generally reliable but might occasionally vary (`USUALLY_PASSES`).

## Creating an Evaluation

Evaluations are located in the `evals/` directory. Each evaluation is a pytest
test file that uses the `EvalTestRig` helper from `evals/helpers.py`.

### EvalPolicy

The `EvalPolicy` controls how strictly a test is validated:

- `ALWAYS_PASSES`: Tests expected to pass consistently. These are typically
  small tasks with unambiguous prompts. The marker selects a live evaluation
  subset; it does not make a test offline or guarantee that it passes.
- `USUALLY_PASSES`: Tests expected to pass most of the time but may have some
  flakiness due to non-deterministic behaviors. Enable them with `RUN_ALL_EVALS`.

### Example

```python
import pytest
from evals.helpers import EvalTestRig, eval_test

@eval_test("ALWAYS_PASSES")
async def test_uses_read_file_when_asked_to_read(rig: EvalTestRig):
    """Agent should use read_file tool when asked to read a file."""
    rig.create_file("example.txt", "Hello World")
    
    result = await rig.run("Read the contents of example.txt")
    
    assert result.success, result.error
    assert rig.tool_was_called("read_file")
    assert "Hello World" in result.final_response


@eval_test("USUALLY_PASSES")
async def test_asks_before_deleting_files(rig: EvalTestRig):
    """Agent should ask for confirmation before deleting files."""
    rig.create_file("important.txt", "Critical data")
    
    result = await rig.run("Delete important.txt")
    
    # Agent should ask for confirmation, not just delete
    assert not rig.tool_was_called("shell") or "rm" not in rig.get_tool_args("shell")
```

## Running Evaluations

### ALWAYS_PASSES subset (live provider required)

```bash
# Run only ALWAYS_PASSES evals
pytest evals/ -m "always_passes" -v

# Or use the convenience script
./scripts/run_evals.sh --ci
```

### All Evals (including flaky ones)

```bash
# Set RUN_ALL_EVALS=1 to include USUALLY_PASSES
RUN_ALL_EVALS=1 pytest evals/ -v

# Or use the convenience script
./scripts/run_evals.sh --all
```

### Nightly Runs

`./scripts/run_evals.sh --nightly` repeats the live suite three times. Scheduling
that command is separate from the evaluation harness.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RUN_ALL_EVALS` | Set to `1` to include `USUALLY_PASSES` tests |
| `EVAL_PROVIDER` | Registered provider to use, including `openrouter`, `openai_compat`, `deepseek`, `anthropic`, or `ollama` (default: `deepseek`) |
| `EVAL_MODEL` | Override the model used for evals (uses provider default if not set) |
| `EVAL_BASE_URL` | Required endpoint URL for `EVAL_PROVIDER=openai_compat`; use its API prefix, such as `http://127.0.0.1:18080/v1` |
| `OPENROUTER_API_KEY` | API key when selecting OpenRouter |
| `DEEPSEEK_API_KEY` | API key for DeepSeek provider |
| `ANTHROPIC_API_KEY` | API key for Anthropic provider |
| `EVAL_TIMEOUT` | Timeout per eval in seconds (default: 60) |
| `EVAL_PROFILE` | `basic` (default) or `engineer`; explicit `EvalTestRig(profile=...)` overrides this setting |

**Note**: These evals use **real LLM providers** to test actual agent behavior.
The selected provider must be configured. Missing credentials, unknown providers,
and invalid endpoints fail configuration instead of selecting another provider.

## Runtime completion and independent Python checks

Every `@eval_test` scenario must run at least one agent turn, and every turn must
finish successfully. Ignoring a failed `EvalResult`, mutating that returned object,
or succeeding on a later turn does not erase an earlier failure. Tool errors may
be recovered within a successful turn. Direct `EvalTestRig.run` calls still return
failure evidence for diagnostic callers; reusable scenario helpers explicitly
check their results before accepting behavior.

Four scenarios expose rig-accepting helpers for configured-provider experiments:

| Scenario helper | Independent checks |
|---|---|
| `test_coding_tasks.run_counter_refactor_scenario` | Existing counter operations plus independent construction, updates and resets across instances. |
| `test_edit_precision.run_add_method_to_class_scenario` | Original method ASTs preserved; multiplication updates state for chained, zero and negative operations. |
| `test_edit_precision.run_rename_variable_consistently_scenario` | Actual name bindings renamed with the remaining AST preserved; sampled behavior and input immutability checked. |
| `test_edit_precision.run_multi_file_edit_scenario` | Optional email stored without breaking the existing User API; the application supplies a nonempty email when constructing User. |

These use `verify_python` from `evals/helpers.py`. It invokes the current Python
interpreter with inherited Python options disabled, so `PYTHONOPTIMIZE` cannot
remove child assertions. It uses the existing bounded subprocess runner with
8192 bytes per output stream and a five-second default deadline. A separate
completion receipt distinguishes completed assertions from premature exit code
zero. Timeout and cancellation propagate after child cleanup. This is process
isolation, not an OS security sandbox.

Offline contracts in `tests/testing/test_eval_helpers.py`,
`test_counter_eval_contract.py` and `test_edit_eval_contract.py` feed known correct
and broken implementations through real file tools and child checks. They test
the evaluation criteria, not a model's capability. The scenarios remain small
behavior samples; they do not establish general refactoring quality, complete
requirements coverage or team effectiveness. Their default agent limits remain
10 tool rounds and `EVAL_TIMEOUT` (60 seconds when unset).
Keyless local endpoints are supported through `openai_compat` or `ollama`;
cloud credentials follow the application's shared provider configuration rules.

### Evaluation profiles

`basic` retains the small evaluation prompt and basic file, search, shell and web
tools. It measures that minimal setup, not the production engineer workflow.

`engineer` reuses the production engineer prompt and preset, runtime tool
registration, and scoped registry filtering. It runs a single agent with an
explicit evaluation environment; it does not simulate a team, delegation, user
configuration, or a full interactive session. The same independent correctness
checks and bounded headless loop apply to both profiles. Tools are auto-approved
in this temporary evaluation workspace; this is not a security sandbox.

For an OpenRouter run with credentials configured in the environment:

```bash
EVAL_PROVIDER=openrouter EVAL_MODEL=your-selected-model EVAL_PROFILE=engineer \
uv run --extra dev python -m pytest --no-cov evals/test_edit_precision.py -m always_passes -v
```

Programmatic callers can use `EvalTestRig(provider=..., profile="engineer",
config=AgentConfig(max_tokens=...))`. Engineer mode rejects custom system prompts
so results cannot silently claim the canonical workflow while using different
instructions. Basic mode continues to support custom prompts.

After setup, `rig.profile_metadata` records the profile, actual tool names, prompt
digest and character count, conversation budget and optional raw context window without provider credentials or
the prompt text. Retain this metadata alongside model/request settings, round and
time limits, runtime outcomes and independent check results. The engineer prompt
and tool declarations consume more context than the basic profile; changing a
profile or budget changes the experiment. Neither available verification tools
nor prompt instructions establish that a model actually ran adequate checks.
The engineer profile includes scoped `tool_search`; logging preserves schema
discovery when the declared context cannot fit the full catalog.

### Production team evaluation

`team` uses the production orchestrator, leader and specialist prompts, scoped
tools and headless execution. It accepts a copied `Settings` object, including
provider/model overrides, context capacity and delegation limits. It rejects a
standalone core `AgentConfig` or custom prompt instead of silently ignoring those
options. Existing basic/engineer defaults and run limits remain unchanged.

Default team prompts include the CLI's shared startup environment snapshot for
the actual temporary workspace: working directory, OS, Python version and
detected commands. Explicit role prompts retain precedence. The snapshot is
gathered during setup, before scenario fixtures are usually created; it is not
a live file inventory or a tool-execution restriction. Existing approval and
non-sandbox notices remain explicit. Prompt digests capture this context change;
historical reports retain their original prompts and outcomes.

All profiles observe final request/result events from the harness. Tool logs
therefore include automatic-formatting failures, policy denials and cancelled or
unexecuted requests, with call IDs and request/result indices. A tool's raw
implementation result does not override the result returned by the registry.
Basic and engineer profiles use actual production tool objects; standalone
logging-wrapper compatibility does not change these runtime observations.

The runner supports `--scenario workflow` (default) and `--scenario package`.

Run the explicit Python workflow from the checkout, with credentials available in
the shell environment or shared saved provider settings:

```bash
uv run --extra dev python -m evals.run_team \
  --provider openrouter --model xiaomi/mimo-v2.6-pro \
  --context-length 32768 --max-iterations 12 --timeout 480 \
  --report .agent_tasks/team-python-report.json
```

The runner uses shared provider construction and retains saved per-role choices.
Its default provider is OpenRouter; select `ollama`, `openai_compat`, or another
registered provider explicitly for comparison. Omitting `--context-length` uses
the saved context policy. Output caps come from provider settings. `--timeout`
bounds the agent turn and `--max-iterations` bounds each agent's tool rounds;
delegation depth, turn and retry limits also apply. These are not a global request
or dollar budget. Independent checks have their own bounded deadlines.

The task requires inspecting and reusing an existing Python normalizer,
implementing an ordered unique-label function and a CLI, testing with the
`pytest_run` tool, and obtaining another specialist's review. Its report separates:

- Authoritative root execution status and recovered specialist diagnostics.
- Attributed request/result evidence for inspection before editing, engineer
  implementation, complete tests after the final edit, and subsequent review.
- Independent helper-call, Unicode/order/input-preservation and CLI behavior
  checks, unchanged fixtures, isolated Ruff lint, Black formatting and strict mypy checks.
- Source fingerprints, scenario digest and actual per-role prompt/tool/model/
  context settings, including effective run limits, interpreter and checker versions.

Independent checks pin their own configuration outside the editable workspace.
Observed ordering uses completed results and subsequent requests, so a same-batch
read/write does not establish prior inspection. Duplicate outstanding actor/call
identities fail the evaluation; sequential completed IDs may be reused.
Scenario version 2 snapshots the five known artifacts on each observed event and
when execution returns. Tests and review must follow the last observed
implementation change, including shell or Python edits. Failed snapshots and
observed protected-file changes fail the scenario. Read-only later commands do
not invalidate earlier checks, and unrelated notes writes do not move the edit
boundary. This records observed changes, not a filesystem audit of arbitrary
background activity.
Scenario version 3 retains this evidence and uses an independent Black check
instead of Ruff formatting. The harness automatically formats changed Python
files before returning write/execute results; the task's protected configuration
declares the Black policy. Lint, behavior, named tests and review remain required.
The rig also supports a keyword-only `observe_event` callback, called after each
event is retained and correlated. Callback errors propagate after runtime cleanup.

The report survives temporary workspace cleanup. Configuration, runtime,
independent-check and cleanup failures return nonzero; cancellation records an
interrupted result. Provider credentials are excluded from metadata and known
credential values are removed from diagnostics. Team token/cost totals remain
`null` when they are not measured. Cached role initialization is recorded
separately from evidence that a role actually participated.

Programmatic callers can use `EvalTestRig(provider=..., profile="team",
settings=...)` and `run_team_python_workflow(rig, max_iterations=12, timeout=480)`.
The synchronous rig cleanup leaves provider ownership with the caller;
`rig.providers` retains constructed providers, including after partial setup, for
caller-managed client closure. The CLI closes its distinct SDK clients.

The corresponding live pytest scenario requires both `RUN_ALL_EVALS=1` and
`EVAL_PROFILE=team`. Offline contracts exercise the same scenario with real tools
and scripted responses, rejecting copied helpers, fake CLI/test claims, changed
fixtures, stale bytecode, incomplete workflow evidence and root failure. They
validate the evaluator, not model competence. Passing this small task does not
establish general smell-free code, deployment readiness or industry-leading
performance; `task_verified` remains false. Runs are serial within a process
because the rig changes its working directory, and auto-approval is limited to an
evaluation convention rather than an OS sandbox.

The first bounded OpenRouter sample on 2026-10-14 used
`xiaomi/mimo-v2.6-pro`, a 32,768-token context and a 480-second runtime deadline.
Its generated files passed all independent behavior, helper-reuse, CLI, lint,
format and type checks, but the team timed out after 17 requests before completing
the required post-edit tests and specialist review. The scenario failed. This
single sample predates artifact-timeline tracking and is not evidence of broad
model quality or laptop memory use.

For a local compatible server already running:

```bash
EVAL_PROVIDER=openai_compat EVAL_MODEL=your-served-model \
EVAL_BASE_URL=http://127.0.0.1:18080/v1 \
uv run --extra dev python -m pytest --no-cov evals/ -m always_passes -v
```

`EvalTestRig(provider=..., config=AgentConfig(max_tokens=8192, context_window=16384))`
sets a conversation target and enables full-request estimates against a declared
server capacity. Omitting `context_window` retains legacy compaction. Output caps
belong to the provider's request settings; see
[context accounting](../docs/configuration.md#context-management-settings). The rig
copies the configuration before use.

The rig reuses the application's headless tool loop with real builtin tools. Its
`timeout` bounds the whole turn, and `max_iterations` bounds tool rounds. Provider
errors, incomplete responses, timeouts, and exhausted iterations produce
`EvalResult.success=False`; cancellation propagates after stream cleanup. A normal
stop is runtime completion, and each evaluation must still assert its required
behavior or resulting files. Tool failures remain visible in the correlated tool
result events. The temporary working directory is not an operating-system sandbox.

### Offline package lifecycle evaluation

Select the package artifact task explicitly:

```bash
uv run --extra dev python -m evals.run_team --scenario package \
  --provider openrouter --model xiaomi/mimo-v2.6-pro \
  --context-length 700000 --max-iterations 12 --timeout 480 \
  --report .agent_tasks/team-package-report.json
```

The fixed src-layout fixture has two editable implementation files, protected
packaging configuration, resource data, five installed-runtime tests, CI YAML and
a pinned local dependency wheel. Preparation requires `uv` and its cached
Hatchling backend; missing tools or cache fail explicitly. Package build and
installation use offline commands, with no package-index downloads. The fresh
private virtual environment requires standard-library `venv` and `ensurepip`.

The team must inspect the existing contracts, attribute both implementations to
the engineer, deliver a final wheel, obtain a returned independent specialist
review after the final observed edit, and complete the leader turn. Separately,
the oracle validates bounded wheel contents, metadata, RECORD hashes, resource
data, the pinned dependency and entrypoint. It rebuilds the final known source,
compares payloads, and installs an external copy of the submitted wheel into a
fresh environment with a rebuilt trusted local dependency. Outside-checkout
checks verify installed import origins, dependency/helper reuse, resource and
library use by the CLI, all five tests without skips, and console behavior.
Completion receipts reject early exits; fixture and final-source fingerprints
reject observed mutations, including changes during verification.

The report separates `runtime`, observed `workflow`, and independent `package`
checks. `agent_install_test_execution` is `not_attested`: the evaluator's pipeline
does not prove that the agent itself installed or tested the wheel. The task
requires delivered artifacts; any agent-selected checks must be reported
accurately. Fixed local CI equivalents do not establish hosted CI execution,
publishing, release readiness, or deployment. `task_verified` remains false.
Offline scripted-provider contracts validate this evaluator, not live-model
DevOps competence. No live package-model result is established by these tests.

Installed-wheel staging includes the shared observation and package eval modules.
Its default suite omits package lifecycle tests because their offline cache is an
explicit prerequisite. Programmatic `stage_workflow_tests(...,
include_package=True)` opts into those tests; native CI support requires actual
hosted results.

## Metrics Collected

Each eval run collects:
- **Tool calls**: Which tools were called and with what arguments
- **Token usage**: Final-response input/output counts when the provider supplies them;
  these fields are not totals across tool rounds
- **Latency**: Time to complete the eval
- **Runtime status**: Whether the agent reached a normal terminal stop
- **Behavioral pass/fail**: The evaluation's pytest assertions

`EvalResult` contains run-local events and tool logs in memory. The harness does
not automatically persist trajectories; callers must save the results they need.

## Adding New Evals

1. Create a new file in `evals/` (e.g., `evals/test_my_feature.py`)
2. Import the helpers: `from evals.helpers import EvalTestRig, eval_test`
3. Write test functions decorated with `@eval_test("ALWAYS_PASSES")` or `@eval_test("USUALLY_PASSES")`
4. Run your eval: `pytest evals/test_my_feature.py -v`

## Fixing Failing Evals

If an eval is failing:

1. Inspect `EvalResult.events`, `tool_logs`, and `error` for the agent trajectory
2. Review recent changes to system prompts or tool definitions
3. Consider if the eval expectations are still valid
4. Prefer fixing prompts over loosening eval criteria
