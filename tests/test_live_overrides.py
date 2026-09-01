from __future__ import annotations

import json

from aion_indian_market_calendar.live_overrides import (
    apply_holiday_date_change,
    load_live_payload,
    match_known_holiday_names,
)


def test_match_known_holiday_names_detects_bakri_id():
    matches = match_known_holiday_names("NSE trading holiday update for Bakri Id circular")
    assert "Bakri Id" in matches


def test_apply_holiday_date_change_moves_bakri_id_group(tmp_path):
    live_path = tmp_path / "live_events.json"

    result = apply_holiday_date_change(
        holiday_name="Bakri Id",
        new_date="2026-05-29",
        live_path=live_path,
        year=2026,
        circular_url="https://nsearchives.nseindia.com/example-bakri-id.pdf",
        circular_title="Revision in trading holiday for Bakri Id",
        note="Shift due to exchange circular",
    )

    payload = load_live_payload(live_path)
    moved = [
        event
        for event in payload["events"]
        if str((event.get("metadata") or {}).get("holiday_name") or "").lower() == "bakri id"
    ]

    assert result.old_date.isoformat() == "2026-05-28"
    assert result.new_date.isoformat() == "2026-05-29"
    assert result.moved_event_count == 7
    assert len(moved) == 7
    assert all(str(event["start"]).startswith("2026-05-29") for event in moved)
    assert "NSE_EQUITY_HOLIDAY_20260528" in payload["deleted_ids"]
    assert any(event["id"] == "NSE_EQUITY_HOLIDAY_20260529" for event in moved)
    assert all((event.get("metadata") or {}).get("generated_by") == "nse_circular_live_override" for event in moved)
    assert all((event.get("metadata") or {}).get("status") == "confirmed_by_nse_circular" for event in moved)


def test_apply_holiday_date_change_replaces_previous_generated_shift(tmp_path):
    live_path = tmp_path / "live_events.json"

    first = apply_holiday_date_change(
        holiday_name="Bakri Id",
        new_date="2026-05-29",
        live_path=live_path,
        year=2026,
    )
    second = apply_holiday_date_change(
        holiday_name="Bakri Id",
        new_date="2026-05-30",
        live_path=live_path,
        year=2026,
    )

    payload = json.loads(live_path.read_text(encoding="utf-8"))
    moved = [
        event
        for event in payload["events"]
        if str((event.get("metadata") or {}).get("holiday_name") or "").lower() == "bakri id"
    ]

    assert first.moved_event_count == 7
    assert second.moved_event_count == 7
    assert len(moved) == 7
    assert all(str(event["start"]).startswith("2026-05-30") for event in moved)
