# Multi-Agent Dev Team

Henchman-AI coordinates specialist agents for planning, discovery, implementation,
and verification. Per-role tool scopes and runtime policies govern execution;
completion metadata records observed outcomes.

## Architecture

At the core of the system is the **Orchestrator**, which manages a team of specialist agents.

```mermaid
graph TD
    User([User]) --> TL[Tech Lead]
    TL -- delegate_task --> Specialists[Specialist Agents]
    Specialists -- results --> TL
    TL -- final response --> User
    
    subgraph "Specialists"
        Planner
        Explorer
        Engineer
        DataEngineer[Data Engineer (data_engineer)]
    end
    
    subgraph "Communication"
        EB[EventBus]
        Agents -- delegate_task --> EB
        EB -- events --> Agents
    end
```

### Key Components

- **Orchestrator**: The brain of the team. It receives user input, delegates to specialists, and synthesizes results.
- **EventBus**: A pub/sub system that allows agents to communicate with each other asynchronously.
- **AgentPool**: Manages the lifecycle and instantiation of agents, providing scoped tool access and role-specific prompts.

## Agent Roster

All default roles include the existing read-only `file_overview`, `symbol_trace`,
and `pattern_search` tools when registered in the runtime. Custom tool allowlists
remain explicit; they are not broadened automatically.

