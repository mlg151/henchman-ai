# Existing edit recovery mechanisms and smallest next change

Read-only source inspection, 2026-10-14. No tools edited, tests run, model calls,
server starts or downloads. Trigger supplied by the live probe: nonunique
`old_str`, then mixed string/line parameters, then destructive stale line ranges.
This report maps existing mechanisms; it does not claim a recovery rerun passed.

## Reuse map

| Existing mechanism | Exact source | Relevant behavior / limit |
|---|---|---|
| Unique string or line edit | `src/henchman/tools/builtins/file_edit.py`: `EditFileTool`, `_FILE_EDIT_PARAMETERS`, `_validate_edit_params`, `_edit_string`, `_edit_line_range` | String target must match exactly once; zero/multiple matches fail before writes. Line mode replaces inclusive ranges, clamps end beyond EOF, and has no expected-text/version check. Both modes support `dry_run` unified diff. |
| Read current source | `src/henchman/tools/builtins/file_read.py`: `ReadFileTool`, `_read_lines_from_file` | Supports bounded `start_line`/`end_line` and `max_chars`, but returns plain unnumbered text. It does not give a content version or edit token. |
| Locate occurrences | `src/henchman/tools/builtins/grep.py`: `GrepTool` | Already supports `line_numbers` and bounded/context search options. Reuse to locate repeated identifiers, followed by a fresh source read; no second search tool needed. |
| Unified diff | `src/henchman/tools/builtins/patch_apply.py`: `PatchApplyTool`, `HunkApplier`, `_find_match` | Existing context-based hunks and dry run. Finds the first matching location, including a ±50-line search after configured fuzz; no unique-match guarantee. Direct `Path.read_text/write_text`, no shared path/atomic helpers, and multi-file updates can partially succeed. Not an automatically safer fallback for ambiguous edits. |
| Structural Python inspection | `src/henchman/tools/builtins/python_ast.py`: `PythonAstTool` | READ tool with `symbols` and `quality` actions. No semantic rename/write operation. `file_overview`, `symbol_trace`, `pattern_search` also exist for discovery. |
| Generic LSP plumbing | `src/henchman/tools/builtins/tier6_tools.py`: `LSPTool`; `src/henchman/lsp/service.py`: `LspService.request` | Register/start/stop/list/request over stdio. A configured server can receive `textDocument/rename`, but there is no dedicated prepare-rename/document synchronization/versioned WorkspaceEdit application workflow. JSON response alone does not apply an edit. |

`edit_file`'s description mentions uniqueness and either mode, but its schema only
requires `path` and `new_str`. It does not express the mode alternatives, paired
line bounds or exclusion of `old_str` with either bound. Runtime validation rejects
`old_str` plus *both* bounds; with only one bound it treats the request as string
mode and silently ignores that bound. Its multiple-match error just says the
string must be unique. It supplies neither recovery instructions nor locations.
The docs at `docs/tools.md` under `edit_file` describe string mode alone and mark
`old_str` required, so they are not a full account of the actual interface.

## Actual role availability and safety helpers

`src/henchman/agents/presets.py` is the default preset source. All five roles have
basic reads/search and code discovery. Planner/explorer/engineer/data_engineer
have `write_file`/`edit_file`; tech_lead lacks those direct write tools, but has
shell and delegates. Engineer/data_engineer additionally have `patch_apply`,
`python_ast`, `diff_view`, `pytest_run`, `lint_check` and other Python tools.
None of these presets includes `lsp`. Engineer prompts in
`src/henchman/agents/prompts.py` already say read before write, prefer surgical
edits, lint/test after changes; they do not spell out ambiguity recovery.
The small-model `EvalTestRig._create_wrapped_registry` in `evals/helpers.py`
provides basic file tools/shell/web/ask_user, not patch/LSP/Python-AST tools.
Adding a tool to production does not automatically make this probe exercise it.

`src/henchman/tools/security.py::validate_path`, `atomic_read`, `atomic_write`
are reused by `edit_file`. Atomic replacement protects against a partially written
file, **not stale edit intent**: the read's stat comparison does not reject a
change, and write uses a predictable sibling `.tmp` path with no compare-and-swap
or operation-wide lock. `src/henchman/utils/file_lock.py::FileLock` exists if a
future coordinated write needs locking. Neither alone proves that the model's
previous read still matches the content being replaced. Do not describe existing
helpers as lost-update protection or semantic Python validation.

## Recommended bounded next slice

Improve **the existing `edit_file` contract and failure guidance first**:

1. Clearly describe exactly one target mode in the tool/schema property text:
   `old_str` plus `new_str`, or both fresh line bounds plus `new_str`. String mode
   should use an exact, unique block including enclosing function/context when
   a short identifier repeats. Avoid adding a parallel rename/edit tool.
2. On zero/multiple string matches, preserve the failed result and unchanged file;
   instruct a fresh `read_file`/numbered `grep`, then retry with sufficient unique
   context. Explicitly say not to guess line ranges or mix modes. On mixed or
   incomplete parameters, show the valid alternatives. Reject either stray line
   bound alongside string mode rather than silently ignoring it.
3. Remind that successful earlier edits can shift line positions; reread before
   switching to line mode, and use existing dry-run preview. Keep preview advisory:
   it does not reserve a file version. Update the nearby tool docs to match.
4. Add deterministic tool contracts for unchanged bytes on these failures and a
   scripted read→ambiguous failure→fresh read→unique successful edit sequence,
   then rerun the same live rename oracle with unchanged acceptance criteria.

This is guidance and parameter-contract repair. Mandatory fresh-read tracking,
expected-content hashes, rejecting all line edits without versions, forcing
Python parse checks, or detecting destructive semantic changes are **additional
write policies**, not fixes implied by JSON Schema. They need explicit design and
coverage for legitimate partial/broken-file repair and concurrent editors. A
provider-facing `oneOf` could express mode selection, but must be checked against
existing provider tool-schema portability; schema text plus runtime validation is
the smaller immediately reusable surface. Guidance may improve recovery, but
cannot guarantee a weak model stops making bad edits.

## Exact regression anchors

- `tests/tools/test_file_tools.py::TestEditFileTool`: existing success, not-found,
  multiple matches, line range, invalid/excessive range, both/no modes, dry-run,
  newline and traversal cases. `TestReadFileTool` covers range reads. There is no
  `tests/tools/test_file_edit.py`.
- `tests/tools/test_patch_apply.py`: patch parser/applier behavior.
- `tests/tools/test_security_extended.py`: `atomic_read`/`atomic_write` contracts.
- `tests/agents/test_presets.py`: actual scoped role tools.
- `tests/tools/test_tier6_lsp_schedule_tools.py`,
  `tests/contracts/test_lsp_contracts.py`: existing generic LSP contracts.
- `tests/testing/test_edit_eval_contract.py`: independent rename oracle; retain
  its bad-rename rejection while improving recovery. `tests/e2e/test_coding_loop.py`
  and `tests/e2e/test_headless_team.py` exercise real file tools through agent loops.
