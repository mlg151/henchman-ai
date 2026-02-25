# Phase 2: Plugin Marketplace & Ecosystem - Design Document

## Overview
Extend the existing extension system to support remote plugin discovery, installation, and management. Create a plugin ecosystem that enables community contributions and easy distribution of tools, commands, and workflows.

## Current State Analysis

### Existing Extension System (`src/henchman/extensions/`)
1. **Extension ABC** - Base class with name, version, description, tools, commands, context
2. **ExtensionManager** - Discovery via entry points and directory scanning
3. **Manual registration** - Programmatic extension registration

### Limitations to Address
1. **No remote discovery** - Can't discover plugins from a central registry
2. **Manual installation** - Users must manually install Python packages
3. **No version management** - Can't check for updates or manage versions
4. **No dependency resolution** - Plugins can't declare dependencies
5. **No security scanning** - Untrusted plugins run with full privileges
6. **No ratings/reviews** - No community feedback system

## Architecture Design

### 1. Plugin Registry API
**Purpose**: Central registry for plugin discovery and metadata

**Components**:
- **Registry Server** (External service - could be GitHub-based initially)
- **Plugin Metadata Schema** - JSON schema for plugin information
- **Search API** - REST endpoints for plugin discovery
- **Statistics API** - Download counts, ratings, etc.

**Metadata Schema**:
```json
{
  "name": "plugin-name",
  "version": "1.0.0",
  "description": "Plugin description",
  "author": "Author Name",
  "license": "MIT",
  "repository": "https://github.com/user/plugin",
  "homepage": "https://plugin.example.com",
  "keywords": ["tool", "utility", "integration"],
  "dependencies": ["requests>=2.25.0", "pydantic>=2.0.0"],
  "compatibility": {
    "henchman": ">=0.1.0",
    "python": ">=3.8"
  },
  "entry_points": {
    "henchman.extensions": "plugin.module:PluginClass"
  },
  "security": {
    "requires_sandbox": false,
    "permissions": ["file_read", "network_access"]
  },
  "stats": {
    "downloads": 1234,
    "rating": 4.5,
    "reviews": 42
  }
}
```

### 2. Enhanced ExtensionManager
**Purpose**: Extend existing manager with remote capabilities

**New Features**:
- **Remote discovery** - Query registry API for plugins
- **Installation system** - Download and install from PyPI/GitHub
- **Version management** - Check for updates, upgrade/downgrade
- **Dependency resolution** - Install required dependencies
- **Security scanning** - Analyze plugin code for risks

**Interface**:
```python
class EnhancedExtensionManager(ExtensionManager):
    def __init__(self, registry_url: str = "https://registry.henchman.ai"):
        self.registry_url = registry_url
        self.installed_plugins: dict[str, PluginMetadata] = {}
    
    async def search_plugins(self, query: str, limit: int = 20) -> list[PluginMetadata]:
        """Search registry for plugins."""
    
    async def install_plugin(self, plugin_name: str, version: str | None = None) -> PluginMetadata:
        """Install plugin from registry."""
    
    async def update_plugin(self, plugin_name: str) -> PluginMetadata:
        """Update plugin to latest version."""
    
    async def uninstall_plugin(self, plugin_name: str) -> None:
        """Uninstall plugin."""
    
    async def check_updates(self) -> dict[str, UpdateInfo]:
        """Check for available updates."""
    
    def scan_security(self, plugin_name: str) -> SecurityReport:
        """Run security scan on plugin."""
```

### 3. Plugin Installation System
**Purpose**: Handle plugin installation from various sources

**Supported Sources**:
1. **PyPI** - Standard Python packages
2. **GitHub** - Git repositories (tags/branches)
3. **Local files** - For development/testing
4. **Direct URLs** - Zip/tar archives

**Installation Process**:
1. **Fetch metadata** from registry
2. **Resolve dependencies** (version conflicts, compatibility)
3. **Download package** from appropriate source
4. **Verify integrity** (checksums, signatures)
5. **Install package** using pip/uv
6. **Register extension** with ExtensionManager
7. **Update local database** of installed plugins

### 4. Security & Sandboxing
**Purpose**: Protect users from malicious plugins

**Security Layers**:
1. **Code analysis** - Static analysis for dangerous patterns
2. **Permission system** - Declarative permissions required by plugin
3. **Sandboxed execution** - Isolate plugin execution
4. **User confirmation** - Prompt for dangerous operations
5. **Audit logging** - Track all plugin activities

**Permission Types**:
- `file_read` - Read files
- `file_write` - Write files
- `network_access` - Make network requests
- `shell_execute` - Execute shell commands
- `env_access` - Read environment variables
- `config_access` - Read/write configuration

### 5. CLI Commands
**Purpose**: User interface for plugin management

**Command Structure**: `/plugin [subcommand]`

