# Quoted Python verification checkpoint — 2026-10-14

The previous turn was progress: session context selection, engineer evaluation
profiles, and live failures changed the next action. This turn fixes the concrete
shell validation failure that prevented a counter-refactoring verification command
from executing. The full coding-agent goal remains active and unproven.

## Root cause and scope

`sanitize_command` already checks the full command for control characters,
restricted patterns and balanced quoting with shlex. It also recursively split
every command at `;`, `&` and `|`, regardless of quoting. A balanced Python snippet
therefore became unbalanced fragments and failed with `No closing quotation`.

The default ShellTool supplies no command-prefix policy. Its recursive pass was
redundant, so that pass now runs only when an explicit prefix policy is supplied.
All full-command checks, raw command preservation and EXECUTE confirmation remain.
The optional prefix-restricted helper path retains its conservative checks and
quoting limitations. No custom shell parser, reconstructed command, new execution
mode, or relaxed dangerous-pattern policy was introduced. This is not a sandbox.

## Regression and verification evidence

- New test file: `tests/tools/test_shell_quoted_python.py`.
- Red: **8 failed / 11 passed**, including the actual live counter verification
  snippet executed against an isolated fixture (`shell-quoted-python-red.log`).
- Source gate: **196 passed**,8.01seconds (`shell-quoted-python-source.log`).
  Covers quoted snippets, real subprocess execution, whole-command restrictions,
  optional prefix policy, existing shell behavior/portability and security contracts.
- Fresh rebuilt and force-reinstalled wheel: **629 passed**, 49.52 seconds on
  Linux / Python 3.12 (`shell-quoted-python-wheel-linux.log`). CLI aliases, local
  RAG and the broader staged runtime suites passed outside the source checkout.
  No full-suite or native Windows/macOS verification claim is made.
- Ruff clean across3 touched Python files; mypy clean across2 selected files;
  scoped diff check clean.
- Independent review found no weakened default restrictions or remaining actionable
  findings; **42 focused tests passed**.
- The existing installed-wheel suite now stages the new regression and public
  security tests. Source-only tests loading a hard-coded source-tree path are not
  used as installed-package evidence.

Docs, changelog and roadmap updated. No commit, push, publication or changes to
the context-switch feature from the preceding turn.

## Live experiment

Reused the preceding engineer profile: Qwen3-4B-Instruct-2507 Q8_0, pinned llama.cpp
b11617 Vulkan runtime, seed42,16384 server context,8192 conversation budget,1024
output tokens,10 rounds and60seconds per scenario. No downloads, criteria changes
or fallback to another provider. Host remains60GiB RAM / RTX3090 24GiB, not a16GB
laptop. This is a single model/profile run, not a controlled benchmark or proof of
general coding quality.

Report: `local-model-16gb-probe/qwen3-4b-engineer-shell-fix-vulkan.json`, with matching
probe/server logs. The counter scenario now passes independent behavior checks;
the previous run repeatedly rejected its balanced Python command and exhausted
the tool-round limit. Class extension still fails because it changes the original
`clear` method despite a successful lint check. Those independent criteria remain
unchanged.

Final live results: **2/4 passed**. Counter refactor passed13.28s with the formerly
rejected shell verification returning `6`, `10`, `0`; scoped rename passed9.02s.
Class extension failed18.30s on preserved-method criteria; multi-file edit failed
8.19s at the10-round limit. This improves this one run from1/4 to2/4, but does not
establish a general model-quality improvement. Owned server PID2796119 exited0
and was confirmed absent. No owned model server remains; unrelated Ollama was
left untouched.

The next substantial open reliability item remains total-request context budgeting:
conversation compaction excludes tool declarations and output reserve. The prior
engineer8K request rejection is retained in the preceding checkpoint. Do not treat
the per-switch conversation capacity as proof that every provider request fits.
