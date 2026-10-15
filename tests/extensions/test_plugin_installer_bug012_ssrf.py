"""Tests for BUG-012: Missing SSRF Protection in Plugin Archive Download.

Verifies that _download_archive calls validate_url() before making HTTP
requests, and rejects internal/private URLs.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.extensions.plugin_installer import _download_archive
from henchman.tools.security import SSRFError


@pytest.fixture
def mock_aiohttp_session() -> MagicMock:
    """Fixture that patches aiohttp.ClientSession and returns the mock."""
    patcher = patch("henchman.extensions.plugin_installer.aiohttp.ClientSession")
    mock_cls = patcher.start()
    mock_session = MagicMock(spec=object)
    mock_session.get = MagicMock()
    mock_cls.return_value.__aenter__.return_value = mock_session
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.read.return_value = b"archive content"
    mock_response.__aenter__.return_value = mock_response
    mock_session.get.return_value = mock_response
    yield mock_session
    patcher.stop()


class TestDownloadArchiveSSRF:
    """_download_archive rejects internal/private URLs."""

    async def test_private_ip_rejected(self, mock_aiohttp_session: MagicMock) -> None:
        """Link-local IP (169.254.x.x) triggers SSRFError."""
        with pytest.raises(SSRFError, match="Private IP address not allowed"):
            await _download_archive("http://169.254.169.254/latest/meta-data/")

    async def test_localhost_rejected(self, mock_aiohttp_session: MagicMock) -> None:
        """Localhost URL triggers SSRFError."""
        with pytest.raises(SSRFError, match="Localhost URLs are not allowed"):
            await _download_archive("http://localhost:8080/pkg.zip")

    async def test_loopback_rejected(self, mock_aiohttp_session: MagicMock) -> None:
        """Loopback 127.0.0.1 URL triggers SSRFError."""
        with pytest.raises(SSRFError, match="Localhost URLs are not allowed"):
            await _download_archive("http://127.0.0.1/pkg.zip")

    async def test_private_network_rejected(self, mock_aiohttp_session: MagicMock) -> None:
        """Private 10.x.x.x URL triggers SSRFError."""
        with pytest.raises(SSRFError, match="Private IP address not allowed"):
            await _download_archive("http://10.0.0.1/admin")
