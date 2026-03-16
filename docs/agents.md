# Multi-Agent Dev Team

Henchman-AI features a powerful multi-agent orchestration system that simulates a full software development team. Instead of a single general-purpose agent, Henchman coordinates specialist agents to solve complex tasks with greater precision and reliability.

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

### Tech Lead (Leader)
- **Role**: Team lead and strategist.
- **Responsibilities**: Decomposes user requirements, delegates to specialists, and ensures final quality.
- **Tools**: Read-only access to codebase, web tools, knowledge tools, shell tools, plus `delegate_task` and `ask_user`.

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
henchman --agent explorer --prompt "How do I use the FastAPI background tasks?"
henchman --agent engineer --prompt "Fix the bug in auth.py"
henchman --agent planner --prompt "Design a microservices architecture"
henchman --agent data_engineer --prompt "Create a data pipeline for user analytics"
```

### Team Management
- `/agent list`: Show all available agents and their current status.
- `/agent config <role>`: View the configuration for a specific agent.
- `/team status`: See detailed status of the whole team and recent shared decisions.
- `/team reset`: Reset the conversation history for all agents in the team.

## Agent Workspace Conventions

When working on tasks, agents follow specific conventions for organizing their work artifacts. This ensures consistency and prevents clutter in the main project directories.

### `.agent_tasks/` Directory Convention

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
3. **Include README.md** - Each task folder should have a README summarizing the goal and current status
4. **Separate source from artifacts** - Source code changes go in normal project directories; only supporting artifacts go here
5. **Reuse existing folders** - If a prior task folder exists for the same topic, reuse it instead of creating a new one
6. **Keep documentation updated** - Update the README before, during, and after work to maintain a single source of truth

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
1. **Before reading a file**: Check `recent_files` to avoid re-reading
2. **After each action**: Update working memory immediately
3. **Every 5 tool calls**: Review and prune `recent_files` (keep last 10)
4. **Task completion**: Archive working memory to `.agent_tasks/<task>/working_memory.yaml`
5. **Metrics tracking**: Count file reads and compare to baseline (target < 1.3 re-reads/task)

## Configuration

You can customize the team in your `settings.yaml`:

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
