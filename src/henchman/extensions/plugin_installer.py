"""Plugin installer for various source types."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import aiohttp

from henchman.extensions.constants import PluginConstants
from henchman.extensions.models import PluginMetadata, PluginSource

logger = logging.getLogger(__name__)


class PluginInstaller:
    """Handles plugin installation from various sources."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize plugin installer.

        Args:
            data_dir: Base directory for plugin installations.
        """
        self.data_dir = data_dir

    async def install_plugin_package(self, metadata: PluginMetadata) -> Path:
        """Install plugin package from source.

        Args:
            metadata: Plugin metadata.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        # Create installation directory
        plugin_dir = self.data_dir / "installed" / metadata.name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Install based on source type
        if metadata.source == PluginSource.PYPI:
            return await self._install_from_pypi(metadata, plugin_dir)
        if metadata.source == PluginSource.GITHUB:
            return await self._install_from_github(metadata, plugin_dir)
        if metadata.source == PluginSource.GIT:
            return await self._install_from_git(metadata, plugin_dir)
        if metadata.source == PluginSource.URL:
            return await self._install_from_url(metadata, plugin_dir)
        if metadata.source == PluginSource.LOCAL:
            return await self._install_from_local(metadata, plugin_dir)
        msg = f"Unsupported plugin source: {metadata.source}"
        raise RuntimeError(msg)

    async def _install_from_pypi(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from PyPI.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        # Build package specification
        package_spec = f"{metadata.name}=={metadata.version}"

        # Use pip to install the package
        # We install to a temporary directory first, then copy to target
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                await self._install_package_with_pip(package_spec, temp_dir)
                self._copy_installed_files(temp_dir, target_dir)
                logger.info("Successfully installed package to: %s", target_dir)
            except Exception as e:
                msg = f"Failed to install from PyPI: {e}"
                raise RuntimeError(msg) from e

        return target_dir

    async def _install_package_with_pip(self, package_spec: str, target_dir: str) -> None:
        """Install package using pip.

        Args:
            package_spec: Package specification (e.g., "package==1.0.0").
            target_dir: Directory to install into.

        Raises:
            RuntimeError: If pip installation fails.
        """
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            package_spec,
            "--target",
            target_dir,
            "--no-deps",  # We'll handle dependencies separately
        ]

        logger.info("Installing package from PyPI: %s", package_spec)
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _stdout, stderr = await result.communicate()

        if result.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            msg = f"Failed to install package: {error_msg}"
            raise RuntimeError(msg)

    def _copy_installed_files(self, source_dir: str, target_dir: Path) -> None:
        """Copy installed files from source to target directory.

        Args:
            source_dir: Source directory with installed files.
            target_dir: Target directory to copy to.
        """
        temp_path = Path(source_dir)
        for item in temp_path.iterdir():
            if item.is_file() or item.is_dir():
                dest = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    async def _install_from_github(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from GitHub repository.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            msg = "GitHub source URL is required"
            raise RuntimeError(msg)

        # Parse GitHub URL
        # Expected format: https://github.com/user/repo or https://github.com/user/repo/tree/branch
        github_pattern = r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?"
        match = re.search(github_pattern, metadata.source_url)

        if not match:
            msg = f"Invalid GitHub URL: {metadata.source_url}"
            raise RuntimeError(msg)

        user, repo, branch = match.groups()
        branch = branch or PluginConstants.DEFAULT_GITHUB_BRANCH

        # Clone repository
        clone_url = f"https://github.com/{user}/{repo}.git"
        return await self._clone_and_copy_git_repo(clone_url, branch, target_dir)

    async def _install_from_git(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from generic git repository.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            msg = "Git source URL is required"
            raise RuntimeError(msg)

        return await self._clone_and_copy_git_repo(metadata.source_url, None, target_dir)

    async def _clone_and_copy_git_repo(
        self,
        clone_url: str,
        branch: str | None,
        target_dir: Path,
    ) -> Path:
        """Clone git repository and copy files to target directory.

        Args:
            clone_url: Git repository URL to clone.
            branch: Branch to clone (None for default).
            target_dir: Directory to copy files to.

        Returns:
            Path where files were copied.

        Raises:
            RuntimeError: If clone or copy fails.
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Build git clone command
                cmd = ["git", "clone", "--depth", str(PluginConstants.GIT_CLONE_DEPTH)]
                if branch:
                    cmd.extend(["--branch", branch])
                cmd.extend([clone_url, temp_dir])

                logger.info("Cloning repository: %s (branch: %s)", clone_url, branch or "default")
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                _stdout, stderr = await result.communicate()

                if result.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    msg = f"Failed to clone repository: {error_msg}"
                    raise RuntimeError(msg)

                # Copy files to target directory
                temp_path = Path(temp_dir)
                for item in temp_path.iterdir():
                    if item.name != ".git":  # Skip .git directory
                        dest = target_dir / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)

                logger.info("Successfully installed from git to: %s", target_dir)

        except Exception as e:
            msg = f"Failed to install from git: {e}"
            raise RuntimeError(msg) from e

        return target_dir

    async def _install_from_url(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from direct URL (zip/tar archive).

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            msg = "URL source is required"
            raise RuntimeError(msg)

        # Download archive to temporary file
        temp_path = await self._download_archive_from_url(metadata.source_url)

        try:
            # Extract archive based on file type
            await self._extract_archive(temp_path, metadata.source_url, target_dir)
            logger.info("Successfully installed from URL to: %s", target_dir)
        finally:
            # Clean up temporary file
            temp_path.unlink(missing_ok=True)

        return target_dir

    async def _download_archive_from_url(self, url: str) -> Path:
        """Download archive from URL to temporary file.

        Args:
            url: URL to download from.

        Returns:
            Path to temporary file with downloaded content.

        Raises:
            RuntimeError: If download fails.
        """
        try:
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status != 200:
                    msg = f"Failed to download from URL: HTTP {response.status}"
                    raise RuntimeError(msg)

                # Create temporary file for download
                with tempfile.NamedTemporaryFile(suffix=".archive", delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                    # Download content
                    content = await response.read()
                    temp_file.write(content)
                    return temp_path
        except Exception as e:
            msg = f"Failed to download from URL: {e}"
            raise RuntimeError(msg) from e

    async def _extract_archive(
        self,
        archive_path: Path,
        source_url: str,
        target_dir: Path,
    ) -> None:
        """Extract archive file to target directory.

        Args:
            archive_path: Path to archive file.
            source_url: Source URL for archive type detection.
            target_dir: Directory to extract into.

        Raises:
            RuntimeError: If extraction fails or format is unsupported.
        """
        # Determine archive type and extract
        if source_url.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)
        elif source_url.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_path, "r:gz") as tar_ref:
                tar_ref.extractall(target_dir)
        elif source_url.endswith(".tar"):
            with tarfile.open(archive_path, "r") as tar_ref:
                tar_ref.extractall(target_dir)
        else:
            msg = f"Unsupported archive format: {source_url}"
            raise RuntimeError(msg)

    async def _install_from_local(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from local directory.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            msg = "Local source path is required"
            raise RuntimeError(msg)

        source_path = Path(metadata.source_url)

        if not source_path.exists():
            msg = f"Local path does not exist: {source_path}"
            raise RuntimeError(msg)

        try:
            if source_path.is_file():
                # Copy single file
                shutil.copy2(source_path, target_dir / source_path.name)
            else:
                # Copy directory
                for item in source_path.iterdir():
                    dest = target_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

            logger.info("Successfully installed from local path to: %s", target_dir)

        except Exception as e:
            msg = f"Failed to install from local path: {e}"
            raise RuntimeError(msg) from e

        return target_dir

    async def install_dependencies(self, dependencies: list[str]) -> None:
        """Install plugin dependencies.

        Args:
            dependencies: List of dependency specifications.

        Raises:
            RuntimeError: If dependency installation fails.
        """
        if not dependencies:
            return

        logger.info("Installing %d dependencies", len(dependencies))

        try:
            # Install dependencies using pip
            cmd = [sys.executable, "-m", "pip", "install", *dependencies]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                # Don't fail the entire installation if dependencies fail
                # Just log a warning and continue
                logger.warning("Failed to install some dependencies: %s", error_msg)
            else:
                logger.info("Successfully installed dependencies")

        except Exception as e:
            logger.warning("Error installing dependencies: %s", e)
            # Continue with plugin installation even if dependencies fail
