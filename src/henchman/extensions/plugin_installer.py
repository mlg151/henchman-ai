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

_HTTP_OK = 200


# ---------------------------------------------------------------------------
# Module-level helpers (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


async def _run_pip_subprocess(package_spec: str, target_dir: str) -> None:
    """Install a package via pip to target_dir.

    Args:
        package_spec: Package specification, e.g. ``"package==1.0.0"``.
        target_dir: Directory passed to ``--target``.

    Raises:
        RuntimeError: If pip exits with a non-zero return code.
    """
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package_spec,
        "--target",
        target_dir,
        "--no-deps",
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


def _copy_dir_contents(source_dir: Path, target_dir: Path) -> None:
    """Copy every item in *source_dir* into *target_dir*.

    Args:
        source_dir: Directory whose contents are to be copied.
        target_dir: Destination directory (must already exist).
    """
    for item in source_dir.iterdir():
        dest = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


async def _install_pypi_package(metadata: PluginMetadata, target_dir: Path) -> Path:
    """Install a PyPI package described by *metadata* into *target_dir*.

    Args:
        metadata: Plugin metadata (must have ``name`` and ``version``).
        target_dir: Pre-created destination directory.

    Returns:
        *target_dir* on success.

    Raises:
        RuntimeError: If pip installation fails.
    """
    package_spec = f"{metadata.name}=={metadata.version}"
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            await _run_pip_subprocess(package_spec, temp_dir)
            _copy_dir_contents(Path(temp_dir), target_dir)
            logger.info("Successfully installed package to: %s", target_dir)
        except Exception as e:
            msg = f"Failed to install from PyPI: {e}"
            raise RuntimeError(msg) from e
    return target_dir


async def _run_git_clone_subprocess(
    clone_url: str,
    branch: str | None,
    dest_dir: str,
) -> None:
    """Execute ``git clone`` into *dest_dir*.

    Args:
        clone_url: Remote URL to clone.
        branch: Branch name, or ``None`` for the remote default.
        dest_dir: Local path to clone into.

    Raises:
        RuntimeError: If git exits with a non-zero return code.
    """
    cmd = ["git", "clone", "--depth", str(PluginConstants.GIT_CLONE_DEPTH)]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([clone_url, dest_dir])

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


def _copy_repo_files(source_dir: Path, target_dir: Path) -> None:
    """Copy repository files from *source_dir* to *target_dir*, skipping ``.git``.

    Args:
        source_dir: Root of the cloned repository.
        target_dir: Destination directory.
    """
    for item in source_dir.iterdir():
        if item.name == ".git":
            continue
        dest = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


