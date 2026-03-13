"""Tests targeting missing coverage lines in extensions modules."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.extensions.models import (
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginSource,
)
from henchman.extensions.plugin_database import PluginDatabase
from henchman.extensions.plugin_installer import PluginInstaller, _copy_repo_files
from henchman.extensions.plugin_manager import PluginManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_metadata(
    name: str = "test-plugin",
    version: str = "1.0.0",
    source: PluginSource = PluginSource.PYPI,
) -> PluginMetadata:
    """Build minimal PluginMetadata."""
    return PluginMetadata(
        name=name,
        version=version,
        description="A test plugin for coverage",
        author="Test Author",
        entry_points=PluginEntryPoints(
            henchman_extensions=f"{name}.module:Plugin",
        ),
        source=source,
    )


def _make_installation(name: str = "test-plugin", path: str | None = None) -> PluginInstallation:
    """Build a minimal PluginInstallation."""
    return PluginInstallation(
        metadata=_make_metadata(name),
        installed_at=datetime.now(),
        installed_version="1.0.0",
        enabled=True,
        installation_path=path,
    )


# ---------------------------------------------------------------------------
# plugin_database.py – lines 86-91: JSON decode error in load_installations
# ---------------------------------------------------------------------------


class TestPluginDatabaseCorruptRow:
    """Cover lines 86-91: corrupt row in DB is skipped gracefully."""

    @pytest.mark.anyio
    async def test_corrupt_row_is_skipped(self) -> None:
        """Lines 86-91: JSON decode error during load is caught and logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "plugins.db"
            db = PluginDatabase(db_path)
            await db.initialize()

            # Insert a row with invalid JSON directly via sqlite3
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "INSERT INTO plugin_installations "
                    "(name, metadata_json, installed_at, installed_version, enabled, "
                    "installation_path, last_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "bad-plugin",
                        "{invalid_json}",  # malformed
                        "2024-01-01T00:00:00",
                        "1.0.0",
                        1,
                        None,
                        None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            # load_installations should skip the corrupt row
            installations = await db.load_installations()
            assert "bad-plugin" not in installations


# ---------------------------------------------------------------------------
# plugin_installer.py – line 148: _copy_repo_files with a subdirectory
# ---------------------------------------------------------------------------


class TestCopyRepoFilesWithDirectory:
    """Cover line 148 in plugin_installer.py: shutil.copytree for subdirs."""

    def test_copy_with_subdirectory(self) -> None:
        """Line 148: directory items are copied via shutil.copytree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            source.mkdir()
            target = Path(tmpdir) / "target"
            target.mkdir()

            # Create a subdirectory (not .git) and a regular file
            subdir = source / "subpackage"
            subdir.mkdir()
            (subdir / "module.py").write_text("# module\n")
            (source / "main.py").write_text("# main\n")
            # Also create a .git directory (should be skipped)
            git_dir = source / ".git"
            git_dir.mkdir()
            (git_dir / "config").write_text("[core]\n")

            _copy_repo_files(source, target)

            # subpackage and main.py should be in target; .git should not
            assert (target / "subpackage" / "module.py").exists()
            assert (target / "main.py").exists()
            assert not (target / ".git").exists()


# ---------------------------------------------------------------------------
# plugin_installer.py – lines 344-345: unsupported plugin source raises
# ---------------------------------------------------------------------------


class TestPluginInstallerUnsupportedSource:
    """Cover lines 344-345 in plugin_installer.py."""

    @pytest.mark.anyio
    async def test_unsupported_source_raises(self) -> None:
        """Lines 344-345: RuntimeError raised for unknown source type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            installer = PluginInstaller(Path(tmpdir))

            # Build metadata with a valid source then use MagicMock with unknown source
            mock_metadata = MagicMock(spec=_make_metadata())
            mock_metadata.name = "test-plugin"
            mock_metadata.source = "totally_unknown_source"

            with pytest.raises(RuntimeError, match="Unsupported plugin source"):
                await installer.install_plugin_package(mock_metadata)


