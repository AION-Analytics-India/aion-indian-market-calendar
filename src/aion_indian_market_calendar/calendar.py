from __future__ import annotations

import json
import logging
import os
import platform
import pkgutil
import re
import uuid
import hashlib
from datetime import date, datetime, time, timedelta, tzinfo
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .models import (
    SESSION_KIND_CLOSING_AUCTION,
    SESSION_KIND_CONTINUOUS,
    MarketEvent,
    SessionRule,
    SessionSegment,
)

logger = logging.getLogger(__name__)

# ── Taxonomy write guard (incident 2026-06-26) ──────────────────────────────
_TAXONOMY_REQUIRED_KEYS = ("metadata", "config", "sectors", "categories")
_TAXONOMY_MIN_BYTES = 10 * 1024  # a real taxonomy is ~117 KB


def _assert_payload_is_taxonomy(name: str, payload: bytes) -> None:
    """Fail loudly if *payload* is not structurally the taxonomy file.

    On 2026-06-26 a hash-less refresh wrote a 105-byte live-events delta
    ({version, events, deleted_ids}) over taxonomy_india_v2_calibrated.yaml,
    wiping the IMI sector engine. Validated without a YAML dependency: a size
    floor plus the four required top-level keys must appear as top-level mappings.
    """
    if len(payload) < _TAXONOMY_MIN_BYTES:
        raise ValueError(
            f"Refusing to write {name}: payload only {len(payload)} bytes "
            f"(< {_TAXONOMY_MIN_BYTES}); a real taxonomy is ~117 KB — looks like a "
            "live-events delta or error page, not a taxonomy (incident 2026-06-26)."
        )
    text = payload.decode("utf-8", errors="replace")
    missing = [k for k in _TAXONOMY_REQUIRED_KEYS if not re.search(rf"(?m)^{k}\s*:", text)]
    if missing:
        raise ValueError(
            f"Refusing to write {name}: payload missing required taxonomy top-level "
            f"keys {missing}. Refusing to clobber the taxonomy with non-taxonomy "
            "content (incident 2026-06-26)."
        )

PACKAGE_NAME = "aion-indian-market-calendar"
AION_TELEMETRY_HOSTS: frozenset[str] = frozenset(
    {
        "aiondashboard.site",
        "dashboard.aiondashboard.site",
        "api.aiondashboard.site",
    }
)
TELEMETRY_OPT_OUT_VALUES: frozenset[str] = frozenset({"0", "false", "no", "off", "disabled"})


def _package_version() -> str:
    try:
        return importlib_metadata.version(PACKAGE_NAME)
    except Exception:
        return "0+unknown"


DEFAULT_SESSIONS: dict[str, list[SessionSegment]] = {
    "NSE": [SessionSegment(market="NSE", open=time(9, 0), close=time(15, 30))],
    "NSE_EQUITY": [SessionSegment(market="NSE_EQUITY", open=time(9, 0), close=time(15, 30))],
    "NSE_EQUITY_FNO_UNDERLYING": [SessionSegment(market="NSE_EQUITY_FNO_UNDERLYING", open=time(9, 0), close=time(15, 30))],
    "NSE_EQUITY_DERIVATIVES": [SessionSegment(market="NSE_EQUITY_DERIVATIVES", open=time(9, 15), close=time(15, 30))],
    "BSE_EQUITY": [SessionSegment(market="BSE_EQUITY", open=time(9, 15), close=time(15, 30))],
    "BSE_EQUITY_FNO_UNDERLYING": [SessionSegment(market="BSE_EQUITY_FNO_UNDERLYING", open=time(9, 15), close=time(15, 30))],
    "BSE_EQUITY_DERIVATIVES": [SessionSegment(market="BSE_EQUITY_DERIVATIVES", open=time(9, 15), close=time(15, 30))],
    "NSE_CURRENCY_DERIVATIVES": [SessionSegment(market="NSE_CURRENCY_DERIVATIVES", open=time(9, 0), close=time(17, 0))],
    "NSE_COMMODITY_DERIVATIVES": [SessionSegment(market="NSE_COMMODITY_DERIVATIVES", open=time(9, 0), close=time(23, 30))],
    "MCX": [
        SessionSegment(market="MCX", open=time(8, 45), close=time(8, 59)),
        SessionSegment(market="MCX", open=time(9, 0), close=time(23, 30)),
    ],
    "NSE_INTEREST_RATE_DERIVATIVES": [SessionSegment(market="NSE_INTEREST_RATE_DERIVATIVES", open=time(9, 0), close=time(17, 0))],
    "NSE_CORPORATE_BONDS": [SessionSegment(market="NSE_CORPORATE_BONDS", open=time(9, 0), close=time(17, 15))],
}

def _canonical_markets() -> frozenset[str]:
    """Every canonical segment name, however it was declared.

    Deriving this from DEFAULT_SESSIONS alone silently broke any segment that
    had aliases but no built-in session: NSE_CURRENCY_DERIVATIVES was declared
    in SEGMENT_ALIASES and carried its own bundled sessions and holidays, yet
    resolving it raised "Unknown market input", so holidays("CDS") and
    is_market_open("USDINR") both failed. Union the two sources so a segment
    declared either way resolves.
    """
    return frozenset(DEFAULT_SESSIONS) | frozenset(SEGMENT_ALIASES)

