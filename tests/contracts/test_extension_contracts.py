"""Contract tests for extension subsystem boundaries."""

from __future__ import annotations

import pytest

from henchman.extensions.base import Extension
from henchman.extensions.manager import ExtensionManager
from henchman.extensions.models import (
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginUpdateInfo,
    SecurityReport,
)
from tests.contracts.helpers import assert_contract_matches

# ===========================================================================
# Extension ABC protocol contract
# ===========================================================================


class TestExtensionProtocolContract:
    """Extension ABC must enforce the required abstract interface.

    Analogous to test_tool_contracts.py::test_tool_contract_methods.
    """

    def test_extension_cannot_be_instantiated_directly(self) -> None:
        """Extension should be an abstract base class."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Extension()  # type: ignore[abstract]

    def test_incomplete_extension_raises_type_error(self) -> None:
        """Subclasses missing abstract methods should not instantiate."""

        class IncompleteExtension(Extension):
            pass

        with pytest.raises(TypeError):
            IncompleteExtension()  # type: ignore[abstract]

    def test_minimal_valid_extension_satisfies_contract(self) -> None:
        """A minimal valid extension should provide all required properties."""

        class MinimalExtension(Extension):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "A minimal extension"

        ext = MinimalExtension()
        assert ext.name == "minimal"
        assert ext.version == "1.0.0"
        assert ext.description == "A minimal extension"
        assert ext.get_tools() == []
        assert ext.get_commands() == []
        assert ext.get_context() == ""

    def test_full_extension_satisfies_contract(self) -> None:
        """A fully-implemented extension should work with all methods."""

        class FullExtension(Extension):
            @property
            def name(self) -> str:
                return "full"

            @property
            def version(self) -> str:
                return "2.0.0"

            @property
            def description(self) -> str:
                return "A full extension with all hooks"

            def get_tools(self) -> list:
                return [object()]

            def get_commands(self) -> list:
                return [object()]

            def get_context(self) -> str:
                return "Additional system context here"

        ext = FullExtension()
        assert ext.name == "full"
        assert len(ext.get_tools()) == 1
        assert len(ext.get_commands()) == 1
        assert ext.get_context() == "Additional system context here"


# ===========================================================================
# ExtensionManager behavioral contract
# ===========================================================================


class TestExtensionManagerContract:
    """ExtensionManager must satisfy the registration/lookup behavioral contract."""

    def test_register_and_list_extensions(self) -> None:
        """Registered extensions should appear in list_extensions."""

        class TestExt(Extension):
            @property
            def name(self) -> str:
                return "test-ext"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Test extension"

        manager = ExtensionManager()
        ext = TestExt()
        manager.register(ext)
        names = manager.list_extensions()
        assert "test-ext" in names

    def test_unregister_extension(self) -> None:
        """Unregistered extensions should be removed."""

        class TestExt(Extension):
            @property
            def name(self) -> str:
                return "to-remove"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Will be removed"

        manager = ExtensionManager()
        manager.register(TestExt())
        assert manager.unregister("to-remove") is True
        assert "to-remove" not in manager.list_extensions()

    def test_unregister_nonexistent_returns_false(self) -> None:
        """Unregistering a non-existent extension should return False."""
        manager = ExtensionManager()
        assert manager.unregister("nonexistent") is False

    def test_get_all_tools_and_commands(self) -> None:
        """ExtensionManager should aggregate tools and commands from all extensions."""

        class ToolExt(Extension):
            @property
            def name(self) -> str:
                return "tool-ext"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Provides tools"

            def get_tools(self) -> list:
                return ["tool1", "tool2"]

        class CmdExt(Extension):
            @property
            def name(self) -> str:
                return "cmd-ext"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Provides commands"

            def get_commands(self) -> list:
                return ["cmd1"]

        manager = ExtensionManager()
        manager.register(ToolExt())
        manager.register(CmdExt())

        all_tools = manager.get_all_tools()
        assert "tool1" in all_tools
        assert "tool2" in all_tools

        all_commands = manager.get_all_commands()
        assert "cmd1" in all_commands

    def test_get_combined_context(self) -> None:
        """ExtensionManager.get_combined_context() should join contexts."""

        class CtxExt(Extension):
            @property
            def name(self) -> str:
                return "ctx-ext"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def description(self) -> str:
                return "Provides context"

            def get_context(self) -> str:
                return "Context block A"

        manager = ExtensionManager()
        manager.register(CtxExt())
        combined = manager.get_combined_context()
        assert "Context block A" in combined


# ===========================================================================
# Plugin Metadata contracts (existing)
# ===========================================================================
    """PluginMetadata should conform to the expected machine-readable shape."""

    def test_plugin_metadata_matches_contract(self, contract_suite: object) -> None:
        """A typical metadata shape matches the contract."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="test_plugin:Extension"),
            license="MIT",
            repository="https://github.com/test/plugin",
            homepage="https://test.plugin.com",
            keywords=["test", "plugin"],
        )
        assert_contract_matches(
            payload=metadata.model_dump(mode="json"),
            schema_name="extensions/plugin_metadata",
            contract_suite=contract_suite,
        )

    def test_minimal_plugin_metadata_matches_contract(self, contract_suite: object) -> None:
        """A metadata shape with minimal fields matches the contract."""
        metadata = PluginMetadata(
            name="test-plugin-minimal",
            version="0.1.0",
            description="Minimal plugin",
            author="Author",
            entry_points=PluginEntryPoints(henchman_extensions="plugin:Extension"),
        )
        assert_contract_matches(
            payload=metadata.model_dump(mode="json"),
            schema_name="extensions/plugin_metadata",
            contract_suite=contract_suite,
        )


