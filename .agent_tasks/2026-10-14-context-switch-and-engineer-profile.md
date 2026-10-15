# Context switching and engineer evaluation profile — 2026-10-14

The previous turn made progress through edit-contract fixes and live failures.
This turn adds representative engineer evaluation and implements the user's new
explicit requirement to set context length while switching models. The broad
industry-leading/provider-independent Python/team goal remains active; these
changes do not establish completion. No commit, push or publication performed.

## Context switch implementation

`/model set <provider> [model] --context-length <tokens>` accepts a positive integer
(also `--context-length=<tokens>`). Unknown/duplicate flags, missing values,
nonpositive/noninteger values and excess positionals fail without switching.
`/model` and successful switches show session capacity and actual conversation
budget. The existing compaction threshold applies once: 4096 with .75 yields3072.

Shared `switch_runtime_provider(..., context_length=...)` updates session settings,
the active agent, leader, pool policy and cached/future specialists. Agent and pool
setters retain both configured/effective limits, so later switches without the
option preserve the override. Histories/tools remain intact. Pool-managed pinned
provider/model choices remain intact; the existing behavior of explicitly switching
the selected active agent is retained. Distinct runtime/orchestrator settings are
updated together. Invalid limits and failed provider preparation preserve state.

This is session-local, with no disk writes or provider output-token changes. The
existing config command remains the way to persist startup settings. The switch
flag controls conversation compaction, not the server's total context capacity.
Tool schemas and generated output still need separate room. Native provider-picker
UI fields were not added; the slash command and shared switching API expose the
new value. No API model-switch endpoint currently exists.

## Engineer evaluation profile

`EvalTestRig(profile="engineer")` or `EVAL_PROFILE=engineer` reuses the canonical
engineer prompt, default preset, ToolManager registration, availability catalog,
and scoped registry filtering. Only real, allowed tools are exposed and logged.
The same AgentConfig/headless loop and independent scenario oracles are retained.
The explicit standalone environment does not claim full-team or interactive parity.

`basic` remains the default. Explicit profile wins over environment selection.
Unknown profiles fail before provider lookup. Engineer custom-prompt conflicts
fail explicitly; basic custom/config prompts retain their prior precedence.
Setup failures restore cwd and remove the owned temporary workspace.
`profile_metadata` exposes profile/single-agent scope, actual tool names, prompt
SHA256/character count and effective context budget, not prompt text or credentials.

Offline feedback test writes invalid Python, observes checker failure in the next
provider request, repairs the file, then observes successful AST and Python checks.
Prompt instructions and tool availability do not force a model to verify code.

## Verification

- Context command red:11 failures against the old parser.
- Core/runtime context API red:17 failures, then green.
- Profile red:9 failures, then11 passing contracts.
- Final combined source selection:**131 passed**,6.37seconds
  (`context-switch-profile-source-final.log`).
- Fresh rebuilt/force-reinstalled wheel:**587 passed**,50.08seconds, Linux/Python3.12
  (`context-switch-profile-wheel-linux.log`). Includes CLI aliases/RAG and broader
  offline coding/team/terminal/eval contracts outside the source checkout.
- Ruff clean across11 files, mypy clean across8 selected files, scoped diff clean.
- Independent review:41 profile/helper tests and28 context-switch/parser tests
  passed; no remaining actionable findings. No full-suite or native OS claim.

## Live profile evidence

Reused the existing pinned Qwen3-4B-Instruct-2507 Q8_0 artifact and llama.cpp b11617
Vulkan runtime; no downloads or provider fallback. Host remains60GiB RAM / RTX3090
24GiB, not a16GB laptop. Server cleanup is owned by the probe supervisor.

First engineer run retained8192 server context,6144 input budget,1024 output cap,
10 rounds,60 seconds per scenario and seed42. All four independent scenarios
failed: three abnormal `length` completions and one explicit context rejection
(8245 request tokens versus8192 server capacity). No task verified. The profile
has25 tools and a13670-character prompt; changing profile changes the experiment.
Report:`local-model-16gb-probe/qwen3-4b-engineer-profile-vulkan.json` and matching
probe/server logs. Owned PID2786011 exited0 and was confirmed absent.

Source inspection explains the limitation: system messages count toward the
conversation budget, tool declarations are attached afterward and are uncounted,
and the provider's output request is separate. Compaction can also preserve a
system/protected set larger than its target. The new switch option exposes the
conversation policy but does not fix total-request accounting. This is an open
reliability issue, not evidence of model task quality.

Second, separately labelled experiment increased the server context to16384 and
conversation budget to8192, retaining the1024 output cap,10 rounds,60-second
deadline, seed and independent oracles. Report:
`local-model-16gb-probe/qwen3-4b-engineer-profile-16k-vulkan.json` and matching logs.
This is not a controlled quality comparison with the8K/basic runs.

- Class extension failed (18.33s): model ran a successful lint check but replaced
  the original `clear` method body while adding multiply; independent AST checks
  caught the regression despite normal runtime completion.
- Counter refactor failed its10-round limit (13.81s). After writing and linting,
  it repeatedly attempted a syntactically balanced `python -c "...; ...;"` shell
  command. The shell tool returned `Invalid shell syntax: No closing quotation`.
  This retained command/error is a concrete candidate tooling defect to reproduce
  next, rather than attributing every failure to the model. The agent repeated the
  rejected command instead of recovering through available `python_exec`.
- Scoped rename passed independent checks (8.59s). The agent recovered from a
  missing edit target by using unique-context replacements and ran lint.
- Multi-file edit hit the10-round limit (7.89s): missing edit targets and a
  mismatched docstring in `old_str` prevented completion.

Result:**1/4**, with actual lint calls and a verification attempt now observed.
Lint success still did not establish behavioral correctness. Owned PID2790522
exited0 and was confirmed absent; no owned model server remains. Existing Ollama
service was left untouched. The retained independent failures and total-request
accounting gap remain open; no industry-leading or local-default claim is made.
