"""Plugin metadata models for Henchman-AI plugin marketplace."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PluginPermission(str, Enum):
    """Permissions that plugins can request."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NETWORK_ACCESS = "network_access"
    SHELL_EXECUTE = "shell_execute"
    ENV_ACCESS = "env_access"
    CONFIG_ACCESS = "config_access"
    PROCESS_SPAWN = "process_spawn"


class PluginSource(str, Enum):
    """Source types for plugin installation."""

    PYPI = "pypi"
    GITHUB = "github"
    GIT = "git"
    LOCAL = "local"
    URL = "url"


class PluginCompatibility(BaseModel):
    """Compatibility requirements for a plugin."""

    henchman: str = Field(
        default=">=0.1.0",
        description="Required Henchman-AI version",
        examples=[">=0.1.0", "^1.0.0"],
    )
    python: str = Field(
        default=">=3.8",
        description="Required Python version",
        examples=[">=3.8", ">=3.9"],
    )
    os: list[str] | None = Field(
        default=None,
        description="Supported operating systems",
        examples=[["linux", "darwin"], ["windows"]],
    )


class PluginSecurity(BaseModel):
    """Security information for a plugin."""

    requires_sandbox: bool = Field(
        default=False,
        description="Whether plugin requires sandboxed execution",
    )
    permissions: list[PluginPermission] = Field(
        default_factory=list,
        description="Permissions required by the plugin",
    )
    verified_author: bool = Field(
        default=False,
        description="Whether author is verified",
    )
    code_reviewed: bool = Field(
        default=False,
        description="Whether code has been reviewed",
    )
    audit_log_required: bool = Field(
        default=True,
        description="Whether plugin activities should be audited",
    )


class PluginStats(BaseModel):
    """Statistics for a plugin."""

    downloads: int = Field(
        default=0,
        description="Total download count",
        ge=0,
    )
    rating: float | None = Field(
        default=None,
        description="Average rating (1.0-5.0)",
        ge=1.0,
        le=5.0,
    )
    reviews: int = Field(
        default=0,
        description="Number of reviews",
        ge=0,
    )
    last_updated: datetime | None = Field(
        default=None,
        description="When plugin was last updated",
    )
    first_seen: datetime | None = Field(
        default=None,
        description="When plugin was first published",
    )


class PluginEntryPoints(BaseModel):
    """Entry points configuration for a plugin."""

    henchman_extensions: str = Field(
        ...,
        description="Entry point for Henchman extension",
        examples=["my_plugin.module:MyPlugin"],
    )
    console_scripts: list[str] | None = Field(
        default=None,
        description="Console scripts provided by plugin",
    )


