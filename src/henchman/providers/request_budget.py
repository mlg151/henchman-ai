"""Portable, approximate request accounting without provider credentials or I/O."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from henchman.utils.tokens import REPLY_PRIMER_TOKENS, TOKENS_PER_MESSAGE, TokenCounter


@dataclass(frozen=True)
class OutputBudget:
    """Output reservation and the per-request options that enforce that cap."""

    output_tokens: int
    request_options: dict[str, Any]


def validate_output_tokens(value: object) -> int:
    """Require a finite positive integer cap without echoing configuration values."""
    if type(value) is not int or value <= 0:
        raise ValueError("Output token cap must be a positive integer")
    return value


def estimate_serialized_input(payload: dict[str, Any], *, model: str | None = None) -> int:
    """Estimate canonical input JSON plus three tokens per message and reply.

    The framing allowance uses the existing token-counter constants. Tokenization
    and server templates vary: this is not a server-exact count or a bound on
    arbitrary provider extensions. Callers pass only known input-bearing fields,
    never credentials, endpoints, headers, or the complete SDK request options.
    """
    text = json.dumps(payload, ensure_ascii=False)
    messages = payload.get("messages", [])
    return (
        TokenCounter.count_text(text, model=model)
        + TOKENS_PER_MESSAGE * len(messages)
        + REPLY_PRIMER_TOKENS
    )
