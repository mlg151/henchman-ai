"""Utilities for dataclass serialization and deserialization."""

from __future__ import annotations

import types
from dataclasses import asdict, fields
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T", bound="SerializableDataclass")


class AsDictMixin:
    """Mixin providing to_dict via dataclasses.asdict."""

    def to_dict(self: Any) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return asdict(self)


class SerializableDataclass(AsDictMixin):
    """Mixin to provide to_dict and from_dict for dataclasses."""

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize entry from a dictionary with support for nested dataclasses.

        Args:
            data: Dictionary containing serialized data for the dataclass.

        Returns:
            An instance of the dataclass populated with data from the dictionary.

        Note:
            Supports nested dataclasses that also implement `from_dict`.
        """
        type_hints = get_type_hints(cls)
        kwargs = {}
        for f in fields(cls):
            if f.name not in data:
                continue

            val = data[f.name]
            f_type = type_hints.get(f.name)
            kwargs[f.name] = cls._deserialize_val(val, f_type) if val is not None and f_type else val

        return cls(**kwargs)

    @classmethod
    def _deserialize_val(cls: type[SerializableDataclass], val: Any, f_type: Any) -> Any:
        """Helper to deserialize individual fields based on their type hints."""
        origin = get_origin(f_type)
        args = get_args(f_type)

        if origin is list and args:
            item_type = args[0]
            if hasattr(item_type, "from_dict") and isinstance(val, list):
                return [item_type.from_dict(i) for i in val]

        if origin in (Union, types.UnionType):
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                return cls._deserialize_val(val, non_none[0])

        if hasattr(f_type, "from_dict") and isinstance(val, dict):
            return f_type.from_dict(val)

        return val
