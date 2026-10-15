"""Configured provider selection must not depend on unrelated credentials."""

from unittest.mock import patch

import pytest

from henchman.config.schema import ProviderSettings
from tests.providers.stream_helpers import SDKResponse


def create(settings: ProviderSettings, **kwargs):
    from henchman.providers.factory import create_configured_provider

    return create_configured_provider(settings, **kwargs)


@pytest.mark.parametrize("other_key", ["DEEPSEEK_API_KEY", "HENCHMAN_API_KEY"])
def test_selected_openrouter_preserves_settings_with_unrelated_key(other_key: str) -> None:
    settings = ProviderSettings(
        default="openrouter",
        openrouter={
            "api_key": "selected-key",
            "model": "vendor/coder",
            "base_url": "https://router.invalid/v1",
        },
    )
    with patch.dict("os.environ", {other_key: "unrelated-key"}, clear=True):
        provider = create(settings)
    assert provider.name == "openrouter"
    assert provider.api_key == "selected-key"
    assert provider.default_model == "vendor/coder"
    assert provider.base_url == "https://router.invalid/v1"


def test_model_override_does_not_mutate_saved_settings() -> None:
    settings = ProviderSettings(openrouter={"api_key": "key", "model": "saved/model"})
    provider = create(settings, provider_name="openrouter", model="temporary/model")
    assert provider.default_model == "temporary/model"
    assert settings.openrouter["model"] == "saved/model"


@pytest.mark.parametrize("model", [42, "", "   "])
def test_invalid_model_is_rejected_before_runtime_can_switch(model: object) -> None:
    settings = ProviderSettings(default="openrouter", openrouter={"api_key": "key", "model": model})
    with pytest.raises(ValueError, match="model"):
        create(settings)


@pytest.mark.parametrize("name", ["openai_compat", "together", "groq", "fireworks", "openai"])
def test_compatible_config_model_is_translated_to_constructor(name: str) -> None:
    settings = ProviderSettings(
        **{
            "default": name,
            name: {
                "api_key": "key",
                "base_url": "https://compatible.invalid/v1",
                "model": "custom-model",
            },
        }
    )
    provider = create(settings)
    assert provider.default_model == "custom-model"
    assert provider.base_url == "https://compatible.invalid/v1"


def test_legacy_default_model_setting_is_preserved() -> None:
    settings = ProviderSettings(
        default="openai_compat",
        openai_compat={
            "api_key": "key",
            "base_url": "https://compatible.invalid/v1",
            "default_model": "legacy-model",
        },
    )
    assert create(settings).default_model == "legacy-model"


def test_deepseek_preserves_compatible_endpoint_and_request_options() -> None:
    settings = ProviderSettings(deepseek={
        "api_key": "key", "model": "deepseek-coder", "base_url": "https://proxy.invalid/v1",
        "temperature": 0.3,
    })
    provider = create(settings)
    assert provider.base_url == "https://proxy.invalid/v1"
    assert provider.default_model == "deepseek-coder"
    assert provider.request_defaults == {"temperature": 0.3}


def test_ollama_needs_no_cloud_key_and_uses_api_path() -> None:
    with patch.dict("os.environ", {"HENCHMAN_API_KEY": "cloud-key"}, clear=True):
        provider = create(ProviderSettings(default="ollama"))
    assert provider.name == "ollama"
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.api_key == "ollama"


def test_ollama_host_is_used_when_endpoint_not_configured() -> None:
    with patch.dict("os.environ", {"OLLAMA_HOST": "http://local.invalid:11434/v1"}, clear=True):
        provider = create(ProviderSettings(default="ollama"))
    assert provider.base_url == "http://local.invalid:11434/v1"


@pytest.mark.parametrize("endpoint", ["http://local.invalid:11434", "http://local.invalid:11434/"])
def test_saved_ollama_server_origin_targets_compatible_api(endpoint: str) -> None:
    provider = create(ProviderSettings(default="ollama", ollama={"base_url": endpoint}))
    assert provider.base_url == "http://local.invalid:11434/v1"


def test_ollama_custom_proxy_path_is_preserved() -> None:
    provider = create(
        ProviderSettings(default="ollama", ollama={"base_url": "https://local.invalid/proxy/v1"})
    )
    assert provider.base_url == "https://local.invalid/proxy/v1"


