"""Hash-verified packaged tokenizers with no downloader or cache-directory writes.

Encoding definitions are adapted from OpenAI tiktoken 0.12.0 (MIT). Original
license, vocabulary source URLs, sizes and SHA-256 hashes ship in
``henchman/data/tokenizers``. tiktoken's public Encoding engine is unchanged.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from importlib.resources import files

import tiktoken
import tiktoken.model

_VOCABULARIES = {
    "cl100k_base": ("223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7", 100256),
    "o200k_base": ("446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d", 199998),
}
_CL100K_PATTERN = r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s"""
_O200K_PATTERN = "|".join([
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"\p{N}{1,3}", r" ?[^\s\p{L}\p{N}]+[\r\n/]*", r"\s*[\r\n]+", r"\s+(?!\S)", r"\s+",
])


def encoding_name_for_model(model: str) -> str:
    """Resolve upstream model metadata without invoking its vocabulary loader.

    The declared tiktoken 0.5 minimum predates the public name-only helper; its
    existing private maps carry the same lookup semantics. Unknown models still
    raise KeyError so callers can choose their documented default estimate.
    """
    resolver = getattr(tiktoken, "encoding_name_for_model", None)
    if resolver is not None:
        return str(resolver(model))
    names: dict[str, str] = getattr(tiktoken.model, "_MODEL_TO_ENCODING", {})
    prefixes: dict[str, str] = getattr(tiktoken.model, "_MODEL_PREFIX_TO_ENCODING", {})
    if model in names:
        return names[model]
    for prefix, name in prefixes.items():
        if model.startswith(prefix):
            return name
    raise KeyError(f"No tokenizer metadata for model {model!r}")


def _ranks(name: str) -> dict[bytes, int]:
    digest, expected_count = _VOCABULARIES[name]
    try:
        content = files("henchman").joinpath("data", "tokenizers", f"{name}.tiktoken").read_bytes()
    except OSError as error:
        raise RuntimeError("Missing bundled tokenizer resource; reinstall Henchman from a complete wheel") from error
    if hashlib.sha256(content).hexdigest() != digest:
        raise RuntimeError("Corrupt bundled tokenizer resource; reinstall Henchman from a verified wheel")
    ranks = {base64.b64decode(token, validate=True): int(rank)
             for token, rank in (line.split() for line in content.splitlines())}
    if len(ranks) != expected_count or set(ranks.values()) != set(range(expected_count)):
        raise RuntimeError("Invalid bundled tokenizer vocabulary")
    return ranks


@lru_cache(maxsize=3)
def offline_encoding(name: str = "cl100k_base") -> tiktoken.Encoding:
    """Load a supported encoding solely from packaged, integrity-checked bytes.

    Unbundled/legacy names fail explicitly. This does not change tiktoken's
    registry, environment, or behavior for independent callers of its API.
    """
    if name not in {"cl100k_base", "o200k_base", "o200k_harmony"}:
        raise ValueError(
            f"Tokenizer {name!r} is not bundled for offline use; choose cl100k_base, o200k_base, or o200k_harmony"
        )
    base = "cl100k_base" if name == "cl100k_base" else "o200k_base"
    special = {"<|endoftext|>": 199999, "<|endofprompt|>": 200018}
    if name == "cl100k_base":
        special = {"<|endoftext|>": 100257, "<|fim_prefix|>": 100258,
                   "<|fim_middle|>": 100259, "<|fim_suffix|>": 100260, "<|endofprompt|>": 100276}
    elif name == "o200k_harmony":
        special.update({"<|startoftext|>": 199998, "<|reserved_200000|>": 200000,
                        "<|reserved_200001|>": 200001, "<|return|>": 200002, "<|constrain|>": 200003,
                        "<|reserved_200004|>": 200004, "<|channel|>": 200005, "<|start|>": 200006,
                        "<|end|>": 200007, "<|message|>": 200008, "<|reserved_200009|>": 200009,
                        "<|reserved_200010|>": 200010, "<|reserved_200011|>": 200011, "<|call|>": 200012})
        special.update({f"<|reserved_{index}|>": index for index in range(200013, 201088)})
    return tiktoken.Encoding(name=name, pat_str=_CL100K_PATTERN if base == "cl100k_base" else _O200K_PATTERN,
                             mergeable_ranks=_ranks(base), special_tokens=special)
