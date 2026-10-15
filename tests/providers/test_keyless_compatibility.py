"""Compatible endpoints work with SDKs that require a nonempty credential."""

import pytest

from henchman.providers.openai_compat import OpenAICompatibleProvider


@pytest.mark.parametrize("configured_key", ["", "explicit-endpoint-key"])
async def test_sdk_credential_is_explicit_without_changing_saved_key(
    monkeypatch: pytest.MonkeyPatch, configured_key: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-sdk-key")
    provider = OpenAICompatibleProvider(
        api_key=configured_key, base_url="http://127.0.0.1:8080/v1", default_model="local/model",
    )
    try:
        assert provider.api_key == configured_key
        assert provider.config.api_key == configured_key
        assert provider._client.api_key, "Keyless endpoints need an SDK-compatible placeholder"
        assert provider._client.api_key != "unrelated-sdk-key"
        if configured_key:
            assert provider._client.api_key == configured_key
    finally:
        await provider._client.close()
