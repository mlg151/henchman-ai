# Missing Contract: AgentPool and Scoped Registry Creation

**Severity:** Low–Medium  
**Location:** `src/henchman/agents/pool.py`

## The gap

`src/henchman/agents/pool.py` defines two critical boundary functions:

### 1. `create_scoped_registry()`

This function creates a child `ToolRegistry` containing only tools allowed
for a specific agent. **No contract test** verifies:

- That only allowed tools appear in the scoped registry
- That `extra_tools` are included
- That `auto_approve` list is respected
- That the parent registry is unmodified

### 2. `AgentPool.get_agent()`

The pool's agent-getter has a lazy-initialization contract. **No contract test**
verifies:

- That agents are lazily created on first access
- That the same agent instance is returned on subsequent accesses
- That `reset_agent()` clears history
- That `shutdown()` cleans up properly

## What's consumed

- `create_scoped_registry()` is used by `AgentPool.__init__` for every agent
  in the pool — it's a key tool-security boundary.
- `AgentPool` is the core team-management interface consumed by `Orchestrator`,
  `DelegationRunner`, and `cli/repl.py`.

## Recommended contract test

### Scoped registry contract

```python
def test_create_scoped_registry_matches_contract():
    """create_scoped_registry() must produce a registry with only allowed tools."""
    parent = ToolRegistry()
    parent.register(ReadTool())
    parent.register(WriteTool())
    parent.register(ShellTool())

    scoped = create_scoped_registry(
        parent=parent,
        allowed_tools=["read", "write"],
        extra_tools=[CustomTool()],
        auto_approve=["read"],
    )

    tool_names = {t.name for t in scoped.list_tools()}
    assert "read" in tool_names
    assert "write" in tool_names
    assert "custom_tool" in tool_names
    assert "shell" not in tool_names  # not in allowed list
```

### AgentPool contract

```python
def test_agent_pool_lifecycle_contract():
    """AgentPool should lazily create and manage agents."""
    pool = AgentPool(...)
    
    # Lazy creation
    assert "coder" not in pool.list_active_agents()
    agent = pool.get_agent("coder")
    assert "coder" in pool.list_active_agents()
    
    # Singleton
    assert pool.get_agent("coder") is agent
    
    # Reset
    pool.reset_agent("coder")
    assert pool.get_agent("coder") is not agent  # new instance
    
    # Shutdown
    pool.shutdown()
    assert pool.list_active_agents() == []
```

## Priority

Low-Medium — `create_scoped_registry` is a security-adjacent boundary.
`AgentPool` lifecycle is important for orchestrator correctness but changes
would be caught by integration tests.
