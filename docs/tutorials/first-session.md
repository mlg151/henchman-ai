# First Session Tutorial

This tutorial walks through a realistic first Henchman-AI session in a repository.

## Goal

Inspect a project, ask a question about the codebase, and save the session for later.

## Step 1: Start the CLI

```bash
henchman
```

## Step 2: Ask for context

Use a targeted prompt such as:

```text
Summarize the architecture of this repository and point me to the most relevant modules.
```

## Step 3: Inspect available tools

Run:

```text
/tools
```

This is a quick way to see which builtin and MCP-backed tools are currently available.

## Step 4: Save the session

Run:

```text
/chat save first-session
```

You can later resume it with the matching chat resume flow.

## Next steps

- [Getting Started](../getting-started.md)
- [Agent Workflows](../guides/agent-workflows.md)
- [Configuration Guide](../configuration.md)