# ---------------------------------------------------------------------------
# plugin_manager.py – line 88->87: disabled plugin not loaded on init
# ---------------------------------------------------------------------------


class TestPluginManagerDisabledPlugin:
    """Cover branch 88->87: disabled plugin is not loaded during initialize."""

    @pytest.mark.anyio
    async def test_disabled_plugin_not_loaded(self) -> None:
        """Line 88->87: installation.enabled=False → _load_plugin_extension not called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(
                registry_url="https://test.example.com",
                data_dir=Path(tmpdir),
            )

            disabled_installation = _make_installation("disabled-plugin")
            disabled_installation = disabled_installation.model_copy(
                update={"enabled": False}
            )

            with patch.object(
                mgr.database,
                "load_installations",
                new=AsyncMock(return_value={"disabled-plugin": disabled_installation}),
            ), patch.object(
                mgr.database,
                "initialize",
                new=AsyncMock(),
            ), patch(
                "henchman.extensions.plugin_manager.PluginRegistryClient"
            ) as mock_reg_cls:
                mock_reg = AsyncMock()
                mock_reg_cls.return_value = mock_reg

                with patch.object(mgr, "_load_plugin_extension", new=AsyncMock()) as mock_load:
                    await mgr.initialize()

                # _load_plugin_extension should NOT be called for disabled plugin
                mock_load.assert_not_called()


# ---------------------------------------------------------------------------
# plugin_manager.py – line 106->110: close when registry_client is None
# ---------------------------------------------------------------------------


class TestPluginManagerCloseNoRegistry:
    """Cover branch 106->110: registry_client is None on close."""

    @pytest.mark.anyio
    async def test_close_with_no_registry_client(self) -> None:
        """Line 106->110: close() with registry_client=None does not raise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            # registry_client starts as None (not initialized)
            assert mgr.registry_client is None

            # Should not raise
            await mgr.close()
            assert not mgr._initialized


# ---------------------------------------------------------------------------
# plugin_manager.py – line 168: get_plugin_info when initialized
# ---------------------------------------------------------------------------


class TestPluginManagerGetPluginInfo:
    """Cover line 168 in plugin_manager.py."""

    @pytest.mark.anyio
    async def test_get_plugin_info_when_initialized(self) -> None:
        """Line 168: returns registry_client.get_plugin_info result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mock_registry = AsyncMock()
            mock_registry.get_plugin_info = AsyncMock(return_value=_make_metadata())

            mgr.registry_client = mock_registry
            mgr._initialized = True

            result = await mgr.get_plugin_info("test-plugin")

            mock_registry.get_plugin_info.assert_called_once_with("test-plugin", None)
            assert result is not None


# ---------------------------------------------------------------------------
# plugin_manager.py – line 213: permission logging
# ---------------------------------------------------------------------------


class TestPluginManagerPermissionLogging:
    """Cover line 213 in plugin_manager.py (permission list logged)."""

    @pytest.mark.anyio
    async def test_permissions_are_logged(self) -> None:
        """Line 213: logger.info called when plugin has permissions."""
        from henchman.extensions.models import PluginPermission, PluginSecurity

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mgr._initialized = True

            metadata = _make_metadata()
            metadata = metadata.model_copy(
                update={
                    "security": PluginSecurity(
                        permissions=[PluginPermission.FILE_READ, PluginPermission.NETWORK_ACCESS]
                    )
                }
            )

            mock_registry = AsyncMock()
            mock_registry.get_plugin_info = AsyncMock(return_value=metadata)
            mgr.registry_client = mock_registry

            mock_installer = AsyncMock()
            mock_installer.install_plugin_files = AsyncMock(return_value=Path(tmpdir) / "plugin")
            mgr.installer = mock_installer

            with patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker"
            ) as mock_checker:
                mock_checker.check_compatibility = AsyncMock(return_value=True)

                with patch.object(mgr.database, "save_installation", new=AsyncMock()), patch.object(
                    mgr, "_load_plugin_extension", new=AsyncMock()
                ), patch(
                    "henchman.extensions.plugin_manager.logger"
                ) as mock_logger:
                    await mgr.install_plugin("test-plugin", confirm_permissions=True)

            # Should have logged permissions
            log_calls = [str(c) for c in mock_logger.info.call_args_list]
            assert any("permissions" in c.lower() or "requires" in c.lower() for c in log_calls)


# ---------------------------------------------------------------------------
# plugin_manager.py – line 268->277: uninstall when no installation_path
# ---------------------------------------------------------------------------


class TestPluginManagerUninstallNoPath:
    """Cover branch 268->277: installation_path is None → no shutil.rmtree."""

    @pytest.mark.anyio
    async def test_uninstall_no_path(self) -> None:
        """Line 268->277: uninstall with no installation_path skips rmtree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mgr._initialized = True

            installation = _make_installation("to-remove", path=None)
            mgr.installed_plugins["to-remove"] = installation

            with patch.object(
                mgr.database, "delete_installation", new=AsyncMock()
            ), patch.object(mgr, "unregister"):
                await mgr.uninstall_plugin("to-remove")

            assert "to-remove" not in mgr.installed_plugins


