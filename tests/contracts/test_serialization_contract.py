"""Contract tests for the SerializableDataclass base and WorkingMemory entries.

These tests validate that SerializableDataclass subclasses can round-trip
via to_dict() and that optional fields are handled correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from henchman.agents.working_memory import WorkingMemoryEntry
from henchman.utils.serialization import SerializableDataclass


@dataclass
class _TestData(SerializableDataclass):
    """Minimal SerializableDataclass for base contract testing."""

    name: str
    count: int = 0
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class _NestedData(SerializableDataclass):
    """SerializableDataclass with a nested field."""

    title: str
    child: _TestData | None = None


class TestSerializableDataclassContract:
    """SerializableDataclass subclasses must satisfy the serialization contract."""

    def test_to_dict_basic_fields(self) -> None:
        """Simple fields should serialize correctly."""
        data = _TestData(name="test", count=42)
        result = data.to_dict()
        assert result["name"] == "test"
        assert result["count"] == 42

    def test_to_dict_with_list_field(self) -> None:
        """List fields should serialize correctly."""
        data = _TestData(name="test", tags=["a", "b", "c"])
        result = data.to_dict()
        assert result["tags"] == ["a", "b", "c"]

    def test_to_dict_with_none_optional(self) -> None:
        """Optional fields with None values should be included as None."""
        data = _TestData(name="test", tags=None, metadata=None)
        result = data.to_dict()
        assert result["tags"] is None
        assert result["metadata"] is None

    def test_to_dict_with_dict_field(self) -> None:
        """Dict fields should serialize correctly."""
        data = _TestData(name="test", metadata={"key": "value", "num": 42})
        result = data.to_dict()
        assert result["metadata"] == {"key": "value", "num": 42}

    def test_roundtrip_simple(self) -> None:
        """Simple data should round-trip via to_dict/from_dict."""
        original = _TestData(name="roundtrip", count=100, tags=["x", "y"])
        data = original.to_dict()
        restored = _TestData.from_dict(data)
        assert restored.name == original.name
        assert restored.count == original.count
        assert restored.tags == original.tags

    def test_roundtrip_with_none_fields(self) -> None:
        """Data with None fields should round-trip correctly."""
        original = _TestData(name="nullable", count=0, tags=None, metadata=None)
        data = original.to_dict()
        restored = _TestData.from_dict(data)
        assert restored.name == "nullable"
        assert restored.count == 0
        assert restored.tags is None

    def test_roundtrip_nested_dataclass(self) -> None:
        """Nested dataclasses should round-trip correctly."""
        child = _TestData(name="child", count=7, tags=["nested"])
        parent = _NestedData(title="parent", child=child)
        data = parent.to_dict()
        restored = _NestedData.from_dict(data)
        assert restored.title == "parent"
        assert restored.child is not None
        assert restored.child.name == "child"
        assert restored.child.count == 7
        assert restored.child.tags == ["nested"]

    def test_from_dict_ignores_unknown_keys(self) -> None:
        """Unknown keys in the dict should be ignored."""
        data = _TestData.from_dict({
            "name": "test",
            "count": 10,
            "unknown_key": "should be ignored",
        })
        assert data.name == "test"
        assert data.count == 10

    def test_from_dict_missing_optional_field(self) -> None:
        """Missing optional fields should use defaults."""
        data = _TestData.from_dict({"name": "test"})
        assert data.name == "test"
        assert data.count == 0  # default
        assert data.tags is None  # default

    def test_field_order_preserved(self) -> None:
        """Field ordering in to_dict should be preserved."""
        data = _TestData(name="order", count=1, tags=["a"], metadata={"k": "v"})
        result = data.to_dict()
        keys = list(result.keys())
        # name should come before count, count before tags, tags before metadata
        assert keys.index("name") < keys.index("count")
        assert keys.index("count") < keys.index("tags")
        assert keys.index("tags") < keys.index("metadata")


class TestWorkingMemoryEntryContract:
    """WorkingMemoryEntry must satisfy the serialization contract."""

    def test_working_memory_entry_defaults(self) -> None:
        """WorkingMemoryEntry with default optional fields should work."""
        entry = WorkingMemoryEntry(path="/src/main.py", purpose="review")
        data = entry.to_dict()
        assert data["path"] == "/src/main.py"
        assert data["purpose"] == "review"
        # optional fields should have their defaults
        assert data["lines_read"] == "full"
        assert "key_insights" in data
        assert "timestamp" in data

    def test_working_memory_entry_full(self) -> None:
        """WorkingMemoryEntry with all fields set should round-trip."""
        entry = WorkingMemoryEntry(
            path="/src/main.py",
            purpose="review",
            lines_read="143-158",
            key_insights=["needs refactoring"],
        )
        data = entry.to_dict()
        restored = WorkingMemoryEntry.from_dict(data)
        assert restored.path == "/src/main.py"
        assert restored.purpose == "review"
        assert restored.lines_read == "143-158"
        assert restored.key_insights == ["needs refactoring"]