async def _git_clone_to_dir(
    clone_url: str,
    branch: str | None,
    target_dir: Path,
) -> None:
    """Clone a git repository and copy its files to *target_dir*.

    Args:
        clone_url: Remote URL to clone.
        branch: Branch name, or ``None`` for the remote default.
        target_dir: Destination directory (must already exist).

    Raises:
        RuntimeError: If clone or file-copy fails.
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            await _run_git_clone_subprocess(clone_url, branch, temp_dir)
            _copy_repo_files(Path(temp_dir), target_dir)
        logger.info("Successfully installed from git to: %s", target_dir)
    except Exception as e:
        msg = f"Failed to install from git: {e}"
        raise RuntimeError(msg) from e


def _parse_github_url(source_url: str) -> tuple[str, str | None]:
    """Parse a GitHub URL into a clone URL and optional branch.

    Args:
        source_url: GitHub URL, e.g.
            ``https://github.com/user/repo/tree/main``.

    Returns:
        A ``(clone_url, branch)`` tuple where *branch* may be ``None``.

    Raises:
        RuntimeError: If the URL does not match the expected GitHub pattern.
    """
    github_pattern = r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?"
    match = re.search(github_pattern, source_url)
    if not match:
        msg = f"Invalid GitHub URL: {source_url}"
        raise RuntimeError(msg)
    user, repo, branch = match.groups()
    effective_branch: str | None = branch or PluginConstants.DEFAULT_GITHUB_BRANCH
    return f"https://github.com/{user}/{repo}.git", effective_branch


async def _download_archive(url: str) -> Path:
    """Download *url* to a temporary file and return its :class:`Path`.

    Args:
        url: Remote URL of an archive to download.

    Returns:
        Path to the downloaded temporary file (caller is responsible for
        deleting it).

    Raises:
        RuntimeError: If the HTTP response is not 200 or the download fails.
    """
    try:
        async with aiohttp.ClientSession() as session, session.get(url) as response:
            if response.status != _HTTP_OK:
                msg = f"Failed to download from URL: HTTP {response.status}"
                raise RuntimeError(msg)  # noqa: TRY301
            with tempfile.NamedTemporaryFile(suffix=".archive", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                content = await response.read()
                temp_file.write(content)
                return temp_path
    except Exception as e:
        msg = f"Failed to download from URL: {e}"
        raise RuntimeError(msg) from e


def _tar_open_mode(source_url: str) -> str | None:
    """Return the tarfile open mode for *source_url*, or ``None`` if unsupported."""
    if source_url.endswith((".tar.gz", ".tgz")):
        return "r:gz"
    if source_url.endswith(".tar"):
        return "r"
    return None


def _extract_archive_file(
    archive_path: Path,
    source_url: str,
    target_dir: Path,
) -> None:
    """Extract an archive file to *target_dir*.

    Archive type is inferred from the *source_url* extension.

    Args:
        archive_path: Local path to the downloaded archive.
        source_url: Original URL (used for extension detection).
        target_dir: Destination directory for extracted contents.

    Raises:
        RuntimeError: If the archive format is unsupported.
    """
    if source_url.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)
        return

    tar_mode = _tar_open_mode(source_url)
    if tar_mode is None:
        msg = f"Unsupported archive format: {source_url}"
        raise RuntimeError(msg)

    with tarfile.open(archive_path, tar_mode) as tar_ref:
        tar_ref.extractall(target_dir)


def _copy_local_path(source_path: Path, target_dir: Path) -> None:
    """Copy a local file or directory to *target_dir*.

    Args:
        source_path: File or directory to copy.
        target_dir: Destination directory (must already exist).
    """
    if source_path.is_file():
        shutil.copy2(source_path, target_dir / source_path.name)
    else:
        _copy_dir_contents(source_path, target_dir)


async def _run_pip_deps_subprocess(dependencies: list[str]) -> None:
    """Install *dependencies* via pip (best-effort; warns on failure).

    Args:
        dependencies: List of pip requirement specifiers.
    """
    cmd = [sys.executable, "-m", "pip", "install", *dependencies]
    result = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await result.communicate()
    if result.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        logger.warning("Failed to install some dependencies: %s", error_msg)
    else:
        logger.info("Successfully installed dependencies")


# ---------------------------------------------------------------------------
# PluginInstaller class — thin orchestration layer
# ---------------------------------------------------------------------------


class PluginInstaller:
    """Handles plugin installation from various sources."""

    def __init__(self: PluginInstaller, data_dir: Path) -> None:
        """Initialize plugin installer.

        Args:
            data_dir: Base directory for plugin installations.
        """
        self.data_dir = data_dir

    async def install_plugin_package(self: PluginInstaller, metadata: PluginMetadata) -> Path:
        """Install plugin package from source.

        Args:
            metadata: Plugin metadata.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        plugin_dir = self.data_dir / "installed" / metadata.name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        source = metadata.source
        if source == PluginSource.PYPI:
            return await self._install_from_pypi(metadata, plugin_dir)
        if source == PluginSource.GITHUB:
            return await self._install_from_github(metadata, plugin_dir)
        if source == PluginSource.GIT:
            return await self._install_from_git(metadata, plugin_dir)
        if source == PluginSource.URL:
            return await self._install_from_url(metadata, plugin_dir)
        if source == PluginSource.LOCAL:
            return await self._install_from_local(metadata, plugin_dir)
        msg = f"Unsupported plugin source: {source}"
        raise RuntimeError(msg)

    async def _install_from_pypi(
        self: PluginInstaller,
        metadata: PluginMetadata,
        target_dir: Path,
    ) -> Path:
        """Install plugin from PyPI.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        return await _install_pypi_package(metadata, target_dir)

    async def _install_package_with_pip(
        self: PluginInstaller,
        package_spec: str,
        target_dir: str,
    ) -> None:
        """Install package using pip.

        Args:
            package_spec: Package specification (e.g., ``"package==1.0.0"``).
            target_dir: Directory to install into.

        Raises:
            RuntimeError: If pip installation fails.
        """
        await _run_pip_subprocess(package_spec, target_dir)

    def _copy_installed_files(
        self: PluginInstaller,
        source_dir: str,
        target_dir: Path,
    ) -> None:
        """Copy installed files from source to target directory.

        Args:
            source_dir: Source directory with installed files.
            target_dir: Target directory to copy to.
        """
        _copy_dir_contents(Path(source_dir), target_dir)

    async def _install_from_github(
        self: PluginInstaller,
        metadata: PluginMetadata,
        target_dir: Path,
    ) -> Path:
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
        clone_url, branch = _parse_github_url(metadata.source_url)
        return await self._clone_and_copy_git_repo(clone_url, branch, target_dir)

    async def _install_from_git(
        self: PluginInstaller,
        metadata: PluginMetadata,
        target_dir: Path,
    ) -> Path:
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
        self: PluginInstaller,
        clone_url: str,
        branch: str | None,
        target_dir: Path,
    ) -> Path:
        """Clone git repository and copy files to target directory.

        Args:
            clone_url: Git repository URL to clone.
            branch: Branch to clone (``None`` for default).
            target_dir: Directory to copy files to.

        Returns:
            Path where files were copied.

        Raises:
            RuntimeError: If clone or copy fails.
        """
        await _git_clone_to_dir(clone_url, branch, target_dir)
        return target_dir

    async def _install_from_url(
        self: PluginInstaller,
        metadata: PluginMetadata,
        target_dir: Path,
    ) -> Path:
        """Install plugin from direct URL (zip/tar archive).

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        source_url = metadata.source_url
        if not source_url:
            msg = "URL source is required"
            raise RuntimeError(msg)
        temp_path = await _download_archive(source_url)
        try:
            _extract_archive_file(temp_path, source_url, target_dir)
            logger.info("Successfully installed from URL to: %s", target_dir)
        finally:
            temp_path.unlink(missing_ok=True)
        return target_dir

    async def _download_archive_from_url(self: PluginInstaller, url: str) -> Path:
        """Download archive from URL to temporary file.

        Args:
            url: URL to download from.

        Returns:
            Path to temporary file with downloaded content.

        Raises:
            RuntimeError: If download fails.
        """
        return await _download_archive(url)

    async def _extract_archive(
        self: PluginInstaller,
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
        _extract_archive_file(archive_path, source_url, target_dir)

    async def _install_from_local(
        self: PluginInstaller,
        metadata: PluginMetadata,
        target_dir: Path,
    ) -> Path:
        """Install plugin from local directory.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        source_url = metadata.source_url
        if not source_url:
            msg = "Local source path is required"
            raise RuntimeError(msg)
        source_path = Path(source_url)
        if not source_path.exists():  # noqa: ASYNC240
            msg = f"Local path does not exist: {source_path}"
            raise RuntimeError(msg)
        try:
            _copy_local_path(source_path, target_dir)
            logger.info("Successfully installed from local path to: %s", target_dir)
        except Exception as e:
            msg = f"Failed to install from local path: {e}"
            raise RuntimeError(msg) from e
        return target_dir

    async def install_dependencies(self: PluginInstaller, dependencies: list[str]) -> None:
        """Install plugin dependencies.

        Args:
            dependencies: List of dependency specifications.
        """
        if not dependencies:
            return
        logger.info("Installing %d dependencies", len(dependencies))
        try:
            await _run_pip_deps_subprocess(dependencies)
        except Exception as e:  # noqa: BLE001
            logger.warning("Error installing dependencies: %s", e)