# ── Closing Auction Session (CAS) ───────────────────────────────────────────
# SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 dated January 16, 2026,
# "Introduction of Closing Auction Session (CAS) in the Equity Cash Segment and
# certain modifications in the Pre-Open Auction Session". Applies to all
# recognised Stock Exchanges, so both NSE and BSE.
#
# Para 4.1.1 — CAS is phased. Initially it determines the closing price only for
#              cash-segment stocks "on which derivative contracts are available".
#              Para 4.1.2 — every other security keeps the 30-minute CTS VWAP.
# Para 4.2.1 — CAS is a separate session of 20 minutes, 15:15 to 15:35:
#                15:15 +5m  reference price calculation / transition CTS -> CAS
#                15:20 +5m  order entry, limit and market orders
#                15:25 +5m  order entry, limit orders only, random close in last 2 min
#                15:30 +5m  order matching
# Para 4.2.2 — order entry closes randomly between 15:28 and 15:30.
# Para 4.2.3 — the equity derivatives segment operates up to 15:40.
# Para 4.2.4 — the cash post-close session operates 15:50 to 16:00.
# Para 6.1   — CAS applies from August 03, 2026.
CLOSING_AUCTION_EFFECTIVE_FROM = date(2026, 8, 3)
CLOSING_AUCTION_CIRCULAR = (
    "SEBI HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 dated 2026-01-16, para 4.2 (CAS), effective 2026-08-03"
)

# Para 6.2 — the revised Pre-Open Auction Session framework applies from
# September 07, 2026. The pre-open session stays 09:00-09:15 overall, so no
# session segment changes; only the internal phases move (see market_timings).
PRE_OPEN_REVISION_EFFECTIVE_FROM = date(2026, 9, 7)

# CAS phase boundaries. Para 4.2.5 defines these as offsets rather than fixed
# clock times, so a special trading session shifts the whole tail intact:
# derivatives close 10 minutes after the CAS order entry period ends, and the
# post-close session begins 10 minutes after the derivatives segment closes.
CAS_START = time(15, 15)
CAS_ORDER_ENTRY_END = time(15, 30)
CAS_END = time(15, 35)
EQUITY_DERIVATIVES_CLOSE = time(15, 40)
POST_CLOSE_START = time(15, 50)
POST_CLOSE_END = time(16, 0)


def _cas_cash_rule(market: str, *, open_time: time) -> SessionRule:
    """Cash-segment rule for a market whose F&O underlyings move to CAS."""
    return SessionRule(
        market=market,
        segments=(
            SessionSegment(market=market, open=open_time, close=CAS_START),
            SessionSegment(market=market, open=CAS_START, close=CAS_END, kind=SESSION_KIND_CLOSING_AUCTION),
        ),
        effective_from=CLOSING_AUCTION_EFFECTIVE_FROM,
        reason=(
            "Continuous trading in stocks with derivative contracts ends 15:15; "
            "the Closing Auction Session runs 15:15-15:35 (SEBI para 4.2.1)."
        ),
        source=CLOSING_AUCTION_CIRCULAR,
    )


def _cas_derivatives_rule(market: str) -> SessionRule:
    return SessionRule(
        market=market,
        segments=(SessionSegment(market=market, open=time(9, 15), close=EQUITY_DERIVATIVES_CLOSE),),
        effective_from=CLOSING_AUCTION_EFFECTIVE_FROM,
        reason="The equity derivatives segment operates up to 15:40 (SEBI para 4.2.3).",
        source=CLOSING_AUCTION_CIRCULAR,
    )


DEFAULT_SESSION_RULES: dict[str, list[SessionRule]] = {
    "NSE_EQUITY_FNO_UNDERLYING": [_cas_cash_rule("NSE_EQUITY_FNO_UNDERLYING", open_time=time(9, 0))],
    "NSE_EQUITY_DERIVATIVES": [_cas_derivatives_rule("NSE_EQUITY_DERIVATIVES")],
    "BSE_EQUITY_FNO_UNDERLYING": [_cas_cash_rule("BSE_EQUITY_FNO_UNDERLYING", open_time=time(9, 15))],
    "BSE_EQUITY_DERIVATIVES": [_cas_derivatives_rule("BSE_EQUITY_DERIVATIVES")],
}

SEGMENT_ALIASES: dict[str, set[str]] = {
    "NSE_EQUITY": {"NSE", "EQUITIES", "NSE_CASH"},
    "NSE_EQUITY_FNO_UNDERLYING": {"NSE_EQUITY_FNO", "NSE_CASH_FNO", "FNO_UNDERLYING", "EQUITY_FNO_UNDERLYING"},
    "NSE_EQUITY_DERIVATIVES": {"NFO", "FNO", "NSE_FNO", "EQUITY_DERIVATIVES"},
    "NSE_CURRENCY_DERIVATIVES": {"CURRENCY_DERIVATIVES", "CDS"},
    "NSE_COMMODITY_DERIVATIVES": {"COMMODITY_DERIVATIVES", "NSE_COMMODITIES"},
    "NSE_INTEREST_RATE_DERIVATIVES": {"INTEREST_RATE_DERIVATIVES", "IRD"},
    "NSE_CORPORATE_BONDS": {"CORPORATE_BONDS", "CBRICS"},
    # "BSE" stays an alias for the cash segment so existing callers and the
    # bundled BSE holiday records keep resolving after the segment split.
    "BSE_EQUITY": {"BSE", "BSE_CASH", "BSE_EQUITIES"},
    "BSE_EQUITY_FNO_UNDERLYING": {"BSE_CASH_FNO", "BSE_FNO_UNDERLYING", "BSE_EQUITY_FNO_UNDERLYINGS"},
    "BSE_EQUITY_DERIVATIVES": {"BFO", "BSE_FNO", "BSE_DERIVATIVES"},
    "MCX": {"MCX-COMMODITIES"},
}

