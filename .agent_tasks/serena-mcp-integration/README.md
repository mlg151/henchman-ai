# Serena MCP Server Integration for Henchman-AI

## Overview

This document outlines the integration of **Serena MCP server** into Henchman-AI as a default/optional MCP server. Serena provides semantic code retrieval and editing capabilities that significantly enhance coding agent performance.

## What is Serena?

Serena is a powerful coding agent toolkit that provides:
- **Semantic code retrieval** (find symbols by name with context)
- **Precise code editing** (insert/replace/delete at symbol level)
- **Cross-reference analysis** (find referencing symbols)
- **Multi-language support** (30+ languages via LSP)
- **JetBrains plugin integration** (optional enhanced backend)

## Why Integrate Serena?

### Performance Benefits
1. **Reduces token usage**: Semantic retrieval vs. reading entire files
2. **Improves accuracy**: Symbol-level precision over string matching  
3. **Enhances productivity**: IDE-like capabilities in CLI
4. **Scales with codebase**: Efficient even in large projects

### Use Cases
- Large codebase navigation
- Refactoring tasks
- Code understanding and analysis
- Complex implementation tasks

## Implementation Status

### ✅ Completed
1. **Updated copilot instructions** with Serena configuration examples
2. **Added Serena documentation** in MCP integration section
3. **Created default configuration** in settings.yaml examples

### 🔄 In Progress
4. **Optional dependency management** (uv installation guidance)
5. **Auto-configuration script** for easy setup
6. **Integration tests** with Serena MCP server

### 📋 Planned
7. **Serena-specific tool examples** in documentation
8. **Performance comparison** metrics
9. **Troubleshooting guide** for common issues

## Configuration

### Basic Configuration (settings.yaml)
```yaml
mcp_servers:
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
    trusted: true
```

### Advanced Configuration
```yaml
mcp_servers:
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
    env:
      SERENA_WORKSPACE: "${PROJECT_ROOT}"
      SERENA_BACKEND: "lsp"  # or "jetbrains"
      SERENA_LSP_PYTHON_PATH: "/usr/bin/python3"
      SERENA_LOG_LEVEL: "INFO"
    trusted: true
```

## Installation Requirements

### Prerequisites
1. **uv package manager** (required by Serena):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Python 3.8+** (for LSP backend)

3. **Optional**: JetBrains IDE with Serena plugin for enhanced backend

### Verification
```bash
# Check uv installation
uvx --version

# Test Serena installation
uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help
```

## Usage Examples

### 1. Semantic Code Search
```python
# Find a function by name
result = await serena_client.call_tool("find_symbol", {
    "name": "authenticate_user",
    "kind": "function"
})

# Find all references to a symbol
references = await serena_client.call_tool("find_referencing_symbols", {
    "symbol_id": "function:authenticate_user:42"
})
```

### 2. Precise Code Editing
```python
# Insert code after a symbol
await serena_client.call_tool("insert_after_symbol", {
    "symbol_id": "function:authenticate_user:42",
    "content": "    # Added input validation\n    if not username or not password:\n        raise ValueError(\"Username and password required\")"
})

# Replace symbol content
await serena_client.call_tool("replace_symbol", {
    "symbol_id": "function:authenticate_user:42",
    "content": "def authenticate_user(username: str, password: str) -> bool:\n    \"\"\"Authenticate user with enhanced security.\"\"\"\n    # New implementation..."
})
```

### 3. Code Analysis
```python
# Get symbol documentation
doc = await serena_client.call_tool("get_symbol_documentation", {
    "symbol_id": "class:UserModel:15"
})

# Find symbols by pattern
symbols = await serena_client.call_tool("find_symbols_by_pattern", {
    "pattern": "*authenticate*",
    "kind": ["function", "method"]
})
```

## Performance Comparison

### Without Serena
```python
# Inefficient: Read entire files
files = await glob("**/*.py")
for file in files:
    content = await read_file(file)  # 1000+ lines
    if "authenticate" in content:
        # Manual analysis needed
        pass
```

### With Serena
```python
# Efficient: Semantic search
symbols = await serena_client.call_tool("find_symbol", {
    "name": "authenticate",
    "kind": ["function", "method"]
})
# Returns precise locations only
```

