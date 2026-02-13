"""Tests for 413 error handling and ContextTooLargeError."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIStatusError

from henchman.providers.base import ContextTooLargeError, Message
from henchman.providers.openai_compat import OpenAICompatibleProvider


class TestContextTooLargeError:
    """Tests for ContextTooLargeError exception."""

    def test_error_creation_default_message(self):
        """Error can be created with default message."""
        error = ContextTooLargeError()
        assert "Request too large" in str(error)

    def test_error_creation_custom_message(self):
        """Error can be created with custom message."""
        error = ContextTooLargeError("Custom error message")
        assert str(error) == "Custom error message"

    def test_error_is_exception(self):
        """ContextTooLargeError should be an Exception."""
        error = ContextTooLargeError()
        assert isinstance(error, Exception)

    def test_error_can_be_raised(self):
        """ContextTooLargeError can be raised and caught."""
        with pytest.raises(ContextTooLargeError) as exc_info:
            raise ContextTooLargeError("Test error")
        assert "Test error" in str(exc_info.value)


class TestOpenAICompatible413Handling:
    """Tests for 413 error handling in OpenAICompatibleProvider."""

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return OpenAICompatibleProvider(
            api_key="test-key",
            base_url="https://api.example.com",
            default_model="test-model",
        )

    @pytest.mark.anyio
    async def test_413_error_raises_context_too_large(self, provider):
        """413 status code should raise ContextTooLargeError."""
        # Create a mock 413 response
        mock_response = MagicMock()
        mock_response.status_code = 413
        mock_response.headers = {}

        api_error = APIStatusError(
            message="Request Entity Too Large",
            response=mock_response,
            body={"error": {"message": "Request too large"}},
        )

        # Mock the client to raise 413
        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=api_error,
        ):
            with pytest.raises(ContextTooLargeError) as exc_info:
                async for _ in provider.chat_completion_stream(
                    messages=[Message(role="user", content="test")]
                ):
                    pass

            # Check error message includes helpful guidance
            error_msg = str(exc_info.value)
            assert "start_line" in error_msg or "line" in error_msg.lower()

    @pytest.mark.anyio
    async def test_other_api_errors_not_caught(self, provider):
        """Non-413 API errors should not be converted."""
        # Create a mock 400 response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.headers = {}

        api_error = APIStatusError(
            message="Bad Request",
            response=mock_response,
            body={"error": {"message": "Invalid request"}},
        )

        # Mock the client to raise 400
        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=api_error,
        ):
            with pytest.raises(APIStatusError) as exc_info:
                async for _ in provider.chat_completion_stream(
                    messages=[Message(role="user", content="test")]
                ):
                    pass

            assert exc_info.value.status_code == 400

    @pytest.mark.anyio
    async def test_500_error_not_caught(self, provider):
        """500 server errors should not be converted."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        api_error = APIStatusError(
            message="Internal Server Error",
            response=mock_response,
            body={"error": {"message": "Server error"}},
        )

        with patch.object(
            provider._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=api_error,
        ):
            with pytest.raises(APIStatusError) as exc_info:
                async for _ in provider.chat_completion_stream(
                    messages=[Message(role="user", content="test")]
                ):
                    pass

            assert exc_info.value.status_code == 500


class TestContextTooLargeErrorHandling:
    """Tests for how the application handles ContextTooLargeError."""

    def test_error_inheritance(self):
        """ContextTooLargeError should be catchable as Exception."""
        try:
            raise ContextTooLargeError("test")
        except Exception as e:
            assert isinstance(e, ContextTooLargeError)

    def test_error_message_actionable(self):
        """Default error message should be actionable."""
        error = ContextTooLargeError()
        message = str(error)
        # Should mention file reading best practices
        assert any(word in message.lower() for word in ["line", "range", "context", "large"])
