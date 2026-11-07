"""Streaming evidence never publishes a credential before its last chunk."""

import json

import pytest

from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor


@pytest.mark.parametrize("secret", ["private-canary-value", 'private-"quoted"', "secret-[REDACTED]-end"])
def test_every_chunk_boundary_masks_registered_secret(secret: str) -> None:
    for value in (secret, json.dumps(secret)[1:-1]):
        text = f"Echo: {value}. Done!"
        for cut in range(len(text) + 1):
            stream = EvidenceStreamRedactor(EvidenceRedactor([secret, "RED"]))
            rendered = stream.feed(text[:cut]) + stream.feed(text[cut:]) + stream.finish()
            assert rendered == "Echo: [REDACTED]. Done!"


@pytest.mark.parametrize("header", ["Authorization", "Proxy-Authorization", "Cookie", "Set-Cookie"])
def test_headers_mask_unknown_values_across_every_boundary(header: str) -> None:
    text = f"Before\n  {header}: Bearer unknown-value\r\nAfter!"
    for cut in range(len(text) + 1):
        stream = EvidenceStreamRedactor(EvidenceRedactor())
        result = stream.feed(text[:cut]) + stream.feed(text[cut:]) + stream.finish()
        assert result == f"Before\n  {header}: [REDACTED]\r\nAfter!"


def test_safe_text_is_immediate_and_incomplete_secret_is_masked_on_close() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor(["private-canary-value"]))
    assert stream.feed("ordinary output!") == "ordinary output!"
    assert stream.feed(" private-canary-") == " "
    assert stream.finish() == "[REDACTED]"
    assert stream.finish() == ""


def test_header_values_are_discarded_without_buffering_the_line() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor())
    assert stream.feed("Authorization:") == "Authorization: [REDACTED]"
    for _ in range(10):
        assert stream.feed("unknown-value" * 1000) == ""
    assert stream.feed("\nDone!") == "\nDone!"
    assert stream.finish() == ""


def test_rotation_and_overlapping_credentials_use_current_shared_policy() -> None:
    policy = EvidenceRedactor(["private", "private-longer"])
    stream = EvidenceStreamRedactor(policy)
    assert stream.feed("private") == ""
    assert stream.feed("-longer!") == "[REDACTED]!"
    policy.register_secret("rotated-canary")
    assert stream.feed(" rotated-") == " "
    assert stream.feed("canary!") == "[REDACTED]!"
    assert stream.finish() == ""


def test_partial_header_is_ordinary_text_and_markers_stay_stable() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor(["RED"]))
    assert stream.feed("[RED") == ""
    assert stream.feed("ACTED]\nAuth") == "[REDACTED]\n"
    assert stream.finish() == "Auth"


def test_headers_only_start_at_real_line_boundaries() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor())
    assert stream.feed("Ordinary ") == "Ordinary "
    assert stream.feed("Authorization: example!") == "Authorization: example!"
    assert stream.finish() == ""


@pytest.mark.parametrize("secret", ["TED]canary", "REDACTED]canary"])
def test_secret_starting_inside_marker_remains_private(secret: str) -> None:
    text = "[REDACTED]canary!"
    for cut in range(len(text) + 1):
        stream = EvidenceStreamRedactor(EvidenceRedactor([secret]))
        output = stream.feed(text[:cut]) + stream.feed(text[cut:]) + stream.finish()
        assert secret not in output


@pytest.mark.parametrize("space", ["\u00a0", "\v", "\f", "\u2003"])
def test_split_header_supports_all_horizontal_whitespace(space: str) -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor())
    output = stream.feed(f"Authorization{space}")
    output += stream.feed(": Bearer unknown-canary\n") + stream.finish()
    assert "unknown-canary" not in output


def test_complete_crossing_secret_wins_over_longer_incomplete_crossing() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor(["REDACTED]canary-longer", "TED]canary"]))
    output = stream.feed("[REDACTED]canary") + stream.finish(interrupted=False)
    assert "TED]canary" not in output


def test_normal_close_preserves_marker_with_incomplete_crossing_candidate() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor(["RED", "REDACTED]canary"]))
    assert stream.feed("[REDACTED]") + stream.finish(interrupted=False) == "[REDACTED]"


def test_unbounded_header_whitespace_is_conservatively_masked() -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor())
    output = stream.feed("Authorization")
    for _ in range(100):
        output += stream.feed(" " * 128)
    assert output == "[REDACTED]"
    output += stream.feed(": unknown-canary\nordinary!") + stream.finish()
    assert output == "[REDACTED]\nordinary!"


@pytest.mark.parametrize("secret", ["Authorization:", "Authorization", "orization:", "Auth"])
def test_known_credential_matching_header_syntax_is_still_private(secret: str) -> None:
    stream = EvidenceStreamRedactor(EvidenceRedactor([secret]))
    output = stream.feed("Authorization: unknown-value\n") + stream.finish()
    assert secret not in output
    assert "unknown-value" not in output
