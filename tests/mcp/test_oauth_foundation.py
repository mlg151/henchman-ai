"""OAuth configuration and immutable authority are separate from stdio credentials."""

import pytest
from pydantic import ValidationError

from henchman.config.schema import McpServerConfig
from henchman.mcp.config import McpServerConfig as LegacyConfig


def configuration(**oauth):
    return McpServerConfig(transport="streamable_http", url="https://resource.example/mcp", oauth={
        "issuer": "https://issuer.example/tenant", "client_id": "public-client", **oauth,
    })


def test_oauth_configuration_roundtrips_without_stdio_or_secret_fields():
    config = configuration()
    assert config.oauth.issuer == "https://issuer.example/tenant"
    assert config.oauth.resource is None
    assert config.oauth.allowed_endpoint_origins == []
    assert LegacyConfig.from_dict(config.model_dump()).to_dict() == config.model_dump()
    with pytest.raises(ValidationError):
        McpServerConfig(command="fixture", oauth=config.oauth)
    with pytest.raises(ValidationError):
        configuration(client_secret="private-canary")


@pytest.mark.parametrize("issuer", ["http://127.0.0.1:1234", "https://user:password@example.com",
                                    "https://issuer.example/?private=canary", "https://issuer.example/#fragment"])
def test_invalid_issuer_configuration_is_rejected(issuer):
    with pytest.raises(ValidationError):
        configuration(issuer=issuer)


@pytest.mark.parametrize("origin", ["https://issuer.example/path", "http://127.0.0.1:1234", "https://issuer.example?x=1"])
def test_additional_origins_are_exact_https_authorities(origin):
    with pytest.raises(ValidationError):
        configuration(allowed_endpoint_origins=[origin])


def test_binding_detaches_configuration_and_preserves_exact_issuer():
    from henchman.mcp.oauth import OAuthBinding

    config = configuration(issuer="https://ISSUER.example:443/tenant", allowed_endpoint_origins=["https://other.example"])
    binding = OAuthBinding.from_config("fixture", config)
    original = binding.fingerprint
    config.oauth.client_id = "changed"
    config.oauth.allowed_endpoint_origins.append("https://later.example")
    assert binding.client_id == "public-client"
    assert binding.issuer == "https://ISSUER.example:443/tenant"
    assert binding.allowed_endpoint_origins == ("https://other.example",)
    assert binding.resource == "https://resource.example/mcp"
    assert binding.fingerprint == original
    assert OAuthBinding.from_config("fixture", config).fingerprint != original


def test_explicit_resource_must_cover_endpoint_on_same_authority():
    from henchman.mcp.oauth import OAuthBinding, OAuthError

    assert OAuthBinding.from_config("fixture", configuration(resource="https://resource.example")).resource == "https://resource.example"
    for resource in ("https://other.example", "https://resource.example/other", "https://resource.example/m"):
        with pytest.raises(OAuthError):
            OAuthBinding.from_config("fixture", configuration(resource=resource))


def test_direct_binding_constructor_cannot_bypass_authority_validation():
    from henchman.mcp.oauth import OAuthBinding, OAuthError

    with pytest.raises(OAuthError):
        OAuthBinding("fixture", "https://resource.example", "http://issuer.example", "https://other.example", "public")


def test_nested_oauth_configuration_errors_do_not_echo_supplied_credentials():
    with pytest.raises(ValidationError) as caught:
        configuration(client_secret="private-error-canary")
    assert "private-error-canary" not in str(caught.value)


@pytest.mark.parametrize("constructor", ["direct", "from_config"])
@pytest.mark.parametrize("endpoint,resource", [
    ("https://resource.example/scope/../outside", "https://resource.example/scope"),
    ("https://resource.example/scope/./child", "https://resource.example/scope"),
    ("https://resource.example/scope/../outside/child", "https://resource.example/scope/../outside"),
])
def test_transport_normalized_paths_cannot_escape_or_redefine_resource_scope(constructor, endpoint, resource):
    import httpx2

    from henchman.mcp.oauth import OAuthBinding, OAuthError

    assert str(httpx2.URL(endpoint)) != endpoint
    with pytest.raises(OAuthError):
        if constructor == "direct":
            OAuthBinding("fixture", endpoint, "https://issuer.example", resource, "public")
        else:
            config = configuration()
            config.url = endpoint
            config.oauth.resource = resource
            OAuthBinding.from_config("fixture", config)