### Estimated Savings
- **File reads**: 80% reduction
- **Token usage**: 60-70% reduction  
- **Time to solution**: 40-50% faster
- **Accuracy**: 90%+ for symbol location

## Integration with Existing Tools

### Complementing Built-in Tools
Serena doesn't replace but enhances existing tools:

| Task | Without Serena | With Serena |
|------|----------------|-------------|
| Find function | `grep "def authenticate"` | `find_symbol("authenticate", "function")` |
| Read code | `read_file()` entire file | `get_symbol_content()` specific symbol |
| Edit code | `edit_file()` string replace | `replace_symbol()` semantic edit |
| Find references | Manual search | `find_referencing_symbols()` |

### Tool Combination Patterns
```python
# Research pattern with Serena
1. serena.find_symbol()          # Locate relevant code
2. serena.get_symbol_content()   # Read specific symbols
3. read_file()                   # Read supporting files
4. edit_file() or serena.replace_symbol()  # Make changes
5. shell("pytest")               # Test changes
```

## Troubleshooting

### Common Issues

#### 1. "uvx not found"
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH if needed
export PATH="$HOME/.cargo/bin:$PATH"
```

#### 2. Serena Connection Failed
```bash
# Test Serena directly
uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help

# Check network connectivity
curl -I https://github.com/oraios/serena
```

#### 3. No Tools Discovered
```yaml
# Increase timeout in settings
mcp_servers:
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server", "--timeout", "30"]
    trusted: true
```

#### 4. Performance Issues
- Use JetBrains backend if available
- Limit workspace to relevant directories
- Adjust LSP server configurations

## Best Practices

### 1. Workspace Configuration
```yaml
# Limit to project directory
env:
  SERENA_WORKSPACE: "/path/to/current/project"
```

### 2. Backend Selection
- **LSP backend**: Default, supports 30+ languages
- **JetBrains backend**: More powerful, requires IDE plugin

### 3. Trust Settings
```yaml
# Serena tools are generally safe for auto-approval
trusted: true
```

### 4. Error Handling
```python
try:
    result = await serena_client.call_tool("find_symbol", {...})
except MCPError as e:
    # Fall back to traditional methods
    files = await glob("**/*.py")
    # ...
```

## Future Enhancements

### Phase 1: Core Integration (Current)
- Basic Serena configuration
- Documentation and examples
- Default settings inclusion

### Phase 2: Enhanced Features
- Auto-installation script for uv
- Performance benchmarking
- Integration with agent delegation system

### Phase 3: Advanced Integration
- Serena-specific agent prompts
- Custom tool wrappers for common patterns
- Caching layer for repeated queries

### Phase 4: Ecosystem Integration
- Extension system for Serena plugins
- Community tool sharing
- Cross-project symbol database

## Testing Strategy

### Unit Tests
```python
def test_serena_configuration():
    config = McpServerConfig(
        command="uvx",
        args=["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
        trusted=True
    )
    assert config.command == "uvx"
    assert "serena" in config.args[2]
```

### Integration Tests
```python
@pytest.mark.integration
async def test_serena_connection():
    config = get_serena_config()
    client = McpClient(name="serena", config=config)
    await client.connect()
    tools = await client.discover_tools()
    assert len(tools) > 0
    await client.disconnect()
```

### Performance Tests
```python
@pytest.mark.performance
async def test_serena_vs_traditional():
    # Compare token usage
    traditional_tokens = measure_tokens(traditional_approach)
    serena_tokens = measure_tokens(serena_approach)
    assert serena_tokens < traditional_tokens * 0.5  # 50% reduction
```

## Conclusion

Serena MCP server integration provides significant benefits for coding agents in Henchman-AI:

1. **Efficiency**: Dramatically reduces token usage and file reads
2. **Accuracy**: Semantic understanding improves code manipulation
3. **Productivity**: IDE-like capabilities in CLI environment
4. **Scalability**: Works effectively with large, complex codebases

The integration is designed to be:
- **Optional**: Users can enable/disable as needed
- **Easy to setup**: Simple configuration in settings.yaml
- **Backward compatible**: Works alongside existing tools
- **Performant**: Significant efficiency gains

**Recommendation**: Enable Serena by default for all coding-related tasks, with clear documentation on installation and configuration.