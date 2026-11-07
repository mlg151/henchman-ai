# Content checkpoints

The content checkpoint service is a foundation for [#22](https://github.com/mlg151/henchman-ai/issues/22).
It currently exposes a Python API with a POSIX restore backend. Runtime ownership
capture, CLI/REPL/Textual review controls, verification invalidation wiring, and a
Windows backend remain required. Existing Tungsten metadata snapshots are explicitly
versioned, non-restorable records; they cannot reconstruct file contents.

## Capture and review

`henchman.advanced.checkpoints.CheckpointService` requires a physical project root.
The caller declares the exact agent-owned file scope before execution and captures
the same scope afterwards. Ownership is not inferred from Git status. Include both
paths for a rename. The service leaves the Git index and unrelated dirty files alone.

```python
from pathlib import Path
from henchman.advanced.checkpoints import CheckpointService

service = CheckpointService(Path.cwd())
record = service.begin(["src/example.py"], actor="engineer")
# The caller performs its authorized edit here.
service.complete(record.checkpoint_id)
review = service.review(record.checkpoint_id)
plan = service.preview(record.checkpoint_id, decision="reject",
                       paths=["src/example.py"])
result = service.apply(plan.plan_id)
```

Preview binds a decision to exact captured content and a checkpoint revision.
`accept` records a decision without changing file contents; `reject` restores the
selected before state. Both support file selections or supported text hunk indices.
Accepted hunk identities remain visible in review. Text over 2,000 lines is still
eligible for whole-file review but does not receive a hunk diff.

Before any selected file changes, apply checks all selected paths against the
captured after state. Conflicts preserve current work. Unsupported file types,
symlinks, hardlinks, special modes, mounted filesystems and excluded paths cannot
be restored. Missing directories are not created by restore. Git ignore policy,
including native global/info excludes, applies to capture; non-Git ignore handling
is conservative. `.git`, `.henchman`, environment files and common dependency/cache
directories are excluded.

## Persistence and recovery

Versioned records live under `.henchman/tungsten/checkpoints` with private storage,
strict codecs, content digests, atomic record replacement and process locking.
Defaults are 1 MiB per file, 64 MiB total storage, 20 checkpoints and 30 days of
retention. A capture accepts 1–256 paths. Binary, oversized and known-secret files
receive an explicit non-restorable state instead of substituted content.

Restore commits its plan before changing files, retains displaced originals, and
publishes replacement files without overwriting an intervening pathname. Use
`pending_restores()` and `recover(plan_id)` after interruption. Recovery checks
staged bytes, file modes, scope, parent identities and progress before continuing.
An unresolved restore blocks later mutations and remains pinned for recovery;
there is no unconditional overwrite or reset operation.

`ReviewResult.changed_paths` and `invalidate_checks` identify affected evidence.
Callers must invalidate their verification records; this service does not yet
connect that signal to the runtime check store.

An already-open writer may continue writing a displaced inode. Its original is
retained in the private journal and located with `retained_originals(plan_id)`;
this is not a guarantee of atomic comparison against arbitrary open-handle writers.
`discard(checkpoint_id)` removes inactive capture/history and retained originals.
`prune()` removes eligible expired/completed history while active captures and
interrupted restores remain pinned. Storage exhaustion fails explicitly.

Pass the current `EvidenceRedactor` when constructing the service. Newly registered
secrets are hidden from later review and block restore. Historical private bytes
already captured remain on disk until explicit discard or retention; registering
a secret does not retroactively scrub the store.
