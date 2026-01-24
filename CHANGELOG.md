# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-01-XX

### Added

- **Core Agent System**
  - Agent class with streaming event architecture
  - Event-driven processing (CONTENT, THOUGHT, TOOL_CALL_REQUEST, etc.)
  - Tool execution with confirmation workflow
  - Session management with auto-save

- **Provider System**
  - DeepSeek provider (default)
  - OpenAI-compatible base provider
  - Anthropic provider with native API
  - Ollama provider for local models
  - Provider registry for dynamic provider creation

- **Built-in Tools**
  - `read_file` - Read file contents
  - `write_file` - Write to files
  - `edit_file` - Surgical file edits
  - `ls` - List directory contents
  - `glob` - Find files by pattern
  - `grep` - Search file contents
  - `shell` - Execute shell commands
  - `web_fetch` - Fetch web pages

- **Interactive REPL**
  - Rich terminal UI with theming
  - Slash commands (/help, /quit, /clear, /tools, /chat)
  - File references with @filename syntax
  - Shell command execution with !command syntax
  - Session save/resume functionality

- **MCP Integration**
  - McpClient for single server connections
  - McpManager for multiple servers
  - Trusted/untrusted server modes
  - /mcp list and /mcp status commands

- **Extension System**
  - Extension base class
  - Entry point discovery
  - Local extension loading from ~/.henchman/extensions/
  - /extensions list command

- **Configuration**
  - Hierarchical YAML settings
  - Environment variable overrides
  - HENCHMAN.md context file discovery
  - Workspace and user-level settings

- **Documentation**
  - MkDocs site with Material theme
  - Getting started guide
  - Provider documentation
  - Tool reference
  - MCP integration guide
  - Extension development guide
  - API reference

- **Quality**
  - 100% test coverage (567+ tests)
  - Type hints throughout
  - Google-style docstrings
  - Ruff linting and formatting
  - Mypy type checking

### Changed

- Rebranded from mlg-cli to henchman-ai

[Unreleased]: https://github.com/matthew/henchman-ai/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/matthew/henchman-ai/releases/tag/v0.1.0
