"""Tests for plugin metadata models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from henchman.extensions.models import (
    PluginCompatibility,
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginPermission,
    PluginSearchResult,
    PluginSource,
    PluginStats,
    PluginUpdateInfo,
    SecurityReport,
)


class TestPluginModels:
    """Test plugin metadata models."""

    def test_plugin_metadata_basic(self) -> None:
        """Test basic PluginMetadata creation."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
        )

        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test plugin for Henchman-AI"
        assert metadata.author == "Test Author"
        assert metadata.license == "MIT"  # Default
        assert metadata.source == PluginSource.PYPI  # Default

    def test_plugin_metadata_validation(self) -> None:
        """Test PluginMetadata validation."""
        # Invalid name (starts with number)
        with pytest.raises(ValidationError):
            PluginMetadata(
                name="123-plugin",
                version="1.0.0",
                description="A test plugin for Henchman-AI",
                author="Test Author",
                entry_points=PluginEntryPoints(
                    henchman_extensions="test.module:Test",
                ),
            )

        # Invalid version (not semver)
        with pytest.raises(ValidationError):
            PluginMetadata(
                name="test-plugin",
                version="invalid",
                description="A test plugin for Henchman-AI",
                author="Test Author",
                entry_points=PluginEntryPoints(
                    henchman_extensions="test.module:Test",
                ),
            )

        # Valid with all fields
        metadata = PluginMetadata(
            name="github-integration",
            version="2.1.0",
            description="GitHub integration for Henchman-AI",
            author="GitHub User",
            author_email="user@github.com",
            license="Apache-2.0",
            repository="https://github.com/user/henchman-github",
            homepage="https://github.com/user/henchman-github",
            keywords=["github", "integration", "git"],
            categories=["integration", "tools"],
            dependencies=["requests>=2.25.0", "pydantic>=2.0.0"],
            compatibility=PluginCompatibility(
                henchman=">=0.1.0",
                python=">=3.8",
                os=["linux", "darwin"],
            ),
            entry_points=PluginEntryPoints(
                henchman_extensions="github_plugin.module:GitHubPlugin",
                console_scripts=["henchman-github=github_plugin.cli:main"],
            ),
            source=PluginSource.GITHUB,
            source_url="https://github.com/user/henchman-github",
            checksum="a" * 64,  # Fake SHA256
        )

        assert metadata.name == "github-integration"
        assert len(metadata.keywords) == 3
        assert "github" in metadata.keywords
        assert len(metadata.dependencies) == 2
        assert metadata.source == PluginSource.GITHUB

    def test_plugin_metadata_serialization(self) -> None:
        """Test PluginMetadata JSON serialization."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test.module:Test",
            ),
        )

        # Convert to dict
        data = metadata.model_dump()
        assert data["name"] == "test-plugin"
        assert data["version"] == "1.0.0"
        assert "created_at" in data
        assert "updated_at" in data

        # Convert to JSON and back
        json_str = metadata.model_dump_json()
        loaded = PluginMetadata.model_validate_json(json_str)
        assert loaded.name == metadata.name
        assert loaded.version == metadata.version

    def test_plugin_compatibility(self) -> None:
        """Test PluginCompatibility model."""
        compat = PluginCompatibility(
            henchman=">=0.1.0",
            python=">=3.9",
            os=["linux", "darwin"],
        )

        assert compat.henchman == ">=0.1.0"
        assert compat.python == ">=3.9"
        assert compat.os == ["linux", "darwin"]

        # Test defaults
        compat_default = PluginCompatibility()
        assert compat_default.henchman == ">=0.1.0"
        assert compat_default.python == ">=3.8"
        assert compat_default.os is None

    def test_plugin_stats(self) -> None:
        """Test PluginStats model."""
        now = datetime.now()
        stats = PluginStats(
            downloads=1234,
            rating=4.5,
            reviews=42,
            last_updated=now,
            first_seen=now,
        )

        assert stats.downloads == 1234
        assert stats.rating == 4.5
        assert stats.reviews == 42
        assert stats.last_updated == now

        # Test validation
        with pytest.raises(ValidationError):
            PluginStats(rating=6.0)  # > 5.0

        with pytest.raises(ValidationError):
            PluginStats(downloads=-1)  # Negative

    def test_plugin_search_result(self) -> None:
        """Test PluginSearchResult model."""
        plugin = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test.module:Test",
            ),
        )

        result = PluginSearchResult(
            plugins=[plugin],
            total=1,
            page=1,
            page_size=20,
            query="test",
        )

        assert len(result.plugins) == 1
        assert result.total == 1
        assert result.page == 1
        assert result.query == "test"

    def test_plugin_installation(self) -> None:
        """Test PluginInstallation model."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test.module:Test",
            ),
        )

        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            enabled=True,
            installation_path="/path/to/plugin",
        )

        assert installation.metadata.name == "test-plugin"
        assert installation.installed_version == "1.0.0"
        assert installation.enabled is True
        assert installation.installation_path == "/path/to/plugin"
        assert installation.installed_at is not None

    def test_plugin_update_info(self) -> None:
        """Test PluginUpdateInfo model."""
        update = PluginUpdateInfo(
            plugin_name="test-plugin",
            current_version="1.0.0",
            latest_version="2.0.0",
            changelog="Added new features",
            breaking_changes=True,
            security_fixes=True,
        )

        assert update.plugin_name == "test-plugin"
        assert update.current_version == "1.0.0"
        assert update.latest_version == "2.0.0"
        assert update.breaking_changes is True
        assert update.security_fixes is True

    def test_security_report(self) -> None:
        """Test SecurityReport model."""
        report = SecurityReport(
            plugin_name="test-plugin",
            passed=True,
            warnings=["Uses exec()"],
            errors=[],
            permissions_used=[PluginPermission.FILE_READ, PluginPermission.NETWORK_ACCESS],
            risk_level="medium",
        )

        assert report.plugin_name == "test-plugin"
        assert report.passed is True
        assert len(report.warnings) == 1
        assert report.risk_level == "medium"
        assert PluginPermission.FILE_READ in report.permissions_used

    def test_plugin_permission_enum(self) -> None:
        """Test PluginPermission enum."""
        assert PluginPermission.FILE_READ.value == "file_read"
        assert PluginPermission.FILE_WRITE.value == "file_write"
        assert PluginPermission.NETWORK_ACCESS.value == "network_access"
        assert PluginPermission.SHELL_EXECUTE.value == "shell_execute"

        # Test string conversion
        assert str(PluginPermission.FILE_READ.value) == "file_read"

    def test_plugin_source_enum(self) -> None:
        """Test PluginSource enum."""
        assert PluginSource.PYPI.value == "pypi"
        assert PluginSource.GITHUB.value == "github"
        assert PluginSource.GIT.value == "git"
        assert PluginSource.LOCAL.value == "local"
        assert PluginSource.URL.value == "url"

    def test_model_defaults(self) -> None:
        """Test that models have sensible defaults."""
        # PluginMetadata should have defaults for optional fields
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="test:Test"),
        )

        assert metadata.license == "MIT"
        assert metadata.keywords == []
        assert metadata.dependencies == []
        assert metadata.security.permissions == []
        assert metadata.stats.downloads == 0

    def test_model_immutability(self) -> None:
        """Test that PluginMetadata is immutable (frozen)."""
        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="test:Test"),
        )

        # Should not be able to modify attributes
        with pytest.raises(ValidationError):
            metadata.name = "new-name"  # type: ignore[misc]

    def test_json_encoders(self) -> None:
        """Test custom JSON encoders for datetime and HttpUrl."""
        from pydantic import HttpUrl

        metadata = PluginMetadata(
            name="test",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            repository=HttpUrl("https://github.com/test/plugin"),
            entry_points=PluginEntryPoints(henchman_extensions="test:Test"),
        )

        json_str = metadata.model_dump_json()
        data = json.loads(json_str)

        # Check that datetime is ISO format
        assert "T" in data["created_at"]  # ISO format has T separator
        # Check that HttpUrl is string
        assert isinstance(data["repository"], str)
        assert data["repository"] == "https://github.com/test/plugin"