INSTRUMENT_TO_SEGMENT: dict[str, dict[str, object]] = {
    "NIFTY": {"primary": "NSE_EQUITY_DERIVATIVES", "alternates": ["NSE_EQUITY"]},
    "BANKNIFTY": {"primary": "NSE_EQUITY_DERIVATIVES"},
    "FINNIFTY": {"primary": "NSE_EQUITY_DERIVATIVES"},
    "MIDCPNIFTY": {"primary": "NSE_EQUITY_DERIVATIVES"},
    "NIFTYNXT50": {"primary": "NSE_EQUITY"},
    # Index instruments resolve to their derivatives segment, matching NIFTY /
    # BANKNIFTY. Index derivatives have no auction and run to 15:40 (para 4.2.3).
    "SENSEX": {"primary": "BSE_EQUITY_DERIVATIVES", "alternates": ["BSE_EQUITY"]},
    "BANKEX": {"primary": "BSE_EQUITY_DERIVATIVES"},
    "USDINR": {"primary": "NSE_CURRENCY_DERIVATIVES"},
    "EURINR": {"primary": "NSE_CURRENCY_DERIVATIVES"},
    "GBPINR": {"primary": "NSE_CURRENCY_DERIVATIVES"},
    "JPYINR": {"primary": "NSE_CURRENCY_DERIVATIVES"},
    "CRUDEOIL": {"primary": "MCX"},
    "NATURALGAS": {"primary": "MCX"},
    "GOLD": {"primary": "MCX"},
    "SILVER": {"primary": "MCX"},
    "COPPER": {"primary": "MCX"},
    "ALUMINIUM": {"primary": "MCX"},
    "ZINC": {"primary": "MCX"},
    "LEAD": {"primary": "MCX"},
    "NICKEL": {"primary": "MCX"},
}

CANONICAL_MARKETS: frozenset[str] = _canonical_markets()

ALIAS_TO_SEGMENT: dict[str, str] = {
    alias: segment
    for segment, aliases in SEGMENT_ALIASES.items()
    for alias in aliases
}

# Segments that are a strict subset of a broader segment. F&O underlying stocks
# are cash-segment equities, so every holiday, special session and circular
# aimed at NSE_EQUITY applies to them too — only their session timings differ.
# Inheritance is one-way: an event aimed at the subset does NOT widen to the parent.
SEGMENT_INHERITS_FROM: dict[str, str] = {
    "NSE_EQUITY_FNO_UNDERLYING": "NSE_EQUITY",
    # The bundled BSE records are tagged "BSE", which resolves to BSE_EQUITY, so
    # both new BSE segments inherit their holidays from it.
    "BSE_EQUITY_FNO_UNDERLYING": "BSE_EQUITY",
    "BSE_EQUITY_DERIVATIVES": "BSE_EQUITY",
}


def _parse_coverage_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def resolve_market_key(market: str) -> str:
    """Normalise an instrument, alias, or segment name to a canonical segment.

    Raises ValueError for anything unrecognised.
    """
    market_upper = market.strip().upper()
    instrument = INSTRUMENT_TO_SEGMENT.get(market_upper)
    if instrument is not None:
        resolved = instrument.get("primary")
        if isinstance(resolved, str):
            return resolved
    alias_market = ALIAS_TO_SEGMENT.get(market_upper)
    if alias_market is not None:
        return alias_market
    if market_upper in CANONICAL_MARKETS:
        return market_upper
    raise ValueError(f"Unknown market input: {market}")


def get_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except Exception:
        import pytz

        return pytz.timezone(name)


def get_ist_timezone() -> tzinfo:
    return get_timezone("Asia/Kolkata")


def _attach_timezone(dt: datetime, tz: tzinfo) -> datetime:
    if hasattr(tz, "localize"):
        return tz.localize(dt)  # type: ignore[attr-defined]
    return dt.replace(tzinfo=tz)


def _convert_timezone(dt: datetime, tz: tzinfo) -> datetime:
    converted = dt.astimezone(tz)
    if hasattr(tz, "normalize"):
        return tz.normalize(converted)  # type: ignore[attr-defined]
    return converted


def _coerce_datetime(value: date | datetime | str, tz: tzinfo) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if len(text) == 10:
            dt = datetime.fromisoformat(f"{text}T00:00:00")
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        return _attach_timezone(dt, tz)
    return _convert_timezone(dt, tz)


