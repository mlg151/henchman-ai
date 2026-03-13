"""Comprehensive tests for plugin_installer, plugin_registry_client, plugin_manager, plugin_compatibility."""

from __future__ import annotations

import io
import sys
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.extensions.models import (
    PluginCompatibility,
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginSource,
)
from henchman.extensions.plugin_compatibility import PluginCompatibilityChecker
from henchman.extensions.plugin_installer import (
    PluginInstaller,
    _copy_dir_contents,
    _copy_local_path,
    _copy_repo_files,
    _download_archive,
    _extract_archive_file,
    _git_clone_to_dir,
    _install_pypi_package,
    _parse_github_url,
    _run_git_clone_subprocess,
    _run_pip_deps_subprocess,
    _run_pip_subprocess,
    _tar_open_mode,
)

# ---------------------------------------------------------------------------
# Helper for building minimal PluginMetadata
# ---------------------------------------------------------------------------


def _make_metadata(
    name: str = "my-plugin",
    version: str = "1.0.0",
    source: PluginSource = PluginSource.PYPI,
    source_url: str | None = None,
) -> PluginMetadata:
    """Create a minimal valid PluginMetadata instance.

    Args:
        name: Plugin name.
        version: Plugin version.
        source: Installation source type.
        source_url: Optional source URL.

    Returns:
        PluginMetadata instance.
    """
    return PluginMetadata(
        name=name,
        version=version,
        description="A test plugin for Henchman-AI",
        author="Test Author",
        entry_points=PluginEntryPoints(henchman_extensions="my_plugin:MyPlugin"),
        source=source,
        source_url=source_url,
    )


# ---------------------------------------------------------------------------
# PluginCompatibilityChecker tests
# ---------------------------------------------------------------------------


class TestPluginCompatibilityChecker:
    """Tests for PluginCompatibilityChecker."""

    def _make_meta_with_compat(
        self,
        henchman: str = ">=0.1.0",
        python: str = ">=3.8",
        os_list: list[str] | None = None,
    ) -> PluginMetadata:
        """Create metadata with specific compatibility settings.

        Args:
            henchman: Henchman version specifier.
            python: Python version specifier.
            os_list: List of supported OS names.

        Returns:
            PluginMetadata with given compatibility.
        """
        return PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="p:P"),
            compatibility=PluginCompatibility(
                henchman=henchman,
                python=python,
                os=os_list,
            ),
        )

    @pytest.mark.anyio
    async def test_compatible_plugin(self) -> None:
        """Plugin with broad version specifiers is compatible."""
        meta = self._make_meta_with_compat(henchman=">=0.1.0", python=">=3.8")
        result = await PluginCompatibilityChecker.check_compatibility(meta)
        assert result is True

    @pytest.mark.anyio
    async def test_incompatible_henchman_version(self) -> None:
        """Plugin requiring future Henchman version is incompatible."""
        meta = self._make_meta_with_compat(henchman=">=999.0.0")
        result = await PluginCompatibilityChecker.check_compatibility(meta)
        assert result is False

    @pytest.mark.anyio
    async def test_incompatible_python_version(self) -> None:
        """Plugin requiring future Python version is incompatible."""
        meta = self._make_meta_with_compat(python=">=999.0.0")
        result = await PluginCompatibilityChecker.check_compatibility(meta)
        assert result is False

    @pytest.mark.anyio
    async def test_compatible_current_os(self) -> None:
        """Plugin supporting current OS is compatible."""
        platform_map = {"linux": "linux", "win32": "windows", "darwin": "macos"}
        current_os = platform_map.get(sys.platform, sys.platform)
        meta = self._make_meta_with_compat(os_list=[current_os])
        result = await PluginCompatibilityChecker.check_compatibility(meta)
        assert result is True

    @pytest.mark.anyio
    async def test_incompatible_os(self) -> None:
        """Plugin not supporting current OS is incompatible."""
        # Use an OS that's definitely not the current one
        current = sys.platform
        other_os_list = []
        if current != "linux":
            other_os_list = ["linux"]
        elif current != "win32":
            other_os_list = ["windows"]
        if other_os_list:
            meta = self._make_meta_with_compat(os_list=other_os_list)
            result = await PluginCompatibilityChecker.check_compatibility(meta)
            assert result is False

    @pytest.mark.anyio
    async def test_invalid_version_specifier(self) -> None:
        """Invalid version specifier returns False (incompatible)."""
        meta = self._make_meta_with_compat(henchman="not_a_valid_specifier")
        result = await PluginCompatibilityChecker.check_compatibility(meta)
        assert result is False

    def test_check_henchman_compatibility_true(self) -> None:
        """Broad henchman spec is compatible."""
        result = PluginCompatibilityChecker._check_henchman_compatibility(">=0.1.0")
        assert result is True

    def test_check_henchman_compatibility_false(self) -> None:
        """Very high henchman spec is incompatible."""
        result = PluginCompatibilityChecker._check_henchman_compatibility(">=999.0.0")
        assert result is False

    def test_check_python_compatibility_true(self) -> None:
        """Broad python spec is compatible."""
        result = PluginCompatibilityChecker._check_python_compatibility(">=3.8")
        assert result is True

    def test_check_python_compatibility_false(self) -> None:
        """Very high python spec is incompatible."""
        result = PluginCompatibilityChecker._check_python_compatibility(">=999.0.0")
        assert result is False

    def test_check_os_compatibility_linux(self) -> None:
        """OS check returns correct result for linux."""
        with patch("sys.platform", "linux"):
            result = PluginCompatibilityChecker._check_os_compatibility(["linux"])
        assert result is True

    def test_check_os_compatibility_windows(self) -> None:
        """OS check returns correct result for windows."""
        with patch("sys.platform", "win32"):
            result = PluginCompatibilityChecker._check_os_compatibility(["windows"])
        assert result is True

    def test_check_os_compatibility_macos(self) -> None:
        """OS check returns correct result for macos."""
        with patch("sys.platform", "darwin"):
            result = PluginCompatibilityChecker._check_os_compatibility(["macos"])
        assert result is True

    def test_check_os_compatibility_mismatch(self) -> None:
        """OS check returns False when current OS not in list."""
        with patch("sys.platform", "linux"):
            result = PluginCompatibilityChecker._check_os_compatibility(["windows"])
        assert result is False

    def test_check_os_compatibility_unknown_platform(self) -> None:
        """OS check handles unknown platforms gracefully."""
        with patch("sys.platform", "freebsd"):
            result = PluginCompatibilityChecker._check_os_compatibility(["linux", "windows"])
        assert result is False


