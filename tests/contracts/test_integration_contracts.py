"""Contract tests for integration payloads."""

from __future__ import annotations

from henchman.config.schema import VoiceSettings
from henchman.integrations.blueprints import BlueprintFile, IntegrationBlueprint
from henchman.integrations.voice import describe_voice_runtime
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_integration_blueprint_matches_contract(contract_suite) -> None:
    """Serialized IntegrationBlueprint should satisfy its contract."""
    blueprint = IntegrationBlueprint(
        slug="test-slug",
        surface="ide",
        name="Test Blueprint",
        description="A test blueprint",
        files=(
            BlueprintFile(relative_path="test.txt", content="hello"),
        )
    )

    assert_contract_matches(
        payload=serialize_contract_value(blueprint),
        schema_name="integrations/blueprint",
        contract_suite=contract_suite,
    )


def test_voice_runtime_description_matches_contract(contract_suite) -> None:
    """Voice runtime description should satisfy its contract."""
    settings = VoiceSettings(
        preferred_voice="test-voice",
        tts_command=["say", "{text}"],
        stt_command=[],
    )
    payload = describe_voice_runtime(settings)

    assert_contract_matches(
        payload=payload,
        schema_name="integrations/voice_runtime",
        contract_suite=contract_suite,
    )
