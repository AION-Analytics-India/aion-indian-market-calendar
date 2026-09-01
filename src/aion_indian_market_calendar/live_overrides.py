from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .calendar import IndiaMarketCalendar


LIVE_OVERRIDE_GENERATOR = "nse_circular_live_override"


@dataclass(frozen=True)
class HolidayDateShiftResult:
    holiday_name: str
    old_date: date
    new_date: date
    moved_event_count: int
    deleted_ids: tuple[str, ...]
    live_path: Path
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "holiday_name": self.holiday_name,
            "old_date": self.old_date.isoformat(),
            "new_date": self.new_date.isoformat(),
            "moved_event_count": self.moved_event_count,
            "deleted_ids": list(self.deleted_ids),
            "live_path": str(self.live_path),
            "version": self.version,
        }


def load_live_payload(path: str | Path) -> dict[str, Any]:
    live_path = Path(path)
    if not live_path.exists():
        return {
            "version": "bootstrap-000",
            "generated_at": None,
            "events": [],
            "deleted_ids": [],
        }

    payload = json.loads(live_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("live override payload must be a JSON object")
    events = payload.get("events")
    deleted_ids = payload.get("deleted_ids")
    if events is not None and not isinstance(events, list):
        raise ValueError("live override payload events must be a list")
    if deleted_ids is not None and not isinstance(deleted_ids, list):
        raise ValueError("live override payload deleted_ids must be a list")
    return {
        "version": str(payload.get("version") or "bootstrap-000"),
        "generated_at": payload.get("generated_at"),
        "events": list(events or []),
        "deleted_ids": [str(item).strip() for item in (deleted_ids or []) if str(item).strip()],
    }


def save_live_payload(path: str | Path, payload: dict[str, Any]) -> None:
    live_path = Path(path)
    # ── Collision guard (incident 2026-06-26) ───────────────────────────────
    # The live-events delta must NEVER be written to the IMI taxonomy file. On
    # 2026-06-26 an events delta ({version, events, deleted_ids}) landed on
    # taxonomy_india_v2_calibrated.yaml and wiped the sector engine. Fail loudly
    # rather than silently clobber the taxonomy.
    if live_path.name == "taxonomy_india_v2_calibrated.yaml":
        raise ValueError(
            "save_live_payload refused: destination is the IMI taxonomy file "
            f"({live_path}). The live-events delta must go to live_cache.json / the "
            "dedicated overrides path, never the taxonomy (incident 2026-06-26)."
        )
    live_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def known_holiday_names(*, year: int = 2026) -> list[str]:
    calendar = IndiaMarketCalendar.bundled(year)
    names = {
        str((event.metadata or {}).get("holiday_name") or "").strip()
        for event in calendar.all_events()
    }
    return sorted(name for name in names if name)


def match_known_holiday_names(text: str, *, year: int = 2026) -> list[str]:
    haystack = str(text or "").strip().lower()
    if not haystack:
        return []
    return [name for name in known_holiday_names(year=year) if name.lower() in haystack]


def _holiday_matches(event, holiday_name: str) -> bool:
    needle = holiday_name.strip().lower()
    if not needle:
        return False
    metadata_name = str((event.metadata or {}).get("holiday_name") or "").strip().lower()
    if metadata_name == needle:
        return True
    return needle in event.name.lower()


def _shift_datetime(value: datetime | None, *, old_day: date, new_day: date) -> datetime | None:
    if value is None:
        return None
    day_offset = value.date() - old_day
    target_day = new_day + timedelta(days=day_offset.days)
    return datetime.combine(target_day, value.timetz())


def _rewrite_event_id(event_id: str, *, old_day: date, new_day: date) -> str:
    old_stamp = old_day.strftime("%Y%m%d")
    new_stamp = new_day.strftime("%Y%m%d")
    if old_stamp in event_id:
        return event_id.replace(old_stamp, new_stamp, 1)
    return f"{event_id}_{new_stamp}"


def _normalize_new_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def apply_holiday_date_change(
    *,
    holiday_name: str,
    new_date: date | str,
    live_path: str | Path,
    year: int = 2026,
    circular_url: str | None = None,
    circular_title: str | None = None,
    note: str | None = None,
    save: bool = True,
) -> HolidayDateShiftResult:
    calendar = IndiaMarketCalendar.bundled(year)
    base_events = [event for event in calendar.events if _holiday_matches(event, holiday_name)]
    if not base_events:
        raise ValueError(f"No bundled events found for holiday_name={holiday_name!r} in {year}")

    new_day = _normalize_new_date(new_date)
    old_day = base_events[0].start.date()
    if any(event.start.date() != old_day for event in base_events):
        raise ValueError(f"Bundled holiday {holiday_name!r} spans multiple base dates; manual review required")

    payload = load_live_payload(live_path)
    base_ids = {event.id for event in base_events}
    deleted_ids = {item for item in payload.get("deleted_ids", []) if item}
    deleted_ids.update(base_ids)

    retained_events: list[dict[str, Any]] = []
    for record in payload.get("events", []):
        metadata = dict(record.get("metadata") or {})
        supersedes_id = str(metadata.get("supersedes_id") or "").strip()
        existing_holiday_name = str(metadata.get("holiday_name") or "").strip().lower()
        generated_by = str(metadata.get("generated_by") or "").strip()
        if supersedes_id in base_ids:
            continue
        if generated_by == LIVE_OVERRIDE_GENERATOR and existing_holiday_name == holiday_name.strip().lower():
            continue
        retained_events.append(record)

    override_events: list[dict[str, Any]] = []
    for event in base_events:
        shifted = event.to_dict()
        shifted["id"] = _rewrite_event_id(event.id, old_day=old_day, new_day=new_day)
        shifted["start"] = _shift_datetime(event.start, old_day=old_day, new_day=new_day).isoformat()
        shifted_end = _shift_datetime(event.end, old_day=old_day, new_day=new_day)
        shifted["end"] = shifted_end.isoformat() if shifted_end else None

        metadata = dict(shifted.get("metadata") or {})
        metadata["holiday_name"] = str(metadata.get("holiday_name") or holiday_name).strip()
        metadata["supersedes_id"] = event.id
        metadata["generated_by"] = LIVE_OVERRIDE_GENERATOR
        metadata["status"] = "confirmed_by_nse_circular"
        if circular_url:
            metadata["nse_circular_url"] = circular_url
        if circular_title:
            metadata["nse_circular_title"] = circular_title
        if note:
            metadata["override_note"] = note
        shifted["metadata"] = metadata
        override_events.append(shifted)

    merged_by_id = {record["id"]: record for record in retained_events}
    for record in override_events:
        merged_by_id[record["id"]] = record

    generated_at = datetime.now(calendar.tz).isoformat()
    version = datetime.now(calendar.tz).strftime("%Y%m%d-%H%M%S")
    next_payload = {
        "version": version,
        "generated_at": generated_at,
        "events": sorted(
            merged_by_id.values(),
            key=lambda record: (str(record.get("start") or ""), str(record.get("id") or "")),
        ),
        "deleted_ids": sorted(deleted_ids),
    }

    if save:
        save_live_payload(live_path, next_payload)

    return HolidayDateShiftResult(
        holiday_name=holiday_name,
        old_date=old_day,
        new_date=new_day,
        moved_event_count=len(override_events),
        deleted_ids=tuple(sorted(base_ids)),
        live_path=Path(live_path),
        version=version,
    )
