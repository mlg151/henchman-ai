"""Schema migration helpers for Tier 8 services."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from henchman.ops.state import AppStateStore
from henchman.ops.store import OpsStore


@dataclass(frozen=True, slots=True)
class Migration:
    """A single ordered migration step."""

    version: int
    name: str
    apply: Callable[[AppStateStore], None]


class MigrationRunner:
    """Apply ordered migrations and persist schema versions."""

    def __init__(
        self,
        *,
        store: OpsStore,
        namespace: str,
        migrations: Sequence[Migration],
    ) -> None:
        """Initialize the migration runner.

        Args:
            store: Shared operations store.
            namespace: Schema namespace to version.
            migrations: Ordered migration definitions.
        """
        self._store = store
        self._namespace = namespace
        self._migrations = sorted(migrations, key=lambda migration: migration.version)

    def current_version(self) -> int:
        """Return the currently applied schema version."""
        return self._store.get_schema_version(self._namespace)

    def migrate(self, state_store: AppStateStore) -> list[str]:
        """Apply pending migrations.

        Args:
            state_store: App-state access for migration hooks.

        Returns:
            List of migration names that were applied.
        """
        current_version = self.current_version()
        applied: list[str] = []
        for migration in self._migrations:
            if migration.version <= current_version:
                continue
            migration.apply(state_store)
            self._store.set_schema_version(self._namespace, migration.version)
            current_version = migration.version
            applied.append(migration.name)
        return applied