# ---------------------------------------------------------------------------
# PluginInstaller module-level helper tests
# ---------------------------------------------------------------------------


class TestPluginInstallerHelpers:
    """Tests for module-level helpers in plugin_installer."""

    @pytest.mark.anyio
    async def test_run_pip_subprocess_success(self, tmp_path: Path) -> None:
        """pip subprocess success does not raise."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Should not raise
            await _run_pip_subprocess("package==1.0.0", str(tmp_path))

    @pytest.mark.anyio
    async def test_run_pip_subprocess_failure(self, tmp_path: Path) -> None:
        """pip subprocess failure raises RuntimeError."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to install package"):
                await _run_pip_subprocess("bad-package==0.0.0", str(tmp_path))

    @pytest.mark.anyio
    async def test_run_pip_subprocess_failure_no_stderr(self, tmp_path: Path) -> None:
        """pip subprocess failure with no stderr raises with Unknown error."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", None))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to install package"):
                await _run_pip_subprocess("bad-package", str(tmp_path))

    def test_copy_dir_contents(self, tmp_path: Path) -> None:
        """_copy_dir_contents copies files and dirs."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("hello")
        subdir = src / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("world")

        dst = tmp_path / "dst"
        dst.mkdir()
        _copy_dir_contents(src, dst)

        assert (dst / "file.txt").read_text() == "hello"
        assert (dst / "subdir" / "nested.txt").read_text() == "world"

    @pytest.mark.anyio
    async def test_install_pypi_package_success(self, tmp_path: Path) -> None:
        """_install_pypi_package succeeds with mocked pip."""
        metadata = _make_metadata(source=PluginSource.PYPI)
        target = tmp_path / "target"
        target.mkdir()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await _install_pypi_package(metadata, target)

        assert result == target

    @pytest.mark.anyio
    async def test_install_pypi_package_failure(self, tmp_path: Path) -> None:
        """_install_pypi_package raises RuntimeError on pip failure."""
        metadata = _make_metadata(source=PluginSource.PYPI)
        target = tmp_path / "target"
        target.mkdir()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"pip error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to install from PyPI"):
                await _install_pypi_package(metadata, target)

    @pytest.mark.anyio
    async def test_run_git_clone_success(self, tmp_path: Path) -> None:
        """git clone subprocess success does not raise."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await _run_git_clone_subprocess(
                "https://github.com/user/repo.git", "main", str(tmp_path)
            )

    @pytest.mark.anyio
    async def test_run_git_clone_failure(self, tmp_path: Path) -> None:
        """git clone subprocess failure raises RuntimeError."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"clone failed"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to clone repository"):
                await _run_git_clone_subprocess("bad-url", None, str(tmp_path))

    @pytest.mark.anyio
    async def test_run_git_clone_failure_no_stderr(self, tmp_path: Path) -> None:
        """git clone subprocess failure with no stderr raises with Unknown error."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", None))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to clone repository"):
                await _run_git_clone_subprocess("bad-url", None, str(tmp_path))

    def test_copy_repo_files_skips_git(self, tmp_path: Path) -> None:
        """_copy_repo_files skips .git directory."""
        src = tmp_path / "repo"
        src.mkdir()
        (src / ".git").mkdir()
        (src / "README.md").write_text("# Readme")

        dst = tmp_path / "dst"
        dst.mkdir()
        _copy_repo_files(src, dst)

        assert not (dst / ".git").exists()
        assert (dst / "README.md").read_text() == "# Readme"

    @pytest.mark.anyio
    async def test_git_clone_to_dir_success(self, tmp_path: Path) -> None:
        """_git_clone_to_dir clones and copies files on success."""
        target = tmp_path / "target"
        target.mkdir()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await _git_clone_to_dir("https://github.com/u/r.git", "main", target)

    @pytest.mark.anyio
    async def test_git_clone_to_dir_failure(self, tmp_path: Path) -> None:
        """_git_clone_to_dir raises RuntimeError on clone failure."""
        target = tmp_path / "target"
        target.mkdir()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Failed to install from git"):
                await _git_clone_to_dir("bad-url", None, target)

    def test_parse_github_url_with_branch(self) -> None:
        """Parse GitHub URL with branch succeeds."""
        clone_url, branch = _parse_github_url(
            "https://github.com/user/repo/tree/develop"
        )
        assert clone_url == "https://github.com/user/repo.git"
        assert branch == "develop"

    def test_parse_github_url_without_branch(self) -> None:
        """Parse GitHub URL without branch uses default branch."""
        clone_url, branch = _parse_github_url("https://github.com/user/repo")
        assert clone_url == "https://github.com/user/repo.git"
        assert branch == "main"  # DEFAULT_GITHUB_BRANCH

    def test_parse_github_url_invalid(self) -> None:
        """Parse invalid GitHub URL raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Invalid GitHub URL"):
            _parse_github_url("https://notgithub.com/something")

    @pytest.mark.anyio
    async def test_download_archive_success(self, tmp_path: Path) -> None:
        """_download_archive downloads file to temp path."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"file content")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            path = await _download_archive("https://example.com/plugin.zip")

        assert path.exists()
        assert path.read_bytes() == b"file content"
        path.unlink(missing_ok=True)

    @pytest.mark.anyio
    async def test_download_archive_http_error(self) -> None:
        """_download_archive raises RuntimeError on HTTP error."""
        mock_response = AsyncMock()
        mock_response.status = 404

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(RuntimeError, match="Failed to download from URL"):
                await _download_archive("https://example.com/missing.zip")

    @pytest.mark.anyio
    async def test_download_archive_connection_error(self) -> None:
        """_download_archive wraps connection errors."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(side_effect=ConnectionError("refused"))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(RuntimeError, match="Failed to download from URL"):
                await _download_archive("https://unreachable.example.com/file.zip")

    def test_tar_open_mode_tar_gz(self) -> None:
        """_tar_open_mode returns r:gz for .tar.gz."""
        assert _tar_open_mode("archive.tar.gz") == "r:gz"

    def test_tar_open_mode_tgz(self) -> None:
        """_tar_open_mode returns r:gz for .tgz."""
        assert _tar_open_mode("archive.tgz") == "r:gz"

    def test_tar_open_mode_tar(self) -> None:
        """_tar_open_mode returns r for .tar."""
        assert _tar_open_mode("archive.tar") == "r"

    def test_tar_open_mode_unsupported(self) -> None:
        """_tar_open_mode returns None for unsupported format."""
        assert _tar_open_mode("archive.rar") is None

    def test_extract_archive_file_zip(self, tmp_path: Path) -> None:
        """_extract_archive_file extracts zip files."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("hello.txt", "Hello World")

        target = tmp_path / "output"
        target.mkdir()
        _extract_archive_file(zip_path, "test.zip", target)

        assert (target / "hello.txt").read_text() == "Hello World"

    def test_extract_archive_file_tar_gz(self, tmp_path: Path) -> None:
        """_extract_archive_file extracts .tar.gz files."""
        tar_path = tmp_path / "test.tar.gz"
        content = b"tar content"
        with tarfile.open(tar_path, "w:gz") as tf:
            info = tarfile.TarInfo(name="hello.txt")
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))

        target = tmp_path / "output"
        target.mkdir()
        _extract_archive_file(tar_path, "test.tar.gz", target)

        assert (target / "hello.txt").read_bytes() == content

    def test_extract_archive_file_unsupported(self, tmp_path: Path) -> None:
        """_extract_archive_file raises for unsupported format."""
        dummy = tmp_path / "archive.rar"
        dummy.write_bytes(b"dummy")
        target = tmp_path / "output"
        target.mkdir()

        with pytest.raises(RuntimeError, match="Unsupported archive format"):
            _extract_archive_file(dummy, "archive.rar", target)

    def test_copy_local_path_file(self, tmp_path: Path) -> None:
        """_copy_local_path copies a single file."""
        src_file = tmp_path / "source.txt"
        src_file.write_text("content")
        dst = tmp_path / "dst"
        dst.mkdir()

        _copy_local_path(src_file, dst)
        assert (dst / "source.txt").read_text() == "content"

    def test_copy_local_path_dir(self, tmp_path: Path) -> None:
        """_copy_local_path copies a directory."""
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "file.py").write_text("import os")

        dst = tmp_path / "dst"
        dst.mkdir()
        _copy_local_path(src_dir, dst)

        assert (dst / "file.py").read_text() == "import os"

    @pytest.mark.anyio
    async def test_run_pip_deps_subprocess_success(self) -> None:
        """Dependency pip install succeeds without raising."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await _run_pip_deps_subprocess(["requests>=2.0", "pydantic>=2.0"])

    @pytest.mark.anyio
    async def test_run_pip_deps_subprocess_failure_warns(self) -> None:
        """Dependency pip install failure logs warning but doesn't raise."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"dep error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Should not raise - deps failure is a warning
            await _run_pip_deps_subprocess(["bad-dep"])

    @pytest.mark.anyio
    async def test_run_pip_deps_subprocess_no_stderr(self) -> None:
        """Dependency pip install failure with no stderr logs Unknown error."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", None))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await _run_pip_deps_subprocess(["bad-dep"])