class IndiaMarketCalendar:
    def __init__(
        self,
        events_json_path: str | None = None,
        *,
        refresh_url: str | None = None,
        refresh_interval_hours: float = 6,
        telemetry: bool | None = None,
        taxonomy_manifesto_url: str | None = None,
        taxonomy_refresh_enabled: bool = True,
        _raw: dict | list | None = None,
    ):
        if _raw is None:
            if events_json_path is None:
                data = pkgutil.get_data(__package__, "data/events_2026.json")
                if data is None:
                    raise FileNotFoundError("Bundled calendar data/events_2026.json not found")
                raw = json.loads(data.decode("utf-8"))
            else:
                raw = json.loads(Path(events_json_path).read_text(encoding="utf-8"))
        else:
            raw = _raw

        payload = self._normalize_payload(raw)
        self.timezone = payload["timezone"]
        self.tz = get_timezone(self.timezone)
        self.default_sessions = self._load_default_sessions(payload.get("market_sessions"))
        self.session_rules = self._load_session_rules(payload.get("session_rules"))
        self.sources = dict(payload.get("sources") or {})
        self.market_timings = dict(payload.get("market_timings") or {})
        coverage = dict(payload.get("range") or {})
        self.coverage_start = _parse_coverage_date(coverage.get("start"))
        self.coverage_end = _parse_coverage_date(coverage.get("end"))
        self._coverage_warned = False
        self.events = tuple(
            sorted(
                (self._normalize_event(event) for event in payload["events"]),
                key=lambda event: (event.start, event.id),
            )
        )
        self.refresh_url = refresh_url
        self.refresh_interval = timedelta(hours=refresh_interval_hours)
        self.telemetry = telemetry
        self.taxonomy_manifesto_url = taxonomy_manifesto_url
        self.taxonomy_refresh_enabled = taxonomy_refresh_enabled
        self._last_refreshed: datetime | None = None
        self._live_events: dict[str, MarketEvent] = {}
        self._live_deleted_ids: set[str] = set()
        self._live_version: str | None = None
        self._live_generated_at: datetime | None = None
        self._live_session_rules: dict[str, Any] | None = None
        self._live_market_sessions: dict[str, Any] | None = None

        if self.refresh_url:
            self._load_cache()
            self.refresh()

    @classmethod
    def from_records(
        cls,
        records: Iterable[dict],
        *,
        timezone: str = "Asia/Kolkata",
        refresh_url: str | None = None,
        refresh_interval_hours: float = 6,
        telemetry: bool | None = None,
        taxonomy_manifesto_url: str | None = None,
        taxonomy_refresh_enabled: bool = True,
    ) -> "IndiaMarketCalendar":
        return cls(
            refresh_url=refresh_url,
            refresh_interval_hours=refresh_interval_hours,
            telemetry=telemetry,
            taxonomy_manifesto_url=taxonomy_manifesto_url,
            taxonomy_refresh_enabled=taxonomy_refresh_enabled,
            _raw={"timezone": timezone, "events": list(records)},
        )

    @classmethod
    def from_json(
        cls,
        path: str | Path,
        *,
        refresh_url: str | None = None,
        refresh_interval_hours: float = 6,
        telemetry: bool | None = None,
        taxonomy_manifesto_url: str | None = None,
        taxonomy_refresh_enabled: bool = True,
    ) -> "IndiaMarketCalendar":
        return cls(
            str(path),
            refresh_url=refresh_url,
            refresh_interval_hours=refresh_interval_hours,
            telemetry=telemetry,
            taxonomy_manifesto_url=taxonomy_manifesto_url,
            taxonomy_refresh_enabled=taxonomy_refresh_enabled,
        )

    @classmethod
    def bundled(
        cls,
        year: int = 2026,
        *,
        refresh_url: str | None = None,
        refresh_interval_hours: float = 6,
        telemetry: bool | None = None,
        taxonomy_manifesto_url: str | None = None,
        taxonomy_refresh_enabled: bool = True,
    ) -> "IndiaMarketCalendar":
        data = pkgutil.get_data(__package__, f"data/events_{year}.json")
        if data is None:
            raise FileNotFoundError(f"Bundled calendar data/events_{year}.json not found")
        return cls(
            refresh_url=refresh_url,
            refresh_interval_hours=refresh_interval_hours,
            telemetry=telemetry,
            taxonomy_manifesto_url=taxonomy_manifesto_url,
            taxonomy_refresh_enabled=taxonomy_refresh_enabled,
            _raw=json.loads(data.decode("utf-8")),
        )

    @staticmethod
    def _normalize_payload(raw: dict | list) -> dict[str, object]:
        if isinstance(raw, list):
            return {
                "timezone": "Asia/Kolkata",
                "events": raw,
                "market_sessions": {},
                "session_rules": {},
                "market_timings": {},
                "sources": {},
                "range": {},
            }
        if isinstance(raw, dict) and isinstance(raw.get("events"), list):
            return {
                "timezone": str(raw.get("timezone") or "Asia/Kolkata"),
                "events": raw["events"],
                "market_sessions": dict(raw.get("market_sessions") or {}),
                "session_rules": dict(raw.get("session_rules") or {}),
                "market_timings": dict(raw.get("market_timings") or {}),
                "sources": dict(raw.get("sources") or {}),
                "range": dict(raw.get("range") or {}),
            }
        raise ValueError("Calendar JSON must be a list of events or an object with an events list")

    @staticmethod
    def _load_default_sessions(payload: Any) -> dict[str, list[SessionSegment]]:
        sessions: dict[str, list[SessionSegment]] = {
            market: list(segments) for market, segments in DEFAULT_SESSIONS.items()
        }
        if not isinstance(payload, dict):
            return sessions

        for market, segments in payload.items():
            if not isinstance(segments, list):
                continue
            parsed = [SessionSegment.from_dict(segment) for segment in segments]
            if parsed:
                sessions[str(market).strip().upper()] = parsed
        return sessions

    @staticmethod
    def _load_session_rules(payload: Any) -> dict[str, list[SessionRule]]:
        """Merge caller-supplied effective-dated session rules over the built-ins.

        A market present in *payload* replaces that market's bundled rule list
        outright, so a data file or a live refresh can correct one segment
        without restating every other one.
        """
        rules: dict[str, list[SessionRule]] = {
            market: list(market_rules) for market, market_rules in DEFAULT_SESSION_RULES.items()
        }
        if not isinstance(payload, dict):
            return rules

        for market, market_rules in payload.items():
            if not isinstance(market_rules, list):
                continue
            # Resolve aliases, so a payload keyed "BSE" or "NFO" lands on the
            # canonical segment that lookups actually read.
            try:
                market_key = resolve_market_key(str(market))
            except ValueError:
                market_key = str(market).strip().upper()
            parsed = [SessionRule.from_dict(rule, market=market_key) for rule in market_rules]
            rules[market_key] = sorted(parsed, key=lambda rule: rule.effective_from)
        return rules

    def _normalize_event(self, payload: dict) -> MarketEvent:
        event = MarketEvent.from_dict(payload)
        start = _coerce_datetime(event.start, self.tz)
        end = _coerce_datetime(event.end, self.tz) if event.end else None
        return MarketEvent(
            id=event.id,
            name=event.name,
            category=event.category,
            impact=event.impact,
            applies_to=list(event.applies_to),
            start=start,
            end=end,
            windows=dict(event.windows) if event.windows else None,
            session_override=list(event.session_override) if event.session_override else None,
            policy=event.policy,
            tags=list(event.tags),
            description=event.description,
            metadata=dict(event.metadata),
        )

    def _now(self) -> datetime:
        return datetime.now(self.tz)

    def _cache_path(self) -> Path:
        base = Path(os.path.expanduser("~")) / ".aion_indian_market"
        base.mkdir(parents=True, exist_ok=True)
        return base / "live_cache.json"

    def _telemetry_path(self) -> Path:
        base = Path(os.path.expanduser("~")) / ".aion_indian_market"
        base.mkdir(parents=True, exist_ok=True)
        return base / "telemetry.json"

    def _taxonomy_cache_dir(self) -> Path:
        base = Path(os.getenv("AION_IMI_TAXONOMY_CACHE_DIR", "")).expanduser() if os.getenv("AION_IMI_TAXONOMY_CACHE_DIR") else Path(os.path.expanduser("~")) / ".aion_indian_market" / "taxonomy"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _taxonomy_manifesto_cache_path(self) -> Path:
        return self._taxonomy_cache_dir() / "taxonomy_manifesto.json"

    def _refresh_host_is_aion_owned(self) -> bool:
        try:
            host = str(urlparse(self.refresh_url or "").hostname or "").strip().lower()
        except Exception:
            return False
        return host in AION_TELEMETRY_HOSTS or host.endswith(".aiondashboard.site")

    def _telemetry_enabled(self) -> bool:
        env_value = str(os.getenv("AION_CALENDAR_TELEMETRY", "")).strip().lower()
        if env_value in TELEMETRY_OPT_OUT_VALUES:
            return False
        if self.telemetry is False:
            return False
        if not self.refresh_url:
            return False
        # Never leak an AION install identifier to arbitrary third-party refresh URLs.
        return self._refresh_host_is_aion_owned()

    def _anonymous_install_id(self) -> str:
        path = self._telemetry_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            install_id = str(payload.get("install_id") or "").strip()
            if install_id:
                return install_id
        except Exception:
            pass

        install_id = uuid.uuid4().hex
        payload = {
            "install_id": install_id,
            "created_at": self._now().isoformat(),
            "scope": "anonymous_live_refresh_usage",
        }
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.debug("Could not persist anonymous calendar install id: %s", exc)
        return install_id

    def _refresh_headers(self) -> dict[str, str]:
        version = _package_version()
        headers = {
            "User-Agent": f"{PACKAGE_NAME}/{version}",
        }
        if self._telemetry_enabled():
            headers.update(
                {
                    "X-AION-Calendar-Telemetry": "live-refresh",
                    "X-AION-Calendar-Install": self._anonymous_install_id(),
                    "X-AION-Calendar-Version": version,
                    "X-AION-Calendar-Python": platform.python_version(),
                    "X-AION-Calendar-System": platform.system(),
                }
            )
        return headers

    def _effective_taxonomy_manifesto_url(self) -> str | None:
        if self.taxonomy_manifesto_url:
            return self.taxonomy_manifesto_url
        if not self.refresh_url:
            return None
        parsed = urlparse(self.refresh_url)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}/taxonomy/taxonomy_manifesto.json"

    @staticmethod
    def _version_key(value: Any) -> tuple[int, ...]:
        parts = re.findall(r"\d+", str(value or ""))
        return tuple(int(part) for part in parts) if parts else (0,)

    def _cached_taxonomy_manifesto(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self._taxonomy_manifesto_cache_path().read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _remote_manifesto_is_newer(self, remote: dict[str, Any], local: dict[str, Any] | None) -> bool:
        if not local:
            return True
        remote_version = self._version_key(remote.get("version"))
        local_version = self._version_key(local.get("version"))
        if remote_version != local_version:
            return remote_version > local_version
        return str(remote.get("signature") or "") != str(local.get("signature") or "")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers=self._refresh_headers())
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object from {url}")
        return payload

    def _fetch_bytes(self, url: str) -> bytes:
        request = Request(url, headers=self._refresh_headers())
        with urlopen(request, timeout=10) as response:
            return response.read()

    @staticmethod
    def _sha256_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _download_taxonomy_manifesto_update(self, manifesto_url: str, manifesto: dict[str, Any]) -> bool:
        files = manifesto.get("files")
        if not isinstance(files, list) or not files:
            taxonomy_name = str(manifesto.get("taxonomy_file") or "taxonomy_india_v2_calibrated.yaml")
            files = [
                {
                    "name": taxonomy_name,
                    "path": manifesto.get("taxonomy_path") or f"/taxonomy/{taxonomy_name}",
                    "sha256": manifesto.get("signature"),
                }
            ]

        cache_dir = self._taxonomy_cache_dir()
        downloaded: list[str] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            name = Path(str(item.get("name") or "")).name
            if not name.endswith((".yaml", ".yml")):
                continue
            expected_hash = str(item.get("sha256") or "").strip()
            path = str(item.get("path") or f"/taxonomy/{name}")
            file_url = urljoin(manifesto_url, path)
            payload = self._fetch_bytes(file_url)
            actual_hash = self._sha256_bytes(payload)
            if expected_hash and actual_hash != expected_hash:
                raise ValueError(f"SHA-256 mismatch for {name}: expected {expected_hash}, got {actual_hash}")
            # ── Content guard (incident 2026-06-26) ──────────────────────────
            # A refresh whose manifest carried NO sha256 once wrote a 105-byte
            # live-events delta over taxonomy_india_v2_calibrated.yaml, wiping the
            # IMI taxonomy. When there is no hash to verify, refuse to write a
            # taxonomy file unless the payload is *structurally a taxonomy*.
            if not expected_hash and name == "taxonomy_india_v2_calibrated.yaml":
                _assert_payload_is_taxonomy(name, payload)
            (cache_dir / name).write_bytes(payload)
            downloaded.append(name)

        taxonomy_file = str(manifesto.get("taxonomy_file") or "taxonomy_india_v2_calibrated.yaml")
        if str(manifesto.get("signature") or ""):
            main_path = cache_dir / Path(taxonomy_file).name
            if main_path.exists() and self._sha256_bytes(main_path.read_bytes()) != str(manifesto["signature"]):
                raise ValueError(f"Manifesto signature mismatch for {taxonomy_file}")

        self._taxonomy_manifesto_cache_path().write_text(
            json.dumps(manifesto, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._reload_imi_runtime_if_available()
        logger.info("Downloaded IMI taxonomy update %s with files: %s", manifesto.get("version"), ", ".join(downloaded))
        return bool(downloaded)

    @staticmethod
    def _reload_imi_runtime_if_available() -> None:
        try:
            from aion_imi import reload_runtime

            reload_runtime()
        except Exception as exc:
            logger.debug("IMI runtime reload after taxonomy refresh skipped: %s", exc)

    def refresh_taxonomy_manifesto(self, force: bool = False) -> bool:
        if not self.taxonomy_refresh_enabled:
            return False
        manifesto_url = self._effective_taxonomy_manifesto_url()
        if not manifesto_url:
            return False
        local = self._cached_taxonomy_manifesto()
        if (
            not force
            and local is not None
            and self._last_refreshed is not None
            and (self._now() - self._last_refreshed) < self.refresh_interval
        ):
            return False

        try:
            remote = self._fetch_json(manifesto_url)
            if not self._remote_manifesto_is_newer(remote, local):
                return False
            return self._download_taxonomy_manifesto_update(manifesto_url, remote)
        except Exception as exc:
            logger.warning("Failed to refresh IMI taxonomy manifesto: %s", exc)
            return False

    def _apply_live_session_payload(
        self,
        *,
        session_rules: Any = None,
        market_sessions: Any = None,
    ) -> None:
        """Apply live session timings over the bundled ones.

        A timing regime change (e.g. the Closing Auction Session) has to reach
        installs that will never upgrade the package, so it travels on the same
        refresh channel as events. Bad data here must not cost the caller their
        events: each block is applied independently and failures fall back to
        the bundled timings.
        """
        if isinstance(session_rules, dict):
            try:
                self.session_rules = self._load_session_rules(session_rules)
                self._live_session_rules = dict(session_rules)
            except Exception as exc:
                logger.warning("Ignoring live session_rules payload: %s", exc)
        if isinstance(market_sessions, dict):
            try:
                self.default_sessions = self._load_default_sessions(market_sessions)
                self._live_market_sessions = dict(market_sessions)
            except Exception as exc:
                logger.warning("Ignoring live market_sessions payload: %s", exc)

    def _load_cache(self) -> None:
        try:
            payload = json.loads(self._cache_path().read_text(encoding="utf-8"))
            last_refreshed = payload.get("last_refreshed")
            self._last_refreshed = _coerce_datetime(last_refreshed, self.tz) if last_refreshed else None
            generated_at = payload.get("generated_at")
            self._live_generated_at = _coerce_datetime(generated_at, self.tz) if generated_at else None
            self._live_version = payload.get("version")
            self._live_deleted_ids = {str(item).strip() for item in payload.get("deleted_ids", []) if str(item).strip()}
            self._live_events = {
                event.id: self._normalize_event(event.to_dict())
                for event in (MarketEvent.from_dict(record) for record in payload.get("events", []))
                if event.id not in self._live_deleted_ids
            }
            self._apply_live_session_payload(
                session_rules=payload.get("session_rules"),
                market_sessions=payload.get("market_sessions"),
            )
        except Exception:
            self._last_refreshed = None
            self._live_generated_at = None
            self._live_version = None
            self._live_deleted_ids = set()
            self._live_events = {}

    def _save_cache(self) -> None:
        payload = {
            "version": self._live_version,
            "generated_at": self._live_generated_at.isoformat() if self._live_generated_at else None,
            "last_refreshed": self._last_refreshed.isoformat() if self._last_refreshed else None,
            "deleted_ids": sorted(self._live_deleted_ids),
            "events": [event.to_dict() for event in self._live_events.values()],
            "session_rules": self._live_session_rules,
            "market_sessions": self._live_market_sessions,
        }
        self._cache_path().write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def refresh(self, force: bool = False) -> bool:
        taxonomy_refreshed = self.refresh_taxonomy_manifesto(force=force)
        if not self.refresh_url:
            return taxonomy_refreshed
        if (
            not force
            and self._last_refreshed is not None
            and (self._now() - self._last_refreshed) < self.refresh_interval
        ):
            logger.debug("Skipping market-calendar refresh; interval has not elapsed")
            return taxonomy_refreshed

        try:
            request = Request(self.refresh_url, headers=self._refresh_headers())
            with urlopen(request, timeout=10) as response:
                payload = json.load(response)
        except Exception as exc:
            logger.warning("Failed to refresh market-calendar live events: %s", exc)
            return False

        deleted_ids = {str(item).strip() for item in payload.get("deleted_ids", []) if str(item).strip()}
        live_events: dict[str, MarketEvent] = {}
        for record in payload.get("events", []):
            event = self._normalize_event(record)
            if event.id not in deleted_ids:
                live_events[event.id] = event

        generated_at = payload.get("generated_at")
        self._live_generated_at = _coerce_datetime(generated_at, self.tz) if generated_at else None
        self._live_version = payload.get("version")
        self._live_deleted_ids = deleted_ids
        self._live_events = live_events
        self._apply_live_session_payload(
            session_rules=payload.get("session_rules"),
            market_sessions=payload.get("market_sessions"),
        )
        self._last_refreshed = self._now()
        self._save_cache()
        logger.info("Loaded %d live market-calendar events from %s", len(live_events), self.refresh_url)
        return True

    def _all_events(self) -> tuple[MarketEvent, ...]:
        merged = {event.id: event for event in self.events}
        for deleted_id in self._live_deleted_ids:
            merged.pop(deleted_id, None)
        merged.update(self._live_events)
        return tuple(sorted(merged.values(), key=lambda event: (event.start, event.id)))

    def __iter__(self):
        return iter(self._all_events())

    def __len__(self) -> int:
        return len(self._all_events())

    def all_events(self) -> tuple[MarketEvent, ...]:
        return self._all_events()

    def _resolve_instrument_segment(self, name: str, *, mode: str = "primary") -> str | None:
        instrument = INSTRUMENT_TO_SEGMENT.get(name.strip().upper())
        if instrument is None:
            return None
        resolved = instrument.get(mode)
        if isinstance(resolved, str):
            return resolved
        return None

    def _resolve_market_key(self, market: str) -> str:
        return resolve_market_key(market)

    def _market_match(self, left: str, right: str) -> bool:
        return self._resolve_market_key(left) == self._resolve_market_key(right)

    @staticmethod
    def _market_lineage(market_key: str) -> list[str]:
        """*market_key* followed by the broader segments it belongs to."""
        lineage = [market_key]
        parent = SEGMENT_INHERITS_FROM.get(market_key)
        while parent and parent not in lineage:
            lineage.append(parent)
            parent = SEGMENT_INHERITS_FROM.get(parent)
        return lineage

    def _event_applies_to_market(self, event: MarketEvent, market: str) -> bool:
        if not event.applies_to:
            return True
        target_markets = set(self._market_lineage(self._resolve_market_key(market)))
        for item in event.applies_to:
            try:
                if self._resolve_market_key(item) in target_markets:
                    return True
            except ValueError:
                if item.strip().upper() in target_markets:
                    return True
        return False

    def _event_active_on_day(self, event: MarketEvent, day: date) -> bool:
        end = event.end or event.start
        return event.start.date() <= day <= end.date()

    def _event_active_at(self, event: MarketEvent, dt: datetime) -> bool:
        end = event.end or event.start
        return event.start <= dt <= end

    def holidays(
        self,
        market: str = "NSE",
        year: int | None = None,
        *,
        exchange: str | None = None,
    ) -> list[date]:
        target_market = self._resolve_market_key(exchange or market)
        results = {
            event.start.date()
            for event in self._all_events()
            if event.is_holiday
            and not event.session_override
            and self._event_applies_to_market(event, target_market)
            and (year is None or event.start.year == year)
        }
        return sorted(results)

    def covers(self, day: date) -> bool:
        """Whether *day* falls inside the bundled data's declared range."""
        if self.coverage_start is not None and day < self.coverage_start:
            return False
        if self.coverage_end is not None and day > self.coverage_end:
            return False
        return True

    def _warn_if_outside_coverage(self, day: date) -> None:
        """Outside the bundled range there are no holiday records, so answers
        degrade to weekday-only logic and quietly report holidays as open. Say so
        once per calendar rather than letting it pass silently."""
        if self._coverage_warned or self.covers(day):
            return
        self._coverage_warned = True
        logger.warning(
            "Date %s is outside the bundled calendar range (%s to %s). No holiday data exists "
            "there, so trading-day answers fall back to weekday-only logic and will report "
            "holidays as open. Load the data file for that year instead.",
            day.isoformat(),
            self.coverage_start,
            self.coverage_end,
        )

    def is_trading_day(self, dt: datetime, market: str = "NSE") -> bool:
        local_dt = _coerce_datetime(dt, self.tz)
        self._warn_if_outside_coverage(local_dt.date())
        market_key = self._resolve_market_key(market)
        if self._session_overrides_for_day(local_dt.date(), market_key):
            return True
        if local_dt.weekday() >= 5:
            return False
        return local_dt.date() not in set(self.holidays(market=market_key, year=local_dt.year))

    def _session_overrides_for_day(self, day: date, market: str) -> list[SessionSegment]:
        market_key = self._resolve_market_key(market)
        lineage = set(self._market_lineage(market_key))
        overrides: list[SessionSegment] = []
        for event in self._all_events():
            if not self._event_active_on_day(event, day):
                continue
            if not event.session_override:
                continue
            for segment in event.session_override:
                try:
                    segment_market = self._resolve_market_key(segment.market)
                except ValueError:
                    continue
                if segment_market in lineage:
                    overrides.append(segment)
        return sorted(overrides, key=lambda segment: (segment.open, segment.close))

    def active_session_rule(self, day: date, market: str = "NSE") -> SessionRule | None:
        """The effective-dated rule governing *market* on *day*, if any."""
        market_key = self._resolve_market_key(market)
        covering = [rule for rule in self.session_rules.get(market_key, []) if rule.covers(day)]
        if not covering:
            return None
        return max(covering, key=lambda rule: rule.effective_from)

    def _sessions_for_day(self, day: date, market_key: str) -> list[SessionSegment]:
        rule = self.active_session_rule(day, market=market_key)
        if rule is not None:
            return list(rule.segments)
        return list(self.default_sessions.get(market_key, []))

    def get_session(self, dt: datetime, market: str = "NSE") -> list[SessionSegment] | None:
        local_dt = _coerce_datetime(dt, self.tz)
        market_key = self._resolve_market_key(market)
        overrides = self._session_overrides_for_day(local_dt.date(), market_key)
        if overrides:
            return overrides

        if not self.is_trading_day(local_dt, market=market_key):
            return None

        return self._sessions_for_day(local_dt.date(), market_key) or None

    def active_sessions(self, dt: datetime, market: str = "NSE") -> list[SessionSegment]:
        local_dt = _coerce_datetime(dt, self.tz)
        sessions = self.get_session(local_dt, market=market) or []
        active: list[SessionSegment] = []
        current = local_dt.timetz().replace(tzinfo=None)
        for segment in sessions:
            if segment.open <= current <= segment.close:
                active.append(segment)
        return active

    def is_market_open(self, dt: datetime | None = None, market: str = "NSE") -> bool:
        local_dt = _coerce_datetime(dt or self._now(), self.tz)
        return bool(self.active_sessions(local_dt, market=market))

    def is_continuous_trading(self, dt: datetime | None = None, market: str = "NSE") -> bool:
        """True only during continuous order matching.

        `is_market_open` stays True through the Closing Auction Session — the
        market is still operating. Callers that place ordinary orders should
        gate on this instead, because 15:15-15:30 in F&O underlying stocks is
        an auction, not continuous trading.
        """
        local_dt = _coerce_datetime(dt or self._now(), self.tz)
        return any(segment.is_continuous for segment in self.active_sessions(local_dt, market=market))

    def closing_auction_session(self, dt: datetime, market: str = "NSE") -> SessionSegment | None:
        """The Closing Auction Session segment for *market* on that day, if it has one."""
        local_dt = _coerce_datetime(dt, self.tz)
        for segment in self.get_session(local_dt, market=market) or []:
            if segment.kind == SESSION_KIND_CLOSING_AUCTION:
                return segment
        return None

    def next_trading_day(
        self,
        after: date | datetime | str | None = None,
        market: str = "NSE",
    ) -> date:
        local_dt = _coerce_datetime(after or self._now(), self.tz)
        cursor = local_dt.date()
        while True:
            probe = _attach_timezone(datetime.combine(cursor, time(12, 0)), self.tz)
            if self.is_trading_day(probe, market=market):
                return cursor
            cursor += timedelta(days=1)

    def get_relevant_events(self, dt: datetime, indices: list[str]) -> list[MarketEvent]:
        local_dt = _coerce_datetime(dt, self.tz)
        index_tokens = {item.strip().upper() for item in indices if item and item.strip()}
        relevant: list[MarketEvent] = []
        for event in self._all_events():
            if not self._event_active_at(event, local_dt):
                continue
            if not event.applies_to:
                relevant.append(event)
                continue
            event_tokens = {item.upper() for item in event.applies_to}
            if event_tokens & index_tokens:
                relevant.append(event)
        return relevant

    def events_on(self, day: date | datetime | str, *, exchange: str | None = None) -> list[MarketEvent]:
        target = _coerce_datetime(day, self.tz).date()
        return [
            event
            for event in self._all_events()
            if event.day == target and (exchange is None or self._event_applies_to_market(event, exchange))
        ]

    def between(
        self,
        start: date | datetime | str,
        end: date | datetime | str,
        *,
        exchange: str | None = None,
    ) -> list[MarketEvent]:
        start_dt = _coerce_datetime(start, self.tz)
        end_dt = _coerce_datetime(end, self.tz)
        if isinstance(end, date) and not isinstance(end, datetime):
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return [
            event
            for event in self._all_events()
            if start_dt <= event.start <= end_dt and (exchange is None or self._event_applies_to_market(event, exchange))
        ]

    def upcoming(
        self,
        *,
        as_of: date | datetime | str | None = None,
        limit: int | None = None,
        exchange: str | None = None,
    ) -> list[MarketEvent]:
        cutoff = _coerce_datetime(as_of or datetime.now(self.tz), self.tz)
        events = [
            event
            for event in self._all_events()
            if event.start >= cutoff and (exchange is None or self._event_applies_to_market(event, exchange))
        ]
        return events[:limit] if limit is not None else events

    def by_category(self, category: str) -> list[MarketEvent]:
        needle = category.strip().lower()
        return [event for event in self._all_events() if event.category.lower() == needle]

    def search(self, text: str) -> list[MarketEvent]:
        needle = text.strip().lower()
        if not needle:
            return list(self._all_events())
        return [
            event
            for event in self._all_events()
            if needle in event.name.lower()
            or needle in (event.description or "").lower()
            or any(needle in tag.lower() for tag in event.tags)
            or needle in event.policy.reason.lower()
        ]


EventCalendar = IndiaMarketCalendar
