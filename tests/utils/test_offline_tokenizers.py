"""Tokenizer runtime works in a fresh process without cache or network access."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("cache_disabled", [False, True])
def test_token_counter_and_rag_work_in_a_cold_offline_process(tmp_path, cache_disabled):
    cache = tmp_path / "empty-token-cache"
    cache.mkdir()
    script = r'''
import os, socket
import tiktoken.load
def blocked(*args, **kwargs):
    raise AssertionError("Tokenizer attempted network or an external vocabulary loader")
socket.create_connection = blocked
socket.getaddrinfo = blocked
socket.socket.connect = blocked
tiktoken.load.read_file = blocked
from henchman.utils.tokens import TokenCounter
from henchman.rag.chunker import TextChunker
original_environment = dict(os.environ)
assert TokenCounter.count_text("Hello, world!") == 4
assert TokenCounter._get_encoding("gpt-4").encode("Hello, world!") == [9906, 11, 1917, 0]
assert TokenCounter._get_encoding("gpt-4o").encode("Hello, world!") == [13225, 11, 2375, 0]
assert TokenCounter.count_text("Hello, world!", model="unknown-local-model") == 4
for name in ("cl100k_base", "o200k_base", "o200k_harmony"):
    chunker = TextChunker(target_tokens=12, overlap_tokens=2, encoding_name=name)
    assert chunker.count_tokens("Hello, world!") == 4
    assert chunker.chunk_text("def hello():\n    return 42\n" * 3, "code.py")
assert dict(os.environ) == original_environment
print("offline tokenizer runtime verified")
'''
    environment = dict(os.environ, TIKTOKEN_CACHE_DIR="" if cache_disabled else str(cache), DATA_GYM_CACHE_DIR=str(cache),
                       PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "offline tokenizer runtime verified"
    assert not list(cache.iterdir())


@pytest.mark.parametrize("name,expected", [
    ("cl100k_base", [755, 24748, 4019, 262, 471, 330, 9468, 234, 235, 57668, 53901, 702]),
    ("o200k_base", [1314, 40617, 8595, 271, 622, 392, 64364, 235, 177519, 1092]),
    ("o200k_harmony", [1314, 40617, 8595, 271, 622, 392, 64364, 235, 177519, 1092]),
])
def test_bundled_token_ids_match_upstream_reference(name, expected):
    from henchman.utils.token_encodings import offline_encoding

    text = 'def hello():\n    return "🌍你好"\n'
    encoding = offline_encoding(name)
    assert encoding.encode(text) == expected
    assert encoding.decode(expected) == text
    assert offline_encoding(name) is encoding


def test_special_token_policy_matches_upstream():
    from henchman.utils.token_encodings import offline_encoding

    encoding = offline_encoding("o200k_harmony")
    assert encoding.encode("<|start|>", allowed_special="all") == [200006]
    with pytest.raises(ValueError, match="disallowed"):
        encoding.encode("<|start|>")


@pytest.mark.parametrize("name", ["r50k_base", "p50k_base", "gpt2", "not-an-encoding"])
def test_unbundled_encoding_fails_without_download_or_substitution(monkeypatch, name):
    import tiktoken

    from henchman.rag.chunker import TextChunker
    from henchman.utils.token_encodings import offline_encoding

    def blocked(*_args, **_kwargs):
        pytest.fail("Unexpected tiktoken downloader entry")

    monkeypatch.setattr(tiktoken, "get_encoding", blocked)
    with pytest.raises(ValueError, match="bundled"):
        offline_encoding(name)
    with pytest.raises(ValueError, match="bundled"):
        TextChunker(encoding_name=name)


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_corrupt_packaged_vocabulary_fails_closed(tmp_path, monkeypatch, missing):
    from henchman.utils import token_encodings

    directory = tmp_path / "data/tokenizers"
    directory.mkdir(parents=True)
    if not missing:
        (directory / "cl100k_base.tiktoken").write_bytes(b"corrupt vocabulary")
    monkeypatch.setattr(token_encodings, "files", lambda _package: tmp_path)
    token_encodings.offline_encoding.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="bundled tokenizer"):
            token_encodings.offline_encoding("cl100k_base")
    finally:
        token_encodings.offline_encoding.cache_clear()


def test_model_name_resolution_supports_minimum_tiktoken_without_loading_vocabularies(monkeypatch):
    import tiktoken
    import tiktoken.model

    from henchman.utils.tokens import TokenCounter

    monkeypatch.delattr(tiktoken, "encoding_name_for_model", raising=False)
    monkeypatch.delattr(tiktoken.model, "MODEL_TO_ENCODING", raising=False)
    monkeypatch.delattr(tiktoken.model, "MODEL_PREFIX_TO_ENCODING", raising=False)
    monkeypatch.setattr(tiktoken.model, "_MODEL_TO_ENCODING", {"gpt-4": "cl100k_base"}, raising=False)
    monkeypatch.setattr(tiktoken.model, "_MODEL_PREFIX_TO_ENCODING", {"gpt-4-": "cl100k_base"}, raising=False)
    assert TokenCounter.count_text("Hello, world!", model="gpt-4") == 4
    assert TokenCounter.count_text("Hello, world!", model="gpt-4-0314") == 4
    assert TokenCounter.count_text("Hello, world!", model="unknown-local") == 4
