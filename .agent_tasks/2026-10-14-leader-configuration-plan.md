# Leader configuration and shared construction

Previous goal turn was progress: live role scopes and actor dispatch passed 297
source and 896 installed-wheel tests. Goal remains active; this slice addresses
provider/model/prompt configuration consistency rather than whole-task quality.

Evidence: leader setup constructs Agent(provider=default_provider) independently
of AgentPool and ignores leader provider/model/system_prompt. Pool.get_agent of
tech_lead can produce another instance. Model-only YAML agent overrides shown in
docs fail schema validation because name/role/description are required before
runtime preset merging.

Design: normalize raw mapping overrides of known builtin roles against canonical
get_default_team() values in AgentSettings validation, before AgentConfig parsing.
Lists replace preset lists rather than unioning. Typed AgentConfig values preserve
explicit programmatic configuration. Unknown custom roles still require their
normal complete metadata. Avoid mutation of input mappings/preset instances.
Use the shared SettingsRepository and canonical .henchman files for verification.

Create the actual leader via pool.get_agent('tech_lead') and retain that same
cached instance for normal/direct execution, resets and provider/context changes.
Pool uses its existing provider resolution for saved explicit providers and
model-only overrides preserving the live endpoint/key/request defaults. No
parallel provider factory. Leader scope retains opt-in parent auto approvals.

Keep leader prompt composition canonical: nonempty runtime system_prompt wins;
otherwise configured leader.system_prompt (including intentional empty string)
wins; otherwise PromptFactory generates the existing team/environment prompt.
Legacy empty runtime argument means no runtime override (UI default is '').
Append optional leader_system_prompt to ContextConfig to preserve positional
compatibility; pool can use it for the shared leader prompt path. Setup retains
its callable interface and disables leader stall detection as before.

Default provider switches update cached/future inherited roles and retain pinned
provider/model choices, including the leader when another role is active.
Explicitly selected active agent still takes the user's selected provider/model,
including an active pinned leader. Explicit context length updates all capacities
and budgets without losing messages, scopes, prompt or saved configuration. Pool
prepares model-only replacement providers before changing references, preserving
atomic failure behavior.

Ownership: worker1 pool/leader setup/prompt factory/ContextConfig with own leader
config tests; worker2 schema known-preset override normalization and config-loader
regressions; root model-switch and actual SDK request tests, docs/package/gates.
Shared working tree: preserve others' edits. No cloud calls, staging or commits.

Verify red first: startup provider/model/prompt values, one leader instance,
custom scopes/approvals, empty prompt semantics, default switch versus explicit
active switch, failed preparation atomicity, partial YAML loading and list
replacement. Use five actual provider adapters with scripted transport to inspect
sent model/prompt/options; retain existing coding/team correctness assertions.

Integration findings: Textual/toolbar displays read the team default rather than
the acting provider. Thread actor resolution through display helpers, including
default_model and explicit context capacity; Textual explicit provider selection
must target its configured direct role. Preserve team default state semantics.

Independent review found active self/ancestor delegation now resolves the shared
cached leader and clears its parent transcript before reentry. Protect active
agent identities before any delegation reset, including the suspended gap before
the child loop starts. Release claims on success, failure and cancellation; test
balanced failed tool results and subsequent reuse. Do not revert shared caching.

The broader orchestrator test file used bare MagicMock request-accounting hooks;
17 failures occurred before model transport. Bind concrete ModelProvider budget
helpers in fixtures (no weakened production validation or semantic assertions).
The affected59 tests passed. One REPL MCP setup fixture also needed real Settings
instead of nonnumeric MagicMock context fields; the full239-test UI gate passed.

Final review extends admission to public run/run_direct: shared task ledger and
metrics must remain unchanged when a concurrent top-level call is rejected.
Reserve the root agent before its initial AGENT_STARTED yield as well as guarding
the per-orchestrator task state. Nested specialist concurrency still uses the
instance claims; do not serialize independent specialist agents accidentally.

Direct-role slash commands and REPL toolbar initially still used the leader even
after provider display helpers were corrected. Both UI command paths now share
actor resolution;18 new cases cover actual model command dispatch, context700000,
and unchanged inactive pinned leader/history/scopes/saved overrides. A session
recording fixture explicitly grants its custom test tool to the acting registry;
production root-catalog registration still grants no implicit role permission.