# ---------------------------------------------------------------------------
# plugin_manager.py – lines 317-321: exception in update_plugin
# ---------------------------------------------------------------------------


class TestPluginManagerUpdateException:
    """Cover lines 317-321 in plugin_manager.py."""

    @pytest.mark.anyio
    async def test_update_plugin_raises_on_reinstall_failure(self) -> None:
        """Lines 317-321: exception during reinstall is logged and re-raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mgr._initialized = True

            old_installation = _make_installation("upd-plugin")
            mgr.installed_plugins["upd-plugin"] = old_installation

            latest_meta = _make_metadata("upd-plugin", version="2.0.0")
            mock_registry = AsyncMock()
            mock_registry.get_plugin_info = AsyncMock(return_value=latest_meta)
            mgr.registry_client = mock_registry

            with patch.object(
                mgr, "uninstall_plugin", new=AsyncMock()
            ), patch.object(
                mgr, "install_plugin", new=AsyncMock(side_effect=RuntimeError("install failed"))
            ), pytest.raises(RuntimeError, match="install failed"):
                await mgr.update_plugin("upd-plugin")


# ---------------------------------------------------------------------------
# plugin_manager.py – line 336->331: same version → no update
# ---------------------------------------------------------------------------


class TestPluginManagerUpdateSameVersion:
    """Cover branch 336->331: latest version == current version."""

    @pytest.mark.anyio
    async def test_no_update_when_same_version(self) -> None:
        """Line 336->331: returns None if already up-to-date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mgr._initialized = True

            current = _make_installation("same-version-plugin")
            mgr.installed_plugins["same-version-plugin"] = current

            same_meta = _make_metadata("same-version-plugin", version="1.0.0")
            mock_registry = AsyncMock()
            mock_registry.get_plugin_info = AsyncMock(return_value=same_meta)
            mgr.registry_client = mock_registry

            result = await mgr.update_plugin("same-version-plugin")

            assert result is None


# ---------------------------------------------------------------------------
# plugin_manager.py – branch 336->331: check_updates with same version
# ---------------------------------------------------------------------------


class TestPluginManagerCheckUpdatesSameVersion:
    """Cover branch 336->331 in check_updates: version is same → no update entry."""

    @pytest.mark.anyio
    async def test_no_update_when_same_version_in_check_updates(self) -> None:
        """Branch 336->331: if version == installed_version, no update entry added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PluginManager(data_dir=Path(tmpdir))
            mgr._initialized = True

            # Plugin with same version as latest
            current = _make_installation("check-plugin", path=None)
            current = current.model_copy(update={"installed_version": "1.0.0"})
            mgr.installed_plugins["check-plugin"] = current

            # Latest has the SAME version
            same_meta = _make_metadata("check-plugin", version="1.0.0")
            mock_registry = AsyncMock()
            mock_registry.get_plugin_info = AsyncMock(return_value=same_meta)
            mgr.registry_client = mock_registry

            updates = await mgr.check_updates()

            # No update should be reported for same-version plugin
            assert "check-plugin" not in updates
