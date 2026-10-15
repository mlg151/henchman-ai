"""Contract tests for the Settings model hierarchy.

These tests validate that serialised Settings models (and their sub-models)
produce JSON payloads that conform to their published JSON Schema contracts.

Every consumer of ``henchman.config.schema`` implicitly depends on the shape
of these models.  The contracts here guard against accidental breaking
changes to that shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from henchman.config.schema import (
    AgentConfig,
    AgentSettings,
    ApiConfig,
    ChatConfig,
    ContextSettings,
    DiscordSettings,
    McpServerConfig,
    ProviderSettings,
    RagSettings,
    Settings,
    SlackSettings,
    ToolSettings,
    UISettings,
    VoiceSettings,
)
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# Fixtures — representative model instances with non-default values
# ---------------------------------------------------------------------------


@pytest.fixture
def full_settings() -> Settings:
    """A Settings instance exercising every sub-model with non-default values."""
    return Settings(
        providers=ProviderSettings(
            default="anthropic",
            anthropic={"model": "claude-sonnet-4-20250514"},
            openai={"model": "gpt-4o"},
        ),
        tools=ToolSettings(
            auto_approve_read=False,
            shell_timeout=60,
            sandbox="docker",
        ),
        ui=UISettings(
            output_style="verbose",
            theme="monokai",
            show_line_numbers=False,
            mcp_logging=True,
            accessible_mode=True,
            keybindings={"c-c": "abort", "c-d": "exit", "c-l": "clear"},
            style_overrides={"border": "blue"},
        ),
        context=ContextSettings(
            max_tokens=16000,
            compaction_threshold=0.8,
            auto_compact=True,
            intelligent_context=True,
            importance_threshold=0.3,
            cluster_similarity_threshold=0.65,
            adaptive_compression=False,
        ),
        mcp_servers={
            "filesystem": McpServerConfig(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                trusted=True,
            ),
        },
        rag=RagSettings(
            enabled=True,
            chunk_size=1024,
            chunk_overlap=128,
            top_k=10,
            embedding_model="BAAI/bge-small-en-v1.5",
            cache_dir="/tmp/rag_cache",
            file_extensions=[".py", ".md", ".txt"],
        ),
        agents=AgentSettings(
            team_preset="custom",
            agents={
                "coder": AgentConfig(
                    name="Coder",
                    role="coder",
                    description="Writes production code",
                    system_prompt="You are a senior engineer.",
                    tools=["read", "write", "shell", "search"],
                    provider="anthropic",
                    model="claude-sonnet-4-20250514",
                    auto_approve=["read", "search"],
                    can_delegate_to=["reviewer"],
                    enabled=True,
                ),
            },
            max_delegation_depth=5,
            max_delegation_turns=200,
            shared_context_max_tokens=4000,
            max_delegation_retries=2,
        ),
        api=ApiConfig(
            require_auth=True,
            api_keys=["sk-abc123"],
            rate_limits={"default": "1000/hour", "admin": "10000/hour"},
            cors={"enabled": True, "origins": ["https://example.com"]},
        ),
        chat=ChatConfig(
            discord=DiscordSettings(
                enabled=True,
                token="discord-token-xyz",
                allowed_user_id="123456789",
                allowed_channel_ids=["987654321"],
                mention_only=False,
                system_prompt="You are a Discord helper bot.",
            ),
            slack=SlackSettings(
                enabled=True,
                app_token="xapp-token",
                bot_token="xoxb-token",
                signing_secret="abc-secret",
                allowed_user_id="U12345",
            ),
        ),
        voice=VoiceSettings(
            enabled=True,
            preferred_voice="en-US-JennyNeural",
            tts_command=["edge-tts", "--voice", "{voice}", "--text", "{text}"],
            stt_command=["whisper", "--model", "base", "--input", "{input}"],
        ),
    )


@pytest.fixture
def default_settings() -> Settings:
    """A Settings instance relying entirely on defaults."""
    return Settings()


# ---------------------------------------------------------------------------
# 1. Root Settings contract
# ---------------------------------------------------------------------------


class TestSettingsContract:
    """The top-level ``Settings.model_dump()`` must satisfy the settings contract."""

    def test_full_serialised_shape_matches_contract(
        self, contract_suite: object, full_settings: Settings
    ) -> None:
        """A fully-populated Settings must conform to the published schema."""
        payload = full_settings.model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/settings",
        )

    def test_default_serialised_shape_matches_contract(
        self, contract_suite: object, default_settings: Settings
    ) -> None:
        """A default Settings must also conform (all optionals exercised)."""
        payload = default_settings.model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/settings",
        )

    def test_settings_yaml_roundtrip_preserves_contract(
        self, contract_suite: object, full_settings: Settings, tmp_path: Path
    ) -> None:
        """Settings serialised to YAML and reloaded must still match the contract."""
        # Serialise to YAML
        data = full_settings.model_dump(mode="json")
        yaml_path = tmp_path / "settings.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        # Reload
        with open(yaml_path) as f:
            reloaded = yaml.safe_load(f)

        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="config/settings",
        )


# ---------------------------------------------------------------------------
# 2. Sub-model contracts (independent shape validation)
# ---------------------------------------------------------------------------


class TestProviderSettingsContract:
    """ProviderSettings payload must satisfy its contract."""

    def test_provider_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ProviderSettings(
            default="anthropic",
            anthropic={"model": "claude-sonnet-4-20250514"},
            openai={"model": "gpt-4o"},
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/provider_settings",
        )


class TestToolSettingsContract:
    """ToolSettings payload must satisfy its contract."""

    def test_tool_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ToolSettings(
            auto_approve_read=False, shell_timeout=120, sandbox="docker"
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/tool_settings",
        )


class TestUISettingsContract:
    """UISettings payload must satisfy its contract."""

    def test_ui_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = UISettings(
            output_style="verbose",
            theme="dracula",
            show_line_numbers=False,
            mcp_logging=True,
            accessible_mode=True,
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/ui_settings",
        )


class TestContextSettingsContract:
    """ContextSettings payload must satisfy its contract."""

    def test_context_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ContextSettings(
            max_tokens=32000,
            compaction_threshold=0.9,
            intelligent_context=True,
            importance_threshold=0.4,
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/context_settings",
        )


class TestMcpServerConfigContract:
    """McpServerConfig payload must satisfy its contract."""

    def test_mcp_server_config_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = McpServerConfig(
            command="uvx",
            args=["mcp-server", "--port", "8080"],
            env={"DEBUG": "1"},
            trusted=True,
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/mcp_server_config",
        )


class TestAgentConfigContract:
    """AgentConfig payload must satisfy its contract."""

    def test_agent_config_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentConfig(
            name="Reviewer",
            role="reviewer",
            description="Reviews pull requests",
            system_prompt="You are a code reviewer.",
            tools=["read", "search", "patch"],
            provider="openai",
            model="gpt-4o",
            auto_approve=["read"],
            can_delegate_to=[],
            enabled=True,
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/agent_config",
        )


class TestAgentSettingsContract:
    """AgentSettings payload must satisfy its contract."""

    def test_agent_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentSettings(
            team_preset="custom",
            agents={
                "reviewer": AgentConfig(
                    name="Reviewer",
                    role="reviewer",
                    description="Reviews PRs",
                    tools=["read", "patch"],
                ),
            },
            max_delegation_depth=5,
            max_delegation_turns=200,
            shared_context_max_tokens=4000,
            max_delegation_retries=2,
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/agent_settings",
        )


class TestRagSettingsContract:
    """RagSettings payload must satisfy its contract."""

    def test_rag_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = RagSettings(
            enabled=True,
            chunk_size=2048,
            chunk_overlap=256,
            top_k=20,
            embedding_model="BAAI/bge-large-en-v1.5",
            cache_dir="/custom/cache",
            file_extensions=[".py", ".rs"],
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/rag_settings",
        )


class TestApiConfigContract:
    """ApiConfig payload must satisfy its contract."""

    def test_api_config_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ApiConfig(
            require_auth=True,
            api_keys=["sk-xyz"],
            rate_limits={"default": "1000/hour"},
            cors={"enabled": True, "origins": ["*"]},
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/api_config",
        )


class TestDiscordSettingsContract:
    """DiscordSettings payload must satisfy its contract."""

    def test_discord_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DiscordSettings(
            enabled=True,
            token="discord-token",
            allowed_user_id="12345",
            allowed_channel_ids=["98765"],
            mention_only=False,
            system_prompt="Custom prompt",
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/discord_settings",
        )


class TestVoiceSettingsContract:
    """VoiceSettings payload must satisfy its contract."""

    def test_voice_settings_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = VoiceSettings(
            enabled=True,
            preferred_voice="en-US-JennyNeural",
            tts_command=["edge-tts", "-v", "{voice}", "-t", "{text}"],
            stt_command=["whisper", "-i", "{input}"],
        ).model_dump(mode="json")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="config/voice_settings",
        )
