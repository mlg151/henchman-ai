"""Generic registry implementation for Henchman-AI.

Provides a common base class for tracking named objects (commands, tools,
providers, extensions, etc.) to eliminate code duplication across registries.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def _set_dict_item(dictionary: dict[str, Any], key: str, value: Any) -> None:
    """Set an item in a dictionary.

    This is a simple utility function to eliminate the duplicate pattern
    of `dictionary[key] = value` across the codebase.

    Args:
        dictionary: The dictionary to update.
        key: The key to set.
        value: The value to set.
    """
    dictionary[key] = value


class Registry(Generic[T]):
    """Generic base class for registries of named items."""

    def __init__(self: Registry[T], prevent_duplicates: bool = False) -> None:
        """Initialize a registry.

        Args:
            prevent_duplicates: If True, raise ValueError when registering
                duplicate items. Defaults to False.
        """
        self._items: dict[str, T] = {}
        self._prevent_duplicates = prevent_duplicates

    def register(self: Registry[T], name: str, item: T) -> None:
        """Register an item by name.

        Args:
            name: Unique name for the item.
            item: The item to register.

        Returns:
            None

        Raises:
            ValueError: If prevent_duplicates is True and item already exists.
        """
        if self._prevent_duplicates and name in self._items:
            raise ValueError(f"Item '{name}' is already registered")
        _set_dict_item(self._items, name, item)

    def get(self: Registry[T], name: str) -> T | None:
        """Get an item by name.

        Args:
            name: Unique name of the item.

        Returns:
            The item if found, otherwise None.
        """
        return self._items.get(name)

    def list_items(self: Registry[T]) -> list[T]:
        """List all registered items.

        Returns:
            A list of all registered item objects.
        """
        return list(self._items.values())

    def list_names(self: Registry[T]) -> list[str]:
        """List all registered item names.

        Returns:
            A list of all registered names.
        """
        return list(self._items.keys())

    def get_sorted_items(
        self: Registry[T],
        key: Callable[[T], Any] | None = None,
        reverse: bool = False,
    ) -> list[T]:
        """Get all registered items sorted by a key function.

        Args:
            key: Function to extract a comparison key from each item.
                If None, items are sorted by their name (registry key).
            reverse: If True, sort in descending order.

        Returns:
            A sorted list of registered items.
        """
        items = self.list_items()
        key_fn: Callable[[T], Any]
        if key is None:
            # Sort by name (registry key) by default
            # Create a mapping from item to name for efficient lookup
            item_to_name = {v: k for k, v in self._items.items()}

            def name_key(item: T) -> Any:
                return item_to_name[item]

            key_fn = name_key
        else:
            key_fn = key

        return sorted(items, key=key_fn, reverse=reverse)
