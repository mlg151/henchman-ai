# Team streaming checkpoint — 2026-10-14

This advances the active coding-agent goal; it does not complete that goal.
The user's current hardware target is 16 GB RAM, CPU operation with optional GPU
acceleration. Earlier 8 GB probe records remain historical evidence.

## Implemented behavior

Nested tool and specialist events now stream through the serial orchestrator as
they arrive. Consumer demand provides backpressure; production execution no longer
buffers a complete nested tool batch before yielding its events. The old
`run_tools_and_collect` function remains a compatibility wrapper only.

Owned iterators close explicitly when a consumer disconnects, raises, cancels or
stops early. Cleanup preserves the original failure, while cleanup cancellation
still propagates when there is no earlier failure. Interrupted delegations mark
the current pending ledger attempt failed, including interruption immediately
after the delegation announcement and during a retry. No synthetic successful
completion is emitted. Parent and child message histories remain balanced.

The integration test uses the real headless renderer and orchestrator with a held
specialist provider: child progress must reach the consumer before that provider
is released. A renderer failure must close the child, prevent later provider
requests and leave no final-success event or pending delegation.

## Verification

- Final source selection: **119 passed**, 16.68 seconds. Log:
  `team-streaming-source-final.log`.
- Implementation specialist's broader focused selection: **312 passed**;
  Ruff clean across eight files and mypy clean across six files.
- Installed wheel regression selection: **397 passed**, 44.48 seconds. Log:
  `team-streaming-wheel-linux.log`. The new wheel was force-reinstalled without
  dependencies into the existing isolated Python 3.12 environment before smoke
  execution, avoiding same-version installation reuse.
- Source Python is 3.14; all executed platform checks are Linux checks. There is
  no new native Windows/macOS execution evidence.
- Existing Chroma deprecation warning remains. No full-suite claim.

Documentation updated in docs/agents.md, docs/architecture.md, CHANGELOG.md,
FEATURE_TODO.md and TODOS.md. Installed-wheel staging includes both new streaming
test files. No files staged or committed.

## Remaining work

Streaming removes nested batch retention; it does not bound all conversation
history, persisted transcripts, or the final JSON-complete event array. Provider
token/cost coverage is a separate unresolved contract; see
`2026-10-14-usage-evidence.md`.

The next local candidate is pinned Qwen3-4B-Instruct-2507 Q8_0 from ggml-org.
At this checkpoint its download is still running and no new-model quality or
memory result exists. The pinned Vulkan runtime was hash-verified and enumerated
the RTX 3090; enumeration alone does not prove accelerated model operation.
The actual host has 60 GiB RAM and a 24 GiB GPU, not the target laptop hardware.

The selected exploratory profile uses 8192 server-context tokens, 6144 agent-input
tokens and 1024 output tokens, with one server slot and four CPU threads. This
changes the profile from earlier small-model probes and must not be described as
a controlled comparison with those runs. CPU and GPU trials will share this new
profile and unchanged behavioral acceptance checks. Research recommendations and
the explicit execution profile are distinct. See `local-model-16gb-probe/` for
the pinned manifest, script, download status and eventual results.

Read-only integration mapping in `2026-10-14-local-runtime-seams.md` found that
team agents ignore the existing context.max_tokens and compaction_threshold
settings. A separate focused follow-up is addressing this propagation; it is not
part of the wheel or counts above. Managed model acquisition, application-owned
server lifecycle, whole-app memory acceptance and broader local coding quality
remain open.