@pytest.mark.parametrize(
    "name,variable",
    [
        ("openrouter", "OPENROUTER_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("together", "TOGETHER_API_KEY"),
        ("groq", "GROQ_API_KEY"),
        ("fireworks", "FIREWORKS_API_KEY"),
    ],
)
def test_provider_specific_environment_key_precedes_generic(name: str, variable: str) -> None:
    options = (
        {"base_url": "https://compatible.invalid/v1", "model": "model"}
        if name in {"together", "groq", "fireworks"}
        else {}
    )
    settings = ProviderSettings(**{"default": name, name: options})
    with patch.dict(
        "os.environ", {variable: "specific", "HENCHMAN_API_KEY": "generic"}, clear=True
    ):
        provider = create(settings)
    assert provider._client.api_key == "specific"


def test_environment_key_reference_is_resolved_without_changing_settings() -> None:
    settings = ProviderSettings(
        default="openrouter", openrouter={"api_key": "${CUSTOM_ROUTER_KEY}"}
    )
    with patch.dict("os.environ", {"CUSTOM_ROUTER_KEY": "resolved-key"}, clear=True):
        assert create(settings).api_key == "resolved-key"
    assert settings.openrouter["api_key"] == "${CUSTOM_ROUTER_KEY}"


def test_missing_referenced_key_is_reported_without_generic_fallback() -> None:
    settings = ProviderSettings(
        default="openrouter", openrouter={"api_key": "${CUSTOM_ROUTER_KEY}"}
    )
    with (
        patch.dict("os.environ", {"HENCHMAN_API_KEY": "wrong-account"}, clear=True),
        pytest.raises(ValueError, match="CUSTOM_ROUTER_KEY"),
    ):
        create(settings)


def test_missing_remote_key_names_selected_provider() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ValueError, match="OPENROUTER_API_KEY"),
    ):
        create(ProviderSettings(default="openrouter"))


def test_unknown_provider_does_not_fall_back() -> None:
    with pytest.raises(ValueError, match="not registered"):
        create(ProviderSettings(default="unknown"))


def test_compatible_missing_endpoint_has_actionable_error() -> None:
    settings = ProviderSettings(
        default="openai_compat", openai_compat={"api_key": "key", "model": "model"}
    )
    with pytest.raises(ValueError, match="base_url"):
        create(settings)


def test_local_compatible_endpoint_can_be_keyless() -> None:
    settings = ProviderSettings(
        default="openai_compat",
        openai_compat={"base_url": "http://localhost:8080/v1", "model": "local"},
    )
    with patch.dict("os.environ", {}, clear=True):
        provider = create(settings)
    assert provider.api_key == ""


@pytest.mark.asyncio
async def test_openrouter_saved_request_options_reach_sdk_and_overrides_are_per_call() -> None:
    from unittest.mock import AsyncMock

    from henchman.providers.base import Message

    settings = ProviderSettings(
        default="openrouter",
        openrouter={
            "api_key": "key",
            "model": "vendor/coder",
            "temperature": 0.2,
            "max_tokens": 2048,
            "extra_body": {"provider": {"require_parameters": True}},
        },
    )
    provider = create(settings)

    async def stream():
        if False:
            yield

    with patch.object(
        provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as request:
        request.side_effect = lambda **_kwargs: SDKResponse(stream())
        messages = [Message(role="user", content="hello")]
        async for _ in provider.chat_completion_stream(messages, temperature=0.5):
            pass
        assert request.call_args.kwargs["temperature"] == 0.5
        assert request.call_args.kwargs["max_tokens"] == 2048
        assert request.call_args.kwargs["extra_body"] == {"provider": {"require_parameters": True}}
        async for _ in provider.chat_completion_stream(messages):
            pass
        assert request.call_args.kwargs["temperature"] == 0.2
    assert settings.openrouter["temperature"] == 0.2


@pytest.mark.parametrize("reserved", ["stream", "messages", "tools"])
def test_request_defaults_cannot_replace_agent_protocol(reserved: str) -> None:
    settings = ProviderSettings(
        default="openrouter", openrouter={"api_key": "key", reserved: False}
    )
    with pytest.raises(ValueError, match="request defaults"):
        create(settings)
