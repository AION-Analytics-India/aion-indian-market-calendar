"""No identifier leaves this machine.

Until 1.4.0 a refresh against an AION host sent X-AION-Calendar-Install, a UUID4
persisted to ~/.aion_indian_market/telemetry.json and reused for the life of the
machine, alongside the package version, the Python version and the operating
system. That is a persistent pseudonymous identifier and it contradicted the
published privacy position.

These tests exist so it cannot come back by accident. See
docs/TELEMETRY_AUDIT.md.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from aion_indian_market_calendar.calendar import IndiaMarketCalendar

SRC = Path(__file__).resolve().parents[1] / "src"


def _calendar(**kwargs):
    return IndiaMarketCalendar(refresh_url="https://api.aiondashboard.site/v1/calendar/live",
                               **kwargs)


def test_refresh_headers_carry_only_a_user_agent():
    headers = _calendar()._refresh_headers()
    assert set(headers) == {"User-Agent"}
    assert headers["User-Agent"].startswith("aion-indian-market-calendar/")


def test_no_x_aion_header_is_ever_sent():
    """The specific headers that used to carry the install identifier."""
    headers = _calendar()._refresh_headers()
    for name in headers:
        assert not name.lower().startswith("x-aion"), name


@pytest.mark.parametrize("telemetry", [True, False, None])
def test_the_telemetry_argument_cannot_turn_anything_back_on(telemetry):
    """Kept as an accepted keyword so 1.3.x code does not break, including
    anyone who passed telemetry=False. It controls nothing."""
    headers = _calendar(telemetry=telemetry)._refresh_headers()
    assert set(headers) == {"User-Agent"}


def test_no_install_identifier_file_is_written(tmp_path, monkeypatch):
    """The old code wrote a UUID4 to ~/.aion_indian_market/telemetry.json on
    first refresh and reused it forever."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _calendar()._refresh_headers()
    assert not (tmp_path / ".aion_indian_market" / "telemetry.json").exists()


def test_the_telemetry_helpers_are_gone_from_the_source():
    """Deleted, not defaulted off. A code path that can send an identifier is a
    liability in a published wheel even when it never fires."""
    source = (SRC / "aion_indian_market_calendar" / "calendar.py").read_text(encoding="utf-8")
    for gone in ("_anonymous_install_id", "_telemetry_enabled",
                 "_refresh_host_is_aion_owned", "AION_TELEMETRY_HOSTS",
                 "X-AION-Calendar-Install"):
        assert f"def {gone}" not in source and f"\n{gone}" not in source, gone


def test_no_module_builds_a_telemetry_header_as_a_string_literal():
    """Catches a reintroduction anywhere in the package, not just calendar.py.

    Parses rather than greps: the header names appear in docstrings here and in
    the audit, deliberately, and a plain text search cannot tell an explanation
    from an implementation.
    """
    import ast

    banned = re.compile(r"^X-AION-Calendar-")
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings):
                assert not banned.match(node.value), f"{path.name}: {node.value!r}"