Generated role prompts ask agents to search for existing implementations and tests
before introducing new functionality, inspect candidates and callers, and carry
file/symbol references and reuse decisions into delegation handoffs. They also ask
the lead to assign ownership, review integrated changes, and verify test/lint/type
evidence. These are workflow instructions, not proof of model compliance. Complete
team-task evaluations and packaged smell/duplication analysis remain tracked in
[`FEATURE_TODO.md`](../FEATURE_TODO.md#python-development-and-team-leadership).

The harness [automatically runs Black](tools.md#automatic-python-formatting) on
observed Python changes before tool results return. Specialists can spend their
calls on implementation, lint, types, tests and review; formatting failures remain
explicit failures. Background shell/Python jobs require
`code_format` after completion; their launch receipts explain this. See
[background execution](tools.md#background-execution).

The opt-in [package artifact evaluation](../evals/README.md#offline-package-lifecycle-evaluation)
uses the production team with ordered inspection, engineer edit attribution and a
returned specialist review of final source. Its independent offline build,
installation and CLI checks are evaluator evidence; agent-side installation and
hosted CI execution remain unverified.

### Tech Lead (Leader)
- **Role**: Team lead and strategist.
- **Responsibilities**: Decomposes user requirements, delegates to specialists, and ensures final quality.
- **Tools**: File reading and discovery, web, knowledge, git and shell tools, plus `delegate_task`, `ask_user` and `verify_plan_execution`. File edits are delegated by default. Shell, git, knowledge and verification tools can execute commands or change state and follow normal approval policies.

### Planner
- **Role**: Architecture and task decomposition specialist.
- **Responsibilities**: Creates technical plans, designs architectures, breaks down tasks, and writes design docs in `.agent_tasks/`.
- **Tools**: Basic file tools, file edit tools (for design docs), git tools, web tools, knowledge tools.

### Explorer
- **Role**: Research and documentation specialist.
- **Responsibilities**: Researches, analyzes, and documents findings. Creates documentation in `.agent_tasks/`.
- **Tools**: Basic file tools, file edit tools (for documentation), git tools, web tools, knowledge tools, shell tools.

### Engineer
- **Role**: Code implementation and testing specialist.
- **Responsibilities**: Implements code, runs tests, debugs, and follows project conventions.
- **Tools**: Full Python development toolset including basic file tools, file edit tools, git tools, shell tools, and all Python development tools.

### Data Engineer
- **Role**: Data pipeline and infrastructure specialist.
- **Responsibilities**: Builds data pipelines, Spark/Pandas transformations, AWS infrastructure, and Airflow orchestration.
- **Tools**: Basic file tools, file edit tools, git tools, web tools (for cloud research), shell tools, and full Python development toolset.

## Usage

### Interactive Mode
By default, you talk to the **Tech Lead**. They will automatically delegate tasks to specialists as needed.

```bash
henchman
❯ Implement a new authentication module
```

### Direct Targeting
You can talk to a specific agent directly using the `/agent` command:

```
❯ /agent engineer Fix the indentation in auth.py
❯ /agent explorer Research FastAPI background tasks
❯ /agent planner Design a new authentication system
❯ /agent data_engineer Create a data pipeline for user analytics
```

Or from the command line:

```bash
henchman chat --agent explorer --prompt "How do I use the FastAPI background tasks?"
henchman chat --agent engineer --prompt "Fix the bug in auth.py"
henchman chat --agent planner --prompt "Design a microservices architecture"
henchman chat --agent data_engineer --prompt "Create a data pipeline for user analytics"
```

### Team Management
- `/agent list`: Show all available agents and their current status.
- `/agent config <role>`: View the configuration for a specific agent.
- `/team status`: See detailed status of the whole team and recent shared decisions.
- `/team reset`: Reset the conversation history for all agents in the team.

## Agent Workspace Conventions

When working on tasks, agents follow specific conventions for organizing their work artifacts. This ensures consistency and prevents clutter in the main project directories.

### `.agent_tasks/` Directory Convention

Default prompts return short discovery and review findings directly in the
handoff. They create supporting artifacts when explicitly requested or when
substantial analysis, long-running work or a durable handoff needs them. A small
lookup does not require a task folder, scratch probe or README solely for process.
Explicit user and project documentation requirements take precedence.

All non-source artifacts (analysis scripts, design docs, research notes, validation reports, scratch files) **MUST** be placed inside the `.agent_tasks/` directory in the project root. **NEVER** create these files in the repo root or alongside source code.

#### Directory Structure
```
.agent_tasks/
├── <task-slug>/            # One folder per task or project
│   ├── README.md           # Task description, status, and findings
│   ├── analysis/           # Analysis scripts, notebooks, data exploration
│   ├── docs/               # Design docs, RFCs, research notes
│   └── scripts/            # Utility/validation/automation scripts
```

#### Rules

1. **Create `.agent_tasks/` if it doesn't exist** - Agents should create this directory when needed
2. **Use descriptive task slugs** - Short, descriptive names (e.g., `elo-parameter-tuning`, `api-migration`)
3. **Summarize substantial tasks** - Use a README for meaningful task state, findings and blockers
4. **Separate source from artifacts** - Source code changes go in normal project directories; only supporting artifacts go here
5. **Reuse existing folders** - If a prior task folder exists for the same topic, reuse it instead of creating a new one
6. **Keep documentation useful** - Update durable notes when findings or handoff state change; repeated updates around every small action are not required by default

#### Agent Responsibilities
- **Planner**: Creates design documents and architectural plans in `.agent_tasks/<task>/docs/`
- **Explorer**: Stores research findings and analysis in `.agent_tasks/<task>/analysis/` and `.agent_tasks/<task>/docs/`
- **All Agents**: Should follow this convention for any non-source artifacts they create

### Working Memory Management

Agents maintain working memory to optimize performance and reduce redundant file reads:

#### Working Memory Template
```yaml
working_memory:
  current_task: "string describing active task"
  task_objectives: ["specific", "goals", "for", "task"]
  recent_files:
    - path: "file/path.py"
      purpose: "why this file was read"
      timestamp: "ISO timestamp"
      lines_read: "start_line-end_line or 'full'"
      key_insights: ["important", "findings", "from", "file"]
  active_context:
    project_structure: "brief description"
    relevant_patterns: ["patterns", "from", "knowledge", "graph"]
    constraints: ["known", "limitations"]
    dependencies: ["required", "components"]
  decisions_made:
    - decision: "key decision"
      rationale: "why this decision"
      impact: "high|medium|low"
  completed_steps: ["step1", "step2"]
  next_actions:
    - action: "next step"
      priority: "high|medium|low"
      estimated_effort: "time estimate"
  insights_gained: ["new", "learnings"]
  problems_encountered:
    - problem: "issue encountered"
      status: "open|in_progress|resolved"
      resolution: "how it was fixed"
```

#### Memory Update Protocol

Use durable working-memory records for substantial work, useful handoffs or
explicit project requirements. Short lookups can return their findings directly.
When maintaining a durable record:

1. **Before reading a file**: Check `recent_files` to avoid re-reading
2. **After meaningful findings**: Update working memory when task state changes
3. **Every 5 tool calls**: Review and prune `recent_files` (keep last 10)
4. **Task completion**: Archive to `.agent_tasks/<task>/working_memory.yaml` when a durable handoff needs it or project instructions require it
5. **Metrics tracking**: Count file reads and compare to baseline (target < 1.3 re-reads/task)

## Headless team execution

Default planning and handoffs scale to the task. A small scoped change can use an
inline plan; saved trackers and knowledge updates support explicit requirements
or useful durable coordination. Related changes and their required checks stay
together under one owner when the execution budget permits. Specialists share
concise decisions, findings and meaningful progress rather than a mandatory
numbered reasoning transcript. Internal reasoning stays private.

Default guidance asks the owner to complete coherent related edits before running
required checks against the final relevant state. Explicit user or project rules
take priority, including checks after each edit, named tools, environments and
verification scope. Returned specialist evidence can be reused only when it
identifies the actual check, relevant environment and scope, and observed result,
and still covers the current relevant state and requirements. Missing, failed,
invalidated or insufficiently evidenced checks must run; a handoff alone does not
invalidate otherwise sufficient evidence. Required independent review still needs
a reviewer distinct from the implementer.

Once assigned criteria are met, specialists should return their final handoff
promptly. Additional checks should resolve unmet criteria or concrete risks.
Advice and response-only work based on supplied context do not require ceremonial
checks unless the user or project requires them. These are prompt instructions,
not runtime enforcement or proof of model compliance. No paired live evaluation
of this guidance has run yet; task success, latency and industry-leading
performance remain unestablished by these changes.

Final handoffs retain the structured status, modified files, checks and observed
results, blockers and next-agent context. Reviews include a clear verdict and
concrete findings or uncertainty; concise reporting does not reduce required
inspection, reuse, verification or review coverage. Requested detailed reports and
project documentation rules still apply. These defaults do not alter custom
system prompts or execution limits.

`henchman chat --prompt "..."` uses the configured orchestrator in text, `json`,
`stream-json`, and `json-complete` modes. The lead can delegate research,
implementation, and review using the same provider settings and tool policies as
interactive work. `--agent engineer` selects that specialist directly in every
output format.

Specialist events flow to the consumer as they are produced; a slow consumer
pauses the nested producer. Serial delegation no longer retains an entire tool
batch of events. Closing the stream interrupts remaining work, closes active
provider streams, and records interrupted delegations as failed.

JSON events include `source_agent` when available, so tool-call identifiers can
be correlated within each agent. Intermediate provider finishes are suppressed;
one final `finished` event describes the whole run. Only the outer completion
with `scope: "run"` supplies the final outcome. Specialist failures remain
visible, and a later successful retry can recover. Failed, stalled, exhausted,
or missing outer completion produces unsuccessful execution.

Each agent has a finite tool-round budget; delegation depth and specialist call
limits apply separately. A completed round records only that agent's tool calls.
Task correctness still requires suitable artifact and test evidence; runtime
completion retains `task_verified: false`.

Each specialist receives its current execution limits with the delegation input.
It also receives the full original user request as mission context, including
requirements beyond the status board's 500-character goal preview. The delegated
task and its completion criteria define that specialist's assignment; the mission
provides context for dependencies and constraints. The normal request-capacity
checks still apply to this context. Long required input fails explicitly when it
cannot fit rather than silently losing the end of the mission.

The delegation call limit counts individual requested tool calls, including failed
calls, and is checked after each whole batch; a batch can exceed the limit.
Reaching it stops execution before another model response. The separate tool-round
limit counts batches and still allows a final answer after the last permitted
batch. Specialists should reserve capacity for verification and their final
handoff. Limits are recomputed for each execution, including cached agents.

Default verification guidance accepts available structured tools such as
`pytest_run` and `lint_check`, as well as project commands through `shell`.
Explicit user or project requirements determine the tool, environment and checks
to use. A successful collection or dry run does not establish passing tests;
handoffs must name the checks and observed results, including failures or
unavailable checks. Verification applies to the final relevant changes.

Structured handoff fields are read from the specialist's final assistant message,
with each field on its own line. Interim reports and the appended tool-error
digest remain visible in the full summary but do not replace those fields.
Cached agents clear their diagnostic buffer when a new execution starts, so
previous delegation errors do not appear as failures of a later retry. Tool
continuations keep the current execution's errors, and previously returned
handoffs remain unchanged. Clearing conversation history also resets diagnostics.
Blank blockers and explicit absence markers such as `BLOCKERS: none` do not
invalidate successful actions. Real blockers, reported failure and runtime
failure still prevent a successful handoff. A failed handoff is not proof that
the specialist made no tool calls.

## Configuration

You can customize the team in `.henchman/settings.yaml`:

```yaml
agents:
  # Max recursive delegation depth
  max_delegation_depth: 3
  
  # Agent overrides
  agents:
    tech_lead:
      model: "gpt-4o"  # Give the tech lead a more powerful model
      enabled: true
    engineer:
      model: "gpt-4o"  # Give the engineer a more powerful model for coding
    explorer:
      enabled: true
    planner:
      enabled: true
    data_engineer:
      enabled: true
    security_auditor:  # Add a custom specialist
      name: "Security Auditor"
      role: "security_auditor"
      description: "Audits code for security"
      tools: ["read_file", "grep"]
      can_delegate_to: ["explorer"]
```

Builtin roles accept partial overrides; omitted fields retain the canonical role
preset. Explicit lists such as `tools` and `auto_approve` replace the preset lists.
Custom roles require their own `name`, `role`, and `description`, as above.

The leader uses the same cached agent and configuration path as specialists.
Setting a role's `provider` selects that provider's saved connection settings;
setting only `model` inherits the current default provider's connection and request
options without changing its default model. See
[provider configuration](providers.md#provider-selection-and-credentials).

For leader prompts, a nonempty runtime `system_prompt` takes precedence, followed
by the role's configured `system_prompt`, then the generated team/environment
prompt. An explicit empty configured prompt suppresses the generated prompt; an
empty runtime argument retains the configured/generated behavior.

When switching the team default while another role is active, pinned provider
choices and model-only overrides remain in effect. Explicit `/model set` selection
also switches the active agent, including a pinned role, for the current session.
It preserves conversation history and leaves saved role overrides unchanged.
An explicit `--context-length` updates the live team's capacities and budgets;
see [context configuration](configuration.md#context-management-settings).
REPL and Textual provider/model labels describe the acting agent, which may differ
from the team default. The REPL token percentage uses its explicit context
capacity when configured.

Delegation reserves the target agent before resetting its previous task history.
An already running or reserved instance cannot receive another delegation,
including self-delegation and delegation back to a waiting ancestor. The caller
receives a failed tool result and can choose another specialist. Reservations
release when execution finishes, fails, or is cancelled.
An orchestrator accepts one top-level `run` or `run_direct` at a time because its
ledger and metrics belong to that task. Concurrent top-level calls fail before
changing those records. Independent specialists can still execute concurrently
within a task.


### Tool scopes and late registration

The leader and specialists each use their configured `tools` allowlist for
provider declarations, scoped discovery and execution. Custom lists are explicit:
including a tool in the runtime catalog grants no access to an agent that omits
it. This applies to normal orchestration and fallback CLI execution.

Allowed tools registered later, including MCP tools, become available to existing
agents. Subsequent lookups and calls reflect parent removal or replacement.
An MCP tool must be named in the role's allowlist; registering a new server does
not expand custom lists. `/tools` shows the registered runtime catalog, while an
agent's `tool_search` searches its current scope.

An agent whose scope includes `delegate_task` can explicitly search enabled team
roles with `tool_search(scope="team", query="<exact tool name>")`. This reports
live role capabilities without creating specialist agents or provider clients.
It preserves local execution scopes and schema priorities. A missing local tool
may be available to a specialist; retain the user's named tool, environment and
check requirements in that specialist's brief. Capability lookup is separate from
execution approval, provider readiness and active-agent admission. See
[tool discovery](tools.md#tools).

The leader preserves the runtime's existing automatic approvals and its configured
`auto_approve` entries. Specialist automatic approvals remain role-specific.
All roles follow the current confirmation handler and plan-mode restrictions;
plan mode is checked before automatic approval. Approving an excluded tool name
cannot add it to the role's allowlist.
