# Interrupted operation recovery

The operation journal records whether an individual tool attempt was queued,
started, completed, cancelled before dispatch, or left with an unknown outcome.
It is separate from usage accounting and workspace checkpoints. A cancelled
request does not establish that an external effect was undone.

## Lifetime and authority

`operations.persistence` defaults to `process`. Runtime attempts are correlated
for the current process; this mode does not establish durable replay authority
after restart. Select durable storage before starting work:

```yaml
operations:
  persistence: durable
```

CLI session binding uses the session data directory's sibling `ops.db`, normally
`~/.henchman/ops.db`. The SQLite operation tables coexist with the operational
and usage stores. Durable mode requires a bound session. Standalone/process-only
orchestrators use memory authority without creating a database or session file.
Changing usage persistence does not change operation persistence.

Each attempt has an operation ID and project, session, run, turn, agent and tool
call correlation. Before executing a tool, the runtime records its intent, saves
the assistant request and binding, and commits the dispatch transition. The
journal stores a digest of the arguments rather than executable arguments. Session
evidence remains subject to credential redaction. Separate specialist-turn
conversations preserve correlation when a cached specialist is reused.
Primary turns resumed by background notifications retain ordered transcript
positions, including intervening text-only turns. Later replies cannot overwrite
the requests associated with earlier tool effects.

Explicit session compaction preserves completed request/result correlation in
detached typed conversation archives and remaps the retained primary positions.
Atomic save/load and subsequent recovery retain the original operation IDs,
journal authority and consumed usage without dispatching completed tools again.
Unreconciled or corrupt bindings stop compaction before it changes the session.
Archives retain full evidence outside the active model context; this can duplicate
evidence already held in compaction summaries and is not a disk-size reduction.
Already-broken historical bindings remain errors rather than being reconstructed
from display text. Automatic runtime compaction separately preserves the original
turn evidence used by session synchronization.
Full transcript reconstruction keeps the original non-user prefix before
archived and active turns, including repeated compaction with no active turns.

Durable storage is discovered independently of the transcript's saved reference.
An older backup cannot reset known effects or authorize a second dispatch.
Missing/corrupt stores, mismatched scope, missing request correlation and conflicting
saved results stop continuation. Completed results can be reconciled into the
transcript without executing their tools again. Unknown effects require an
explicit user decision; automatic network retries are disabled inside an operation
scope. Budget/recovery control failures propagate through delegation and background
agent boundaries instead of being converted into ordinary retryable tool errors.

## User decisions

In the REPL or Textual command input:

```text
/recovery status
/recovery complete OPERATION_ID REVISION inspected external state and confirmed completion
/recovery abandon OPERATION_ID REVISION outcome remains uncertain; do not retry
/recovery retry OPERATION_ID REVISION
```

Status reports existing history without creating an empty durable store. It shows
operation IDs, revisions, states, tools and agents, plus bounded projected evidence.
Use the current revision printed by status. A concurrent resolution makes an older
revision invalid.

`complete` records the user's explicit confirmation and note. `abandon` permits
continuation while retaining the uncertain outcome. Neither rolls back effects
or proves whole-task correctness. `retry` allows one new attempt after current
registry authorization, schema, instruction and policy checks. Its permission is
runtime-owned, single-use and cannot be recreated from saved session metadata.
Changed, redacted or missing input cannot be replayed. Orchestration-only
`delegate_task` retries are refused before consuming authority; explicitly resolve
the prior attempt and issue a new task through normal orchestration instead.

If the attempt cannot save its required session binding, it does not dispatch.
A committed journal transition can still outlive a failed transcript save; retain
both files for repair rather than deleting history to obtain fresh authority.

## Evidence and limits

Output and errors are projected for known credentials before truncation. Text is
bounded to 50,000 characters with a visible truncation marker and a digest of the
full projected value. Typed output has a 65,536-character serialized recovery
bound; oversized payloads carry explicit unavailability/provenance metadata rather
than pretending that an absent value was returned. Canonical tool results outside
the journal have their own bounds. Missing structured output remains distinct from
explicit null, and error results retain failure status.

This is the tool-operation and public-orchestration recovery increment for #23.
Qualified [provider continuation profiles](providers.md#provider-continuation) now
retain opaque state and reject incompatible replay. Full background-process
restart recovery, general orchestration retry and final native qualification
remain separate gates. Stored PIDs or task records do not establish that this
process owns a live child, and the journal does not reverse external side effects.
Background task records last saved as running now load as `outcome_unknown`,
without invented stop/exit evidence. Their output remains inspectable, while
stop/wait operations refuse control without an owned child. See
[background task lifetime](tools.md#background-execution).