# ---------------------------------------------------------------------------
# PluginInstaller class tests
# ---------------------------------------------------------------------------


class TestPluginInstaller:
    """Tests for the PluginInstaller class."""

    @pytest.fixture
    def installer(self, tmp_path: Path) -> PluginInstaller:
        """Create PluginInstaller with temp directory.

        Args:
            tmp_path: Pytest tmp_path fixture.

        Returns:
            PluginInstaller instance.
        """
        return PluginInstaller(data_dir=tmp_path)

    @pytest.mark.anyio
    async def test_install_from_pypi(self, installer: PluginInstaller, tmp_path: Path) -> None:
        """install_plugin_package from PyPI calls pip."""
        metadata = _make_metadata(source=PluginSource.PYPI)

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await installer.install_plugin_package(metadata)

        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_github(self, installer: PluginInstaller) -> None:
        """install_plugin_package from GitHub calls git clone."""
        metadata = _make_metadata(
            source=PluginSource.GITHUB,
            source_url="https://github.com/user/repo",
        )

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await installer.install_plugin_package(metadata)

        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_github_no_url(self, installer: PluginInstaller) -> None:
        """install_plugin_package from GitHub raises when no URL."""
        metadata = _make_metadata(source=PluginSource.GITHUB, source_url=None)

        with pytest.raises(RuntimeError, match="GitHub source URL is required"):
            await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_from_git(self, installer: PluginInstaller) -> None:
        """install_plugin_package from generic git calls git clone."""
        metadata = _make_metadata(
            source=PluginSource.GIT,
            source_url="https://gitlab.com/user/repo.git",
        )

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await installer.install_plugin_package(metadata)

        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_git_no_url(self, installer: PluginInstaller) -> None:
        """install_plugin_package from git raises when no URL."""
        metadata = _make_metadata(source=PluginSource.GIT, source_url=None)

        with pytest.raises(RuntimeError, match="Git source URL is required"):
            await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_from_url_zip(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """install_plugin_package from URL extracts zip archive."""
        # Create real zip archive
        zip_path = tmp_path / "plugin.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("plugin.py", "# plugin code")

        metadata = _make_metadata(
            source=PluginSource.URL,
            source_url="https://example.com/plugin.zip",
        )

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=zip_path.read_bytes())

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await installer.install_plugin_package(metadata)

        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_url_no_url(self, installer: PluginInstaller) -> None:
        """install_plugin_package from URL raises when no URL."""
        metadata = _make_metadata(source=PluginSource.URL, source_url=None)

        with pytest.raises(RuntimeError, match="URL source is required"):
            await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_from_local_file(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """install_plugin_package from local path copies the file."""
        src_file = tmp_path / "plugin.py"
        src_file.write_text("# plugin code")

        metadata = _make_metadata(source=PluginSource.LOCAL, source_url=str(src_file))

        result = await installer.install_plugin_package(metadata)
        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_local_dir(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """install_plugin_package from local directory copies the directory."""
        src_dir = tmp_path / "plugin_src"
        src_dir.mkdir()
        (src_dir / "extension.py").write_text("# ext")

        metadata = _make_metadata(source=PluginSource.LOCAL, source_url=str(src_dir))

        result = await installer.install_plugin_package(metadata)
        assert result.exists()

    @pytest.mark.anyio
    async def test_install_from_local_no_url(self, installer: PluginInstaller) -> None:
        """install_plugin_package from local raises when no URL."""
        metadata = _make_metadata(source=PluginSource.LOCAL, source_url=None)

        with pytest.raises(RuntimeError, match="Local source path is required"):
            await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_from_local_path_not_exist(self, installer: PluginInstaller) -> None:
        """install_plugin_package from local raises when path doesn't exist."""
        metadata = _make_metadata(
            source=PluginSource.LOCAL, source_url="/nonexistent/path/plugin"
        )

        with pytest.raises(RuntimeError, match="Local path does not exist"):
            await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_pypi_failure_propagates(self, installer: PluginInstaller) -> None:
        """install_plugin_package propagates pypi installation failure."""
        metadata = _make_metadata(source=PluginSource.PYPI)

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"pip failed"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError):
                await installer.install_plugin_package(metadata)

    @pytest.mark.anyio
    async def test_install_dependencies_empty(self, installer: PluginInstaller) -> None:
        """install_dependencies with empty list does nothing."""
        # Should not raise or call pip
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            await installer.install_dependencies([])
        mock_exec.assert_not_called()

    @pytest.mark.anyio
    async def test_install_dependencies_success(self, installer: PluginInstaller) -> None:
        """install_dependencies calls pip for deps."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await installer.install_dependencies(["requests>=2.0"])

    @pytest.mark.anyio
    async def test_install_dependencies_failure_logs_warning(
        self, installer: PluginInstaller
    ) -> None:
        """install_dependencies swallows exceptions and logs warning."""
        with patch(
            "henchman.extensions.plugin_installer._run_pip_deps_subprocess",
            side_effect=RuntimeError("dep failed"),
        ):
            # Should not raise
            await installer.install_dependencies(["bad-dep"])

    @pytest.mark.anyio
    async def test_install_package_with_pip(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """_install_package_with_pip calls pip subprocess."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await installer._install_package_with_pip("package==1.0.0", str(tmp_path))

    def test_copy_installed_files(self, installer: PluginInstaller, tmp_path: Path) -> None:
        """_copy_installed_files copies source to target."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1")
        dst = tmp_path / "dst"
        dst.mkdir()

        installer._copy_installed_files(str(src), dst)
        assert (dst / "mod.py").read_text() == "x = 1"

    @pytest.mark.anyio
    async def test_download_archive_from_url(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """_download_archive_from_url delegates to _download_archive."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"data")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            path = await installer._download_archive_from_url("https://example.com/a.zip")

        assert path.exists()
        path.unlink(missing_ok=True)

    @pytest.mark.anyio
    async def test_extract_archive(self, installer: PluginInstaller, tmp_path: Path) -> None:
        """_extract_archive delegates to _extract_archive_file."""
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file.txt", "content")

        target = tmp_path / "out"
        target.mkdir()
        await installer._extract_archive(zip_path, "test.zip", target)

        assert (target / "file.txt").read_text() == "content"

    @pytest.mark.anyio
    async def test_clone_and_copy_git_repo(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """_clone_and_copy_git_repo delegates to _git_clone_to_dir."""
        target = tmp_path / "target"
        target.mkdir()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await installer._clone_and_copy_git_repo(
                "https://github.com/u/r.git", "main", target
            )

        assert result == target

    @pytest.mark.anyio
    async def test_local_install_copy_failure(
        self, installer: PluginInstaller, tmp_path: Path
    ) -> None:
        """_install_from_local raises RuntimeError on copy failure."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        metadata = _make_metadata(source=PluginSource.LOCAL, source_url=str(src_dir))

        with patch(
            "henchman.extensions.plugin_installer._copy_local_path",
            side_effect=OSError("permission denied"),
        ), pytest.raises(RuntimeError, match="Failed to install from local path"):
            await installer._install_from_local(metadata, tmp_path / "dst")


# ---------------------------------------------------------------------------
# PluginRegistryClient tests
# ---------------------------------------------------------------------------


class TestPluginRegistryClient:
    """Tests for PluginRegistryClient."""

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """Create mock aiohttp session.

        Returns:
            Mock session object.
        """
        session = MagicMock()
        return session

    @pytest.fixture
    def client(self, mock_session: MagicMock):
        """Create PluginRegistryClient with mock session.

        Args:
            mock_session: Mock session.

        Returns:
            PluginRegistryClient instance.
        """
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        return PluginRegistryClient(
            registry_url="https://test.example.com",
            session=mock_session,
        )

    @pytest.mark.anyio
    async def test_search_plugins_success(self, client) -> None:
        """search_plugins returns PluginSearchResult on success."""
        plugin_data = {
            "name": "my-plugin",
            "version": "1.0.0",
            "description": "A test plugin for Henchman-AI",
            "author": "Author",
            "entry_points": {"henchman_extensions": "m:M"},
        }
        response_data = {"plugins": [plugin_data], "total": 1, "page": 1, "page_size": 20}

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        params = PluginSearchParams(query="test", page=1, page_size=20)
        result = await client.search_plugins(params)

        assert isinstance(result, PluginSearchResult)
        assert result.total == 1
        assert len(result.plugins) == 1

    @pytest.mark.anyio
    async def test_search_plugins_with_category(self, client) -> None:
        """search_plugins includes category in request."""
        response_data = {"plugins": [], "total": 0, "page": 1, "page_size": 20}

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        params = PluginSearchParams(page=1, page_size=20)
        result = await client.search_plugins(params, category="tools")

        assert isinstance(result, PluginSearchResult)
        assert result.total == 0

    @pytest.mark.anyio
    async def test_search_plugins_validation_error(self, client) -> None:
        """search_plugins returns empty result on validation error."""
        # Return invalid plugin data (missing required fields)
        response_data = {"plugins": [{"bad": "data"}], "total": 1}

        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=response_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        params = PluginSearchParams(page=1, page_size=20)
        result = await client.search_plugins(params)

        assert result.total == 0
        assert result.plugins == []

    @pytest.mark.anyio
    async def test_search_plugins_not_initialized(self) -> None:
        """search_plugins raises RuntimeError when not initialized."""
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        client = PluginRegistryClient(session=None)
        # Don't call initialize() to leave session as None

        params = PluginSearchParams()
        with pytest.raises(RuntimeError, match="Registry client not initialized"):
            await client.search_plugins(params)

    @pytest.mark.anyio
    async def test_get_plugin_info_found(self, client) -> None:
        """get_plugin_info returns PluginMetadata when plugin exists."""
        plugin_data = {
            "name": "my-plugin",
            "version": "1.0.0",
            "description": "A test plugin for Henchman-AI",
            "author": "Author",
            "entry_points": {"henchman_extensions": "m:M"},
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=plugin_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        result = await client.get_plugin_info("my-plugin")
        assert result is not None
        assert result.name == "my-plugin"

    @pytest.mark.anyio
    async def test_get_plugin_info_not_found(self, client) -> None:
        """get_plugin_info returns None when plugin not found (404)."""
        mock_resp = AsyncMock()
        mock_resp.status = 404
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        result = await client.get_plugin_info("nonexistent-plugin")
        assert result is None

    @pytest.mark.anyio
    async def test_get_plugin_info_with_version(self, client) -> None:
        """get_plugin_info with version uses versioned URL."""
        plugin_data = {
            "name": "my-plugin",
            "version": "2.0.0",
            "description": "A test plugin for Henchman-AI",
            "author": "Author",
            "entry_points": {"henchman_extensions": "m:M"},
        }
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=plugin_data)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        result = await client.get_plugin_info("my-plugin", version="2.0.0")
        assert result is not None
        # Check that a versioned URL was used
        call_url = client._session.get.call_args[0][0]
        assert "versions/2.0.0" in call_url

    @pytest.mark.anyio
    async def test_get_plugin_info_validation_error(self, client) -> None:
        """get_plugin_info returns None on validation error."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value={"bad": "data"})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        client._session.get = MagicMock(return_value=mock_resp)

        result = await client.get_plugin_info("bad-plugin")
        assert result is None

    @pytest.mark.anyio
    async def test_get_plugin_info_not_initialized(self) -> None:
        """get_plugin_info raises RuntimeError when not initialized."""
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        client = PluginRegistryClient(session=None)

        with pytest.raises(RuntimeError, match="Registry client not initialized"):
            await client.get_plugin_info("test")

    @pytest.mark.anyio
    async def test_context_manager(self) -> None:
        """PluginRegistryClient works as async context manager."""
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.close = AsyncMock()
            mock_session_cls.return_value = mock_session

            async with PluginRegistryClient() as client:
                assert client._session is not None

    @pytest.mark.anyio
    async def test_initialize_creates_session(self) -> None:
        """initialize creates aiohttp session when none provided."""
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session

            client = PluginRegistryClient(session=None)
            await client.initialize()

            assert client._session is not None
            mock_session_cls.assert_called_once()

    @pytest.mark.anyio
    async def test_close_owned_session(self) -> None:
        """close() closes session if we own it."""
        from henchman.extensions.plugin_registry_client import PluginRegistryClient

        mock_session = AsyncMock()
        mock_session.close = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = PluginRegistryClient(session=None)
            await client.initialize()
            await client.close()

        mock_session.close.assert_called_once()

    @pytest.mark.anyio
    async def test_close_external_session_not_closed(self, client) -> None:
        """close() doesn't close session if not owned."""
        client._session.close = AsyncMock()
        await client.close()
        client._session.close.assert_not_called()


# ---------------------------------------------------------------------------
# PluginManager tests
# ---------------------------------------------------------------------------


class TestPluginManagerExtended:
    """Additional tests for PluginManager covering uncovered branches."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Create temp directory.

        Args:
            tmp_path: Pytest tmp_path fixture.

        Returns:
            Temporary directory path.
        """
        return tmp_path

    @pytest.fixture
    def manager(self, temp_dir: Path):
        """Create PluginManager with temp dir.

        Args:
            temp_dir: Temporary directory.

        Returns:
            PluginManager instance.
        """
        from henchman.extensions.plugin_manager import PluginManager

        return PluginManager(
            registry_url="https://test.example.com",
            data_dir=temp_dir,
        )

    @pytest.mark.anyio
    async def test_initialize_creates_dir(self, manager, temp_dir: Path) -> None:
        """initialize creates data directory and marks initialized."""
        with (
            patch.object(manager.database, "initialize", new=AsyncMock()),
            patch.object(manager.database, "load_installations", new=AsyncMock(return_value={})),
            patch("henchman.extensions.plugin_registry_client.PluginRegistryClient.initialize", new=AsyncMock()),
        ):
            await manager.initialize()

        assert manager._initialized is True
        assert temp_dir.exists()

    @pytest.mark.anyio
    async def test_initialize_idempotent(self, manager) -> None:
        """initialize is idempotent when called twice."""
        manager._initialized = True
        # Should return immediately without calling database
        with patch.object(manager.database, "initialize") as mock_db_init:
            await manager.initialize()
        mock_db_init.assert_not_called()

    @pytest.mark.anyio
    async def test_close_cleanup(self, manager) -> None:
        """close() sets agent/installer to None and marks uninitialized."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        manager.registry_client = mock_client
        manager.installer = MagicMock()
        manager._initialized = True

        await manager.close()

        mock_client.close.assert_called_once()
        assert manager.registry_client is None
        assert manager.installer is None
        assert manager._initialized is False

    @pytest.mark.anyio
    async def test_search_plugins_not_initialized(self, manager) -> None:
        """search_plugins raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="Plugin manager not initialized"):
            await manager.search_plugins("test")

    @pytest.mark.anyio
    async def test_get_plugin_info_not_initialized(self, manager) -> None:
        """get_plugin_info raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="Plugin manager not initialized"):
            await manager.get_plugin_info("test")

    @pytest.mark.anyio
    async def test_install_plugin_not_initialized(self, manager) -> None:
        """install_plugin raises RuntimeError when not initialized."""
        with pytest.raises(RuntimeError, match="Plugin manager not initialized"):
            await manager.install_plugin("test-plugin")

    @pytest.mark.anyio
    async def test_install_plugin_already_installed(self, manager) -> None:
        """install_plugin raises ValueError if plugin already installed."""
        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = MagicMock()
        manager.installed_plugins = {"my-plugin": MagicMock()}

        with pytest.raises(ValueError, match="already installed"):
            await manager.install_plugin("my-plugin")

    @pytest.mark.anyio
    async def test_install_plugin_not_found(self, manager) -> None:
        """install_plugin raises ValueError if plugin not found in registry."""
        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = MagicMock()
        manager.installed_plugins = {}

        with patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=None)):
            with pytest.raises(ValueError, match="not found in registry"):
                await manager.install_plugin("nonexistent")

    @pytest.mark.anyio
    async def test_install_plugin_incompatible(self, manager) -> None:
        """install_plugin raises RuntimeError if plugin is incompatible."""
        metadata = _make_metadata()
        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = MagicMock()
        manager.installed_plugins = {}

        with (
            patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=metadata)),
            patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker.check_compatibility",
                new=AsyncMock(return_value=False),
            ),pytest.raises(RuntimeError, match="not compatible")
        ):
            await manager.install_plugin("my-plugin")

    @pytest.mark.anyio
    async def test_install_plugin_success(self, manager, tmp_path: Path) -> None:
        """install_plugin completes successfully."""
        metadata = _make_metadata()
        plugin_dir = tmp_path / "installed" / "my-plugin"
        plugin_dir.mkdir(parents=True)

        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = AsyncMock()
        manager.installer.install_plugin_package = AsyncMock(return_value=plugin_dir)
        manager.installer.install_dependencies = AsyncMock()
        manager.installed_plugins = {}

        with (
            patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=metadata)),
            patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker.check_compatibility",
                new=AsyncMock(return_value=True),
            ),
            patch.object(manager.database, "save_installation", new=AsyncMock()),
            patch.object(manager, "_load_plugin_extension", new=AsyncMock()),
        ):
            result = await manager.install_plugin("my-plugin")

        assert result.metadata.name == "my-plugin"
        assert "my-plugin" in manager.installed_plugins

    @pytest.mark.anyio
    async def test_install_plugin_installer_failure(self, manager) -> None:
        """install_plugin raises RuntimeError when installer fails."""
        metadata = _make_metadata()

        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = AsyncMock()
        manager.installer.install_plugin_package = AsyncMock(
            side_effect=RuntimeError("install failed")
        )
        manager.installer.install_dependencies = AsyncMock()
        manager.installed_plugins = {}

        with (
            patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=metadata)),
            patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker.check_compatibility",
                new=AsyncMock(return_value=True),
            ),pytest.raises(RuntimeError, match="Failed to install plugin")
        ):
            await manager.install_plugin("my-plugin")

    @pytest.mark.anyio
    async def test_uninstall_plugin_not_installed(self, manager) -> None:
        """uninstall_plugin raises ValueError if plugin not installed."""
        manager.installed_plugins = {}

        with pytest.raises(ValueError, match="not installed"):
            await manager.uninstall_plugin("nonexistent")

    @pytest.mark.anyio
    async def test_uninstall_plugin_success(self, manager, tmp_path: Path) -> None:
        """uninstall_plugin removes plugin from filesystem and database."""
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        (plugin_dir / "ext.py").write_text("x=1")

        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path=str(plugin_dir),
        )
        manager.installed_plugins = {"my-plugin": installation}

        with (
            patch.object(manager, "unregister", MagicMock()),
            patch.object(manager.database, "delete_installation", new=AsyncMock()),
        ):
            await manager.uninstall_plugin("my-plugin")

        assert "my-plugin" not in manager.installed_plugins

    @pytest.mark.anyio
    async def test_uninstall_plugin_removal_failure_warns(self, manager, tmp_path: Path) -> None:
        """uninstall_plugin handles filesystem removal failure gracefully."""
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path="/nonexistent/path",
        )
        manager.installed_plugins = {"my-plugin": installation}

        with (
            patch.object(manager, "unregister", MagicMock()),
            patch.object(manager.database, "delete_installation", new=AsyncMock()),
            patch("shutil.rmtree", side_effect=OSError("permission denied")),
        ):
            # Should not raise
            await manager.uninstall_plugin("my-plugin")

        assert "my-plugin" not in manager.installed_plugins

    @pytest.mark.anyio
    async def test_update_plugin_not_installed(self, manager) -> None:
        """update_plugin raises ValueError if plugin not installed."""
        manager.installed_plugins = {}

        with pytest.raises(ValueError, match="not installed"):
            await manager.update_plugin("nonexistent")

    @pytest.mark.anyio
    async def test_update_plugin_not_found_in_registry(self, manager) -> None:
        """update_plugin returns None when plugin not found in registry."""
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata, installed_version="1.0.0"
        )
        manager.installed_plugins = {"my-plugin": installation}

        with patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=None)):
            result = await manager.update_plugin("my-plugin")

        assert result is None

    @pytest.mark.anyio
    async def test_update_plugin_already_up_to_date(self, manager) -> None:
        """update_plugin returns None when already on latest version."""
        metadata = _make_metadata(version="1.0.0")
        installation = PluginInstallation(
            metadata=metadata, installed_version="1.0.0"
        )
        manager.installed_plugins = {"my-plugin": installation}

        with patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=metadata)):
            result = await manager.update_plugin("my-plugin")

        assert result is None

    @pytest.mark.anyio
    async def test_check_updates_finds_update(self, manager) -> None:
        """check_updates returns update info for outdated plugins."""
        old_meta = _make_metadata(version="1.0.0")
        new_meta = _make_metadata(version="2.0.0")
        installation = PluginInstallation(
            metadata=old_meta, installed_version="1.0.0"
        )
        manager.installed_plugins = {"my-plugin": installation}

        with patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=new_meta)):
            updates = await manager.check_updates()

        assert "my-plugin" in updates
        assert updates["my-plugin"].latest_version == "2.0.0"

    @pytest.mark.anyio
    async def test_check_updates_none_found(self, manager) -> None:
        """check_updates returns empty dict when registry lookup fails."""
        old_meta = _make_metadata(version="1.0.0")
        installation = PluginInstallation(
            metadata=old_meta, installed_version="1.0.0"
        )
        manager.installed_plugins = {"my-plugin": installation}

        with patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=None)):
            updates = await manager.check_updates()

        assert updates == {}

    @pytest.mark.anyio
    async def test_scan_security_not_installed(self, manager) -> None:
        """scan_security raises ValueError if plugin not installed."""
        manager.installed_plugins = {}

        with pytest.raises(ValueError, match="not installed"):
            await manager.scan_security("nonexistent")

    @pytest.mark.anyio
    async def test_scan_security_passes(self, manager) -> None:
        """scan_security returns SecurityReport for installed plugin."""
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata, installed_version="1.0.0"
        )
        manager.installed_plugins = {"my-plugin": installation}

        report = await manager.scan_security("my-plugin")
        assert report.plugin_name == "my-plugin"
        assert report.passed is True

    @pytest.mark.anyio
    async def test_scan_security_sandbox_warning(self, manager) -> None:
        """scan_security warns when plugin requires sandbox."""
        from henchman.extensions.models import PluginSecurity

        security = PluginSecurity(requires_sandbox=True)
        meta = PluginMetadata(
            name="my-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="m:M"),
            security=security,
        )
        installation = PluginInstallation(metadata=meta, installed_version="1.0.0")
        manager.installed_plugins = {"my-plugin": installation}

        report = await manager.scan_security("my-plugin")
        assert len(report.warnings) > 0
        assert report.risk_level == "medium"

    @pytest.mark.anyio
    async def test_load_plugin_extension_no_path(self, manager) -> None:
        """_load_plugin_extension does nothing when no installation_path."""
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata, installed_version="1.0.0", installation_path=None
        )
        # Should not raise
        await manager._load_plugin_extension(installation)

    @pytest.mark.anyio
    async def test_load_plugin_extension_no_ext_file(self, manager, tmp_path: Path) -> None:
        """_load_plugin_extension does nothing when no extension.py."""
        plugin_dir = tmp_path / "empty_plugin"
        plugin_dir.mkdir()
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path=str(plugin_dir),
        )
        # Should not raise
        await manager._load_plugin_extension(installation)

    @pytest.mark.anyio
    async def test_load_plugin_extension_failure_warns(
        self, manager, tmp_path: Path
    ) -> None:
        """_load_plugin_extension logs warning when loading fails."""
        plugin_dir = tmp_path / "bad_plugin"
        plugin_dir.mkdir()
        (plugin_dir / "extension.py").write_text("invalid syntax !!!")

        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path=str(plugin_dir),
        )

        with patch.object(manager, "_load_extension_from_file", side_effect=Exception("load error")):
            # Should not raise
            await manager._load_plugin_extension(installation)

    @pytest.mark.anyio
    async def test_initialize_loads_enabled_plugins(self, manager) -> None:
        """initialize loads extensions for enabled installed plugins."""
        metadata = _make_metadata()
        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            enabled=True,
            installation_path=None,
        )

        with (
            patch.object(manager.database, "initialize", new=AsyncMock()),
            patch.object(
                manager.database,
                "load_installations",
                new=AsyncMock(return_value={"my-plugin": installation}),
            ),
            patch.object(manager, "_load_plugin_extension", new=AsyncMock()) as mock_load,
            patch(
                "henchman.extensions.plugin_registry_client.PluginRegistryClient.initialize",
                new=AsyncMock(),
            ),
        ):
            await manager.initialize()

        mock_load.assert_called_once_with(installation)

    @pytest.mark.anyio
    async def test_search_plugins_delegates_to_client(self, manager) -> None:
        """search_plugins delegates to registry client."""
        manager._initialized = True
        mock_client = AsyncMock()
        mock_result = MagicMock(spec=PluginSearchResult)
        mock_client.search_plugins = AsyncMock(return_value=mock_result)
        manager.registry_client = mock_client

        result = await manager.search_plugins(query="test", page=1, page_size=10, category="ui")

        assert result is mock_result
        mock_client.search_plugins.assert_called_once()

    @pytest.mark.anyio
    async def test_install_plugin_with_dependencies(self, manager, tmp_path: Path) -> None:
        """install_plugin installs dependencies before plugin."""
        from henchman.extensions.models import PluginMetadata as PM

        metadata = PM(
            name="my-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(henchman_extensions="m:M"),
            dependencies=["requests>=2.0"],
        )
        plugin_dir = tmp_path / "installed" / "my-plugin"
        plugin_dir.mkdir(parents=True)

        manager._initialized = True
        manager.registry_client = MagicMock()
        manager.installer = AsyncMock()
        manager.installer.install_plugin_package = AsyncMock(return_value=plugin_dir)
        manager.installer.install_dependencies = AsyncMock()
        manager.installed_plugins = {}

        with (
            patch.object(manager, "get_plugin_info", new=AsyncMock(return_value=metadata)),
            patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker.check_compatibility",
                new=AsyncMock(return_value=True),
            ),
            patch.object(manager.database, "save_installation", new=AsyncMock()),
            patch.object(manager, "_load_plugin_extension", new=AsyncMock()),
        ):
            await manager.install_plugin("my-plugin")

        manager.installer.install_dependencies.assert_called_once_with(["requests>=2.0"])
