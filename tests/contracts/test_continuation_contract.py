"""Strict portable shape for non-rendered provider continuation evidence."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from henchman.providers.base import Message, StreamChunk
from henchman.providers.continuation import ContinuationEnvelope
from tests.contracts.helpers import assert_contract_matches


def envelope():
    provider = SimpleNamespace(name="deepseek", default_model="model", api_key="offline-test",
                               _client=SimpleNamespace(base_url="https://offline.invalid/v1"))
    return ContinuationEnvelope.create(provider, "reason").to_dict()


@pytest.mark.parametrize("schema,instance", [("runtime/message", Message("assistant", "Done")),
                                             ("runtime/stream_chunk", StreamChunk()),
                                             ("runtime/session_message", Message("assistant", "Done"))])
def test_continuation_contract_accepts_omitted_null_and_versioned_payload(contract_suite, schema, instance):
    payload = asdict(instance)
    for value in (None, envelope()):
        payload["continuation"] = value
        assert_contract_matches(payload=payload, schema_name=schema, contract_suite=contract_suite)
    payload.pop("continuation")
    assert_contract_matches(payload=payload, schema_name=schema, contract_suite=contract_suite)
    for value in ("opaque", {**envelope(), "version": 2}, {**envelope(), "unknown": True}):
        payload["continuation"] = value
        with pytest.raises(AssertionError):
            assert_contract_matches(payload=payload, schema_name=schema, contract_suite=contract_suite)
