import importlib
from unittest.mock import patch
import label_index


def test_normalization_and_duplicates():
    assert label_index.unique_labels(["  Red Fox ", "RED   FOX", "Blue Bird"]) == ["red-fox", "blue-bird"]


def test_empty_order_and_unicode():
    assert label_index.unique_labels(["", " ", "Zoo", "Straße", "STRASSE", "Apple"]) == ["zoo", "strasse", "apple"]
    assert label_index.unique_labels([]) == []


def test_input_unchanged():
    values = [" B ", "A", "b"]
    before = list(values)
    assert label_index.unique_labels(values) == ["b", "a"]
    assert values == before


def test_calls_existing_helper():
    calls = []
    def existing(value):
        calls.append(value)
        return {"one": "shared", "two": "shared", "three": "other"}[value]
    with patch("normalization.normalize_label", existing):
        importlib.reload(label_index)
        assert label_index.unique_labels(["one", "two", "three"]) == ["shared", "other"]
        assert calls == ["one", "two", "three"]
    importlib.reload(label_index)