**Subcommands**:
- `/plugin search <query>` - Search for plugins
- `/plugin install <name>` - Install plugin
- `/plugin update [name]` - Update plugin(s)
- `/plugin uninstall <name>` - Uninstall plugin
- `/plugin list` - List installed plugins
- `/plugin info <name>` - Show plugin details
- `/plugin enable <name>` - Enable plugin
- `/plugin disable <name>` - Disable plugin
- `/plugin audit` - Security audit of installed plugins

### 6. Ratings & Reviews System
**Purpose**: Community feedback and quality indicators

**Components**:
- **Rating system** - 1-5 stars
- **Review comments** - Text feedback
- **Helpfulness votes** - Community moderation
- **Developer responses** - Plugin author replies
- **Report system** - Flag inappropriate content

**Integration**:
- Display ratings in search results
- Show reviews in plugin info
- Calculate trust scores
- Highlight popular/trusted plugins

## Implementation Phases

### Phase 2.1: Foundation (Week 1-2)
1. **Enhanced ExtensionManager** with remote capabilities skeleton
2. **PluginMetadata model** - Pydantic models for plugin data
3. **Basic CLI commands** - Search, install, list (mock registry)
4. **Local plugin database** - SQLite for installed plugin tracking

### Phase 2.2: Installation System (Week 3-4)
1. **PyPI integration** - Install from PyPI packages
2. **Dependency resolution** - Basic version conflict handling
3. **GitHub integration** - Install from git repositories
4. **Integrity verification** - Checksum validation

### Phase 2.3: Security & Registry (Week 5-6)
1. **Permission system** - Declarative permissions
2. **Security scanning** - Basic static analysis
3. **Registry API client** - Real registry integration
4. **Ratings system** - Basic star ratings

### Phase 2.4: Polish & Ecosystem (Week 7-8)
1. **Sandboxed execution** - Isolated plugin runtime
2. **Advanced features** - Updates, batch operations
3. **Developer tools** - Plugin creation templates
4. **Documentation** - User and developer guides

## Technical Decisions

### Registry Implementation Options
1. **GitHub-based** - Use GitHub releases/tags as registry (simplest)
2. **Custom server** - Dedicated registry service (most control)
3. **PyPI metadata** - Extend PyPI as registry (leveraging existing)

**Recommendation**: Start with GitHub-based (markdown index + releases), evolve to custom server.

### Dependency Resolution
- **Use uv/pip** - Leverage existing Python package managers
- **Isolated environments** - Consider virtual environments per plugin
- **Conflict handling** - Warn users about version conflicts

### Security Model
- **Opt-in permissions** - Plugins declare required permissions
- **User confirmation** - Prompt for dangerous permissions
- **Audit trail** - Log all plugin activities
- **Sandboxing** - Consider `restrictedpython` or custom interpreter

### Data Storage
- **SQLite database** - Installed plugins, metadata, settings
- **JSON config files** - User preferences, enabled/disabled state
- **Cache directory** - Downloaded packages, temporary files

## Success Metrics

### Quantitative
- Number of plugins in registry (target: 50+ within 6 months)
- Plugin installations per month (target: 1000+)
- User adoption rate (target: 30% of users install plugins)
- Average plugin rating (target: 4.0/5.0+)

### Qualitative
- Developer experience (easy to create and publish plugins)
- User experience (simple discovery and installation)
- Security confidence (users trust the ecosystem)
- Community engagement (active reviews and discussions)

## Risks & Mitigations

### Technical Risks
1. **Security vulnerabilities** - Malicious plugins
   - *Mitigation*: Sandboxing, code analysis, permission system
2. **Dependency hell** - Version conflicts
   - *Mitigation*: Isolated environments, clear warnings
3. **Performance overhead** - Plugin system slows down CLI
   - *Mitigation*: Lazy loading, async operations, caching

### Adoption Risks
1. **Empty registry** - No plugins initially
   - *Mitigation*: Create high-quality official plugins, incentivize early adopters
2. **Complex installation** - Users find it difficult
   - *Mitigation*: Simple commands, clear feedback, one-click installs
3. **Trust issues** - Users wary of third-party code
   - *Mitigation*: Security features, verified authors, transparency

## Next Steps

### Immediate (Week 1)
1. Create `PluginMetadata` Pydantic models
2. Extend `ExtensionManager` with remote capabilities skeleton
3. Implement basic CLI commands (`/plugin search`, `/plugin list`)
4. Create local plugin database schema
5. Design mock registry for testing

### Dependencies
- Python 3.8+ (already satisfied)
- `pydantic` for data validation (already dependency)
- `requests` or `httpx` for HTTP client (to be added)
- `sqlalchemy` or direct SQLite for database (to be evaluated)

## Conclusion

The plugin marketplace will transform Henchman-AI from a standalone tool into a platform with an ecosystem. By building on the existing extension system and adding remote discovery, installation, and security features, we can create a vibrant community of plugin developers and users.

The phased approach allows us to deliver value incrementally while ensuring security and stability at each step.

---
*Design Document Version: 1.0*  
*Status: Ready for Implementation*  
*Phase: 2.1 Foundation*