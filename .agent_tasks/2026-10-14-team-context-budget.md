# Team context budget checkpoint — 2026-10-14

The leader and specialists previously ignored `settings.context.max_tokens` and
`compaction_threshold`. Both construction paths now use the same small helper:
`max(1, int(max_tokens * compaction_threshold))`. This forwards an effective input
budget through the existing Agent API; no new compactor, settings schema or
provider-switching mechanism was added.

The existing settings defaults are 8000 and 0.75, yielding 6000 tokens per agent.
The configuration guide's stale 128000 default was corrected. Standalone pools
accept an optional effective ContextConfig.max_tokens; None preserves existing
automatic model resolution. Cached agents retain explicit budgets and histories
when switching providers, while automatic budgets follow model changes. Pinned
provider/model overrides keep their existing semantics.

Five new regressions were observed failing before implementation and then passing.
They cover nondefault thresholds, the schema-permitted zero threshold, lead and
specialist construction, actual runtime switching, cached and lazy agents,
preserved history, provider/model overrides and automatic budgets.

## Verification

- Implementation broader gate: **261 passed**.
- Root final focused source gate: **61 passed**, 16.85 seconds, including provider
  switching, both streaming tests, actual headless teams, wheel staging and docs.
  Log: `team-context-source-final.log`.
- Final rebuilt and force-reinstalled Linux wheel: **402 passed**, 42.33 seconds.
  Log: `team-context-wheel-linux.log`.
- Ruff clean across six root-checked files; specialist mypy clean across four
  touched implementation/test files.
- Independent read-only review found no concrete defect; its five focused cases
  passed. Existing Chroma deprecation warning remains. No full-suite or native
  macOS/Windows execution claim.

The provider-switch regression fixture exposed an inherited mock incompatibility:
its plain async generator lacked the SDK response's async close method. The test
now wraps it in the existing SDKResponse helper; production transport is unchanged.

Updated docs/configuration.md, CHANGELOG.md, FEATURE_TODO.md and TODOS.md. Staged
wheel regression selection includes the new context tests. No Git staging or
commits. Conversation budgets are not guaranteed physical model-window bounds:
tool-schema/output headroom, approximate token counting, RAG and subprocess memory
remain separate. No managed model lifecycle has been implemented in this slice.

## Local model trial status

The Qwen3-4B-Instruct-2507 Q8_0 download completed. Its 4280403520-byte length and
SHA-256 `ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1`
were verified before the `.part` file was renamed. The CPU trial is running under
the prepared 8K-context profile; it has no final quality result at this checkpoint.
See `local-model-16gb-probe/` for reports and server logs. The revised target stays
16 GB RAM with CPU operation and optional GPU acceleration.