class TestPluginSearchParamsContract:
    """PluginSearchParams should conform to the expected machine-readable shape."""

    def test_search_params_matches_contract(self, contract_suite: object) -> None:
        """A full set of search parameters matches the contract."""
        params = PluginSearchParams(
            query="test",
            page=2,
            page_size=50,
            category="tools",
        )
        assert_contract_matches(
            payload=params.model_dump(mode="json"),
            schema_name="extensions/plugin_search_params",
            contract_suite=contract_suite,
        )

    def test_default_search_params_matches_contract(self, contract_suite: object) -> None:
        """Default search parameters match the contract."""
        params = PluginSearchParams()
        assert_contract_matches(
            payload=params.model_dump(mode="json"),
            schema_name="extensions/plugin_search_params",
            contract_suite=contract_suite,
        )


class TestPluginSearchResultContract:
    """PluginSearchResult should conform to the expected machine-readable shape."""

    def test_search_result_matches_contract(self, contract_suite: object) -> None:
        """A typical search result matches the contract."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="plugin:Extension"),
        )
        result = PluginSearchResult(
            plugins=[metadata],
            total=1,
            page=1,
            page_size=20,
            query="test",
        )
        assert_contract_matches(
            payload=result.model_dump(mode="json"),
            schema_name="extensions/plugin_search_result",
            contract_suite=contract_suite,
        )


class TestPluginInstallationContract:
    """PluginInstallation should conform to the expected machine-readable shape."""

    def test_installation_matches_contract(self, contract_suite: object) -> None:
        """A typical installation matches the contract."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="plugin:Extension"),
        )
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path="/plugins/test-plugin",
            enabled=True,
        )
        assert_contract_matches(
            payload=installation.model_dump(mode="json"),
            schema_name="extensions/plugin_installation",
            contract_suite=contract_suite,
        )

    def test_installation_roundtrip(self, contract_suite: object) -> None:
        """Installation payload serialization can roundtrip cleanly."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="mod:ext"),
        )
        original = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path="/path",
            enabled=False,
        )
        payload = original.model_dump(mode="json")
        assert_contract_matches(
            payload=payload,
            schema_name="extensions/plugin_installation",
            contract_suite=contract_suite,
        )

        restored = PluginInstallation.model_validate(payload)
        assert restored == original


class TestPluginUpdateInfoContract:
    """PluginUpdateInfo should conform to the expected machine-readable shape."""

    def test_update_info_matches_contract(self, contract_suite: object) -> None:
        """A typical update info object matches the contract."""
        info = PluginUpdateInfo(
            plugin_name="test-plugin",
            current_version="1.0.0",
            latest_version="2.0.0",
        )
        assert_contract_matches(
            payload=info.model_dump(mode="json"),
            schema_name="extensions/plugin_update_info",
            contract_suite=contract_suite,
        )


class TestSecurityReportContract:
    """SecurityReport should conform to the expected machine-readable shape."""

    def test_security_report_matches_contract(self, contract_suite: object) -> None:
        """A typical security report matches the contract."""
        report = SecurityReport(
            plugin_name="test-plugin",
            passed=False,
            risk_level="high",
            warnings=["Executes arbitrary code"],
        )
        assert_contract_matches(
            payload=report.model_dump(mode="json"),
            schema_name="extensions/security_report",
            contract_suite=contract_suite,
        )

    def test_clean_security_report_matches_contract(self, contract_suite: object) -> None:
        """A clean security report matches the contract."""
        report = SecurityReport(
            plugin_name="test-plugin",
            passed=True,
            risk_level="low",
            warnings=[],
        )
        assert_contract_matches(
            payload=report.model_dump(mode="json"),
            schema_name="extensions/security_report",
            contract_suite=contract_suite,
        )
