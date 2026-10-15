"""Project-local cron schedule persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from henchman.config.paths import resolve_project_settings_path

_FIELD_RANGES = (
    (0, 59),
    (0, 23),
    (1, 31),
    (1, 12),
    (0, 6),
)
_SEARCH_WINDOW_MINUTES = 366 * 24 * 60


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON payload or return *default* when absent."""

    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: object) -> None:
    """Persist one JSON payload with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _normalize_argv(value: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Normalize an argv-like value into a tuple of strings."""

    if value is None:
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _expand_part(part: str, minimum: int, maximum: int) -> set[int]:
    """Expand one cron field token into the matching numeric values."""

    if part == "*":
        return set(range(minimum, maximum + 1))

    if "/" in part:
        base, step_text = part.split("/", 1)
        step = int(step_text)
        if step <= 0:
            msg = "Cron step must be positive."
            raise ValueError(msg)
        seed = _expand_part(base or "*", minimum, maximum)
        return {value for value in sorted(seed) if (value - minimum) % step == 0}

    if "-" in part:
        start_text, end_text = part.split("-", 1)
        start = int(start_text)
        end = int(end_text)
        if start > end:
            msg = "Cron range start must be <= end."
            raise ValueError(msg)
        return set(range(start, end + 1))

    value = int(part)
    if minimum == 0 and maximum == 6 and value == 7:
        value = 0
    if value < minimum or value > maximum:
        msg = f"Cron value {value} is outside {minimum}-{maximum}."
        raise ValueError(msg)
    return {value}


def _parse_field(field: str, minimum: int, maximum: int) -> set[int]:
    """Parse one cron field into a set of matching values."""

    values: set[int] = set()
    for part in field.split(","):
        cleaned = part.strip()
        if not cleaned:
            continue
        values.update(_expand_part(cleaned, minimum, maximum))
    if not values:
        msg = "Cron fields must not be empty."
        raise ValueError(msg)
    return values


def _parse_cron(cron: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Parse a 5-field cron expression."""

    fields = cron.split()
    if len(fields) != 5:
        msg = "Cron expressions must have exactly 5 fields."
        raise ValueError(msg)
    parsed_fields = [
        _parse_field(field, minimum, maximum)
        for field, (minimum, maximum) in zip(fields, _FIELD_RANGES, strict=True)
    ]
    return (
        parsed_fields[0],
        parsed_fields[1],
        parsed_fields[2],
        parsed_fields[3],
        parsed_fields[4],
    )


@dataclass(frozen=True, slots=True)
class CronScheduleRecord:
    """Persisted cron schedule metadata."""

    schedule_id: str
    title: str
    cron: str
    argv: tuple[str, ...]
    enabled: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "schedule_id": self.schedule_id,
            "title": self.title,
            "cron": self.cron,
            "argv": list(self.argv),
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CronScheduleRecord:
        """Create a schedule record from persisted data."""

        raw_argv = payload.get("argv")
        return cls(
            schedule_id=str(payload.get("schedule_id", "")),
            title=str(payload.get("title", "")),
            cron=str(payload.get("cron", "")),
            argv=_normalize_argv(raw_argv if isinstance(raw_argv, list | tuple) else None),
            enabled=bool(payload.get("enabled", False)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
        )


class CronScheduleService:
    """Manage project-local cron schedules."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the cron schedule service for one project root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._storage_dir = resolve_project_settings_path(self._project_root) / "schedules"
        self._index_path = self._storage_dir / "index.json"

    def create_schedule(
        self,
        *,
        title: str,
        cron: str,
        argv: list[str] | tuple[str, ...],
    ) -> CronScheduleRecord:
        """Create one persisted cron schedule."""

        normalized_argv = _normalize_argv(argv)
        if not title.strip():
            msg = "A schedule title is required."
            raise ValueError(msg)
        if not normalized_argv:
            msg = "A non-empty argv list is required."
            raise ValueError(msg)
        self.next_run_for(cron, after=datetime.now(UTC))
        now = _now_iso()
        record = CronScheduleRecord(
            schedule_id=f"schedule-{uuid4().hex[:12]}",
            title=title.strip(),
            cron=cron.strip(),
            argv=normalized_argv,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        records = self._load_records()
        records[record.schedule_id] = record
        self._persist_records(records)
        return record

    def list_schedules(self) -> list[CronScheduleRecord]:
        """Return all persisted schedules."""

        return sorted(self._load_records().values(), key=lambda record: record.created_at)

    def get_schedule(self, schedule_id: str) -> CronScheduleRecord | None:
        """Return one schedule when present."""

        return self._load_records().get(schedule_id)

    def pause(self, schedule_id: str) -> CronScheduleRecord:
        """Disable one persisted schedule."""

        return self._set_enabled(schedule_id, enabled=False)

    def resume(self, schedule_id: str) -> CronScheduleRecord:
        """Enable one persisted schedule."""

        return self._set_enabled(schedule_id, enabled=True)

    def delete(self, schedule_id: str) -> bool:
        """Delete one persisted schedule."""

        records = self._load_records()
        if schedule_id not in records:
            return False
        del records[schedule_id]
        self._persist_records(records)
        return True

    def next_run_for(self, cron: str, *, after: datetime) -> datetime:
        """Return the next run time for one cron expression."""

        minutes, hours, days, months, weekdays = _parse_cron(cron)
        candidate = after.astimezone(UTC).replace(second=0, microsecond=0)
        candidate += timedelta(minutes=1)
        for _ in range(_SEARCH_WINDOW_MINUTES):
            if (
                candidate.minute in minutes
                and candidate.hour in hours
                and candidate.day in days
                and candidate.month in months
                and candidate.weekday() in weekdays
            ):
                return candidate
            candidate += timedelta(minutes=1)
        msg = "Unable to find the next run time within the search window."
        raise ValueError(msg)

    def _set_enabled(self, schedule_id: str, *, enabled: bool) -> CronScheduleRecord:
        """Update one schedule's enabled state."""

        records = self._load_records()
        record = records.get(schedule_id)
        if record is None:
            msg = f"Schedule {schedule_id} not found."
            raise KeyError(msg)
        updated = CronScheduleRecord(
            schedule_id=record.schedule_id,
            title=record.title,
            cron=record.cron,
            argv=record.argv,
            enabled=enabled,
            created_at=record.created_at,
            updated_at=_now_iso(),
        )
        records[schedule_id] = updated
        self._persist_records(records)
        return updated

    def _load_records(self) -> dict[str, CronScheduleRecord]:
        """Load persisted schedules from disk."""

        payload = _read_json(self._index_path, default=[])
        if not isinstance(payload, list):
            return {}
        records: dict[str, CronScheduleRecord] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = CronScheduleRecord.from_dict(item)
            records[record.schedule_id] = record
        return records

    def _persist_records(self, records: dict[str, CronScheduleRecord]) -> None:
        """Persist schedules to project-local storage."""

        payload = [
            record.to_dict()
            for record in sorted(records.values(), key=lambda item: item.created_at)
        ]
        _write_json(self._index_path, payload)
