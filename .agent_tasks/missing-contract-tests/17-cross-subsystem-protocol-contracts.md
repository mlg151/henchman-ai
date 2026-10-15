# Missing Contract: Cross-Subsystem Protocol Contracts

**Severity:** Medium  
**Location:** Multiple protocol definitions across the codebase

## The gap

Several runtime-checkable protocols define cross-subsystem contracts. While
`test_protocol_contracts.py` covers some (`AgentProtocol`, `SettingsRepositoryLike`,
`_ChatAgent`), **the following protocols have no contract tests**:

### 1. `AgentInterface` (`src/henchman/core/agent_interface.py`)

Defines `run()`, `continue_with_tool_results()`, `submit_tool_result()`,
`clear_history()`, `record_delegation_errors()`, `get_delegation_errors()`.
**No contract test** verifies a valid agent implementation satisfies all methods.

### 2. `LspServerProtocol` (`tests/contracts/test_lsp_contracts.py`)

Defined inside the test file. **Only tested via LspService mock tests** —
no behavioral contract test for the protocol itself.

### 3. `AgentLoopRunner` (`src/henchman/agents/delegation.py`)

Defined as a `Protocol` for the orchestrator loop runner. **Tested only
implicitly** in `test_cli_boundary_contracts.py` as an inline async generator.

### 4. `ToolCallProtocol` (`src/henchman/cli/textual_widgets.py`)

Defines the interface for tool call data **used by Textual widgets**. Only
tested in `test_cli_boundary_contracts.py` with a minimal double — no formal
protocol definition or behavioral contract.

### 5. `_BranchManagerProtocol`, `_CommitAssistantProtocol`, `_WorkflowProtocol`,
    `_ReviewerProtocol`, `_CommentManagerProtocol`, `_AutofixServiceProtocol`,
    `_GitHubAppServiceProtocol`

Defined in `cli/commands/git_command.py` and `cli/commands/pull_request_command.py`.
**Tested in `test_cli_boundary_contracts.py`** only via structural subtyping
(i.e., passing doubles) — no runtime `isinstance()` checks against a
`@runtime_checkable` protocol. These are implicit structural contracts.

## What's consumed

| Protocol | Consumers |
|----------|-----------|
| `AgentInterface` | `Orchestrator`, `DelegationRunner`, `cli/repl.py` |
| `LspServerProtocol` | `LspService` in `lsp/service.py` |
| `AgentLoopRunner` | `DelegationRunner`, `Orchestrator` |
| `ToolCallProtocol` | `textual_widgets.py` UI |
| CLI Protocols | `git_command.py`, `pull_request_command.py` commands |

## Recommended improvements

### For `AgentInterface`:

Create a contract test similar to `test_tool_contracts.py`:

```python
def test_agent_interface_protocol():
    """AgentInterface must be satisfiable by a minimal implementation."""
    class MinimalAgent:
        def __init__(self):
            self.messages = []
        @property
        def provider(self): ...
        @property
        def tool_registry(self): ...
        @property
        def messages(self): ...
        @property
        def identity(self): ...
        async def run(self, user_input): ...
        async def continue_with_tool_results(self): ...
        def record_delegation_errors(self, errors): ...
        def get_delegation_errors(self): ...

    assert isinstance(MinimalAgent(), AgentInterface)
```

### For CLI Protocols:

Promote the CLI protocol types from module-private `_` naming to `@runtime_checkable`
Protocol classes, and add `isinstance` checks in contract tests.

## Priority

Medium — these are implicit contracts that break silently when the interface
changes. A `@runtime_checkable` protocol with a contract test provides a
compilation-like safety net.