class PluginMetadata(BaseModel):
    """Metadata for a Henchman-AI plugin.

    This model represents plugin information stored in the registry
    and locally for installed plugins.
    """

    # Core identification
    name: str = Field(
        ...,
        description="Plugin name (must be unique)",
        min_length=2,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_-]*$",
        examples=["github-integration", "docker-tools"],
    )
    version: str = Field(
        ...,
        description="Plugin version (semver)",
        pattern=r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\.]+)?(\+[a-zA-Z0-9\.]+)?$",
        examples=["1.0.0", "2.1.0-beta.1"],
    )
    description: str = Field(
        ...,
        description="Short description of the plugin",
        min_length=10,
        max_length=500,
    )

    # Author information
    author: str = Field(
        ...,
        description="Author name or organization",
        min_length=2,
        max_length=100,
    )
    author_email: str | None = Field(
        default=None,
        description="Author email",
    )
    maintainers: list[str] = Field(
        default_factory=list,
        description="List of maintainers",
    )

    # Distribution
    license: str = Field(
        default="MIT",
        description="License identifier",
        examples=["MIT", "Apache-2.0", "GPL-3.0"],
    )
    repository: HttpUrl | None = Field(
        default=None,
        description="Source code repository URL",
    )
    homepage: HttpUrl | None = Field(
        default=None,
        description="Project homepage URL",
    )
    documentation: HttpUrl | None = Field(
        default=None,
        description="Documentation URL",
    )

    # Categorization
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for search",
        max_length=20,
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Plugin categories",
        examples=[["tools", "integration"], ["ui", "theme"]],
    )

    # Technical details
    dependencies: list[str] = Field(
        default_factory=list,
        description="Python dependencies",
        examples=[["requests>=2.25.0", "pydantic>=2.0.0"]],
    )
    compatibility: PluginCompatibility = Field(
        default_factory=PluginCompatibility,
        description="Compatibility requirements",
    )
    entry_points: PluginEntryPoints = Field(
        ...,
        description="Entry points configuration",
    )

    # Security
    security: PluginSecurity = Field(
        default_factory=PluginSecurity,
        description="Security information",
    )

    # Source information
    source: PluginSource = Field(
        default=PluginSource.PYPI,
        description="Installation source type",
    )
    source_url: str | None = Field(
        default=None,
        description="Source URL for installation",
    )
    checksum: str | None = Field(
        default=None,
        description="SHA256 checksum for verification",
        pattern=r"^[a-f0-9]{64}$",
    )

    # Statistics
    stats: PluginStats = Field(
        default_factory=PluginStats,
        description="Plugin statistics",
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When metadata was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When metadata was last updated",
    )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "name": "github-integration",
                "version": "1.0.0",
                "description": "GitHub integration for Henchman-AI",
                "author": "GitHub User",
            }
        },
    )


class PluginSearchResult(BaseModel):
    """Search result from plugin registry."""

    plugins: list[PluginMetadata] = Field(
        ...,
        description="Matching plugins",
    )
    total: int = Field(
        ...,
        description="Total number of matching plugins",
        ge=0,
    )
    page: int = Field(
        default=1,
        description="Current page number",
        ge=1,
    )
    page_size: int = Field(
        default=20,
        description="Results per page",
        ge=1,
        le=100,
    )
    query: str | None = Field(
        default=None,
        description="Search query",
    )


class PluginInstallation(BaseModel):
    """Record of an installed plugin."""

    metadata: PluginMetadata = Field(
        ...,
        description="Plugin metadata",
    )
    installed_at: datetime = Field(
        default_factory=datetime.now,
        description="When plugin was installed",
    )
    installed_version: str = Field(
        ...,
        description="Installed version",
    )
    enabled: bool = Field(
        default=True,
        description="Whether plugin is enabled",
    )
    installation_path: str | None = Field(
        default=None,
        description="Path where plugin is installed",
    )
    last_used: datetime | None = Field(
        default=None,
        description="When plugin was last used",
    )


class PluginUpdateInfo(BaseModel):
    """Information about available plugin updates."""

    plugin_name: str = Field(
        ...,
        description="Plugin name",
    )
    current_version: str = Field(
        ...,
        description="Currently installed version",
    )
    latest_version: str = Field(
        ...,
        description="Latest available version",
    )
    changelog: str | None = Field(
        default=None,
        description="Changelog for the update",
    )
    breaking_changes: bool = Field(
        default=False,
        description="Whether update contains breaking changes",
    )
    security_fixes: bool = Field(
        default=False,
        description="Whether update contains security fixes",
    )


class SecurityReport(BaseModel):
    """Security analysis report for a plugin."""

    plugin_name: str = Field(
        ...,
        description="Plugin name",
    )
    passed: bool = Field(
        ...,
        description="Whether security check passed",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Security warnings",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Security errors",
    )
    permissions_used: list[PluginPermission] = Field(
        default_factory=list,
        description="Permissions detected in code",
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        ...,
        description="Overall risk level",
    )
    scan_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When scan was performed",
    )


# Type aliases for common use cases
PluginName = str
PluginVersion = str
PluginDict = dict[str, Any]