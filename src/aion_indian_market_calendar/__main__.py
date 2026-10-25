import argparse
import sys
import logging
import os
from pathlib import Path

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

def cmd_update(args):
    """Refresh the hash-verified holiday data now.

    Until 1.6.0 this command required a --refresh-url and defaulted to a
    live-events endpoint that ``IndiaMarketCalendar.refresh`` has ignored since
    1.4.1, so the URL did nothing and leaving it out was an error. It now runs
    the same verified refresh the library uses. The data source is set with
    AION_IN_CALENDAR_URL.
    """
    from aion_indian_market_calendar import store
    logger = logging.getLogger("nse_calendar_poller")

    if args.refresh_url:
        logger.warning(
            "--refresh-url / AION_CALENDAR_REFRESH_URL is ignored since 1.4.1; "
            "set AION_IN_CALENDAR_URL to change the data source."
        )
    result = store.refresh(force=args.force)
    logger.info("Holiday data refresh: %s", result)
    logger.info("Calendar update complete")

def cmd_poll(args):
    logger = logging.getLogger("nse_rss_poller")
    try:
        import feedparser
    except ImportError:
        logger.error("feedparser is required for the 'poll' command. Install it with: pip install feedparser")
        sys.exit(1)
        
    import datetime as dt
    
    NSE_RSS_URL = "https://nsearchives.nseindia.com/content/RSS/Circulars.xml"
    KEYWORDS = ("holiday", "trading session", "muhurat", "market closed", "market timing", "session")

    def _now_utc() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def _published_at(entry) -> dt.datetime | None:
        parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if not parsed:
            return None
        return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)

    logger.info("Fetching RSS circulars from %s", NSE_RSS_URL)
    feed = feedparser.parse(NSE_RSS_URL)
    if getattr(feed, "bozo", False):
        logger.error("RSS parse error: %s", getattr(feed, "bozo_exception", "unknown"))
        sys.exit(1)

    cutoff = _now_utc() - dt.timedelta(hours=args.lookback_hours)
    matches = []
    for entry in feed.entries:
        published_at = _published_at(entry)
        if published_at and published_at < cutoff:
            continue

        title = str(getattr(entry, "title", "")).strip()
        lower_title = title.lower()
        if not any(keyword in lower_title for keyword in KEYWORDS):
            continue

        matches.append(
            {
                "title": title,
                "link": str(getattr(entry, "link", "")).strip(),
                "published": str(getattr(entry, "published", "")).strip(),
                "summary": str(getattr(entry, "summary", "")).strip(),
            }
        )
        
    logger.info("Found %d relevant circulars.", len(matches))
    
    out_path = Path(args.output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = [f"# New NSE circulars found at {_now_utc().isoformat()}", ""]
    if not matches:
        lines.append("No new relevant circulars.")
    else:
        for item in matches:
            lines.extend(
                [
                    f"## [{item['title']}]({item['link']})",
                    f"Published: {item['published']}",
                    "",
                    item["summary"] or "_No summary provided._",
                    "",
                    "Action: review and add/remove entries in `live_events.json` if the calendar should change.",
                    "",
                ]
            )
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    logger.info("Wrote review queue to %s", out_path)

def main():
    setup_logging()
    parser = argparse.ArgumentParser(
        description="AION Indian Market Calendar CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")
    
    # Update command
    parser_update = subparsers.add_parser("update", help="Refresh the hash-verified holiday data now")
    parser_update.add_argument(
        "--lookback-hours",
        type=float,
        default=6.0,
        help="Minimum hours between refresh attempts (default: 6)",
    )
    parser_update.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.9,
        help="Minimum confidence for accepting live events",
    )
    parser_update.add_argument(
        "--refresh-url",
        default=os.getenv("AION_CALENDAR_REFRESH_URL", "").strip(),
        help="Ignored since 1.4.1, kept so existing scripts do not break; use AION_IN_CALENDAR_URL",
    )
    parser_update.add_argument(
        "--force",
        action="store_true",
        help="Force refresh regardless of last-refresh interval",
    )
    
    # Poll command
    parser_poll = subparsers.add_parser("poll", help="Poll NSE RSS circulars and write to review queue")
    parser_poll.add_argument(
        "--lookback-hours",
        type=float,
        default=6.0,
        help="Hours to look back for new RSS feeds (default: 6)",
    )
    
    pkg_dir = Path(__file__).resolve().parent
    default_out_path = pkg_dir.parents[1] / "review_queue" / "latest.md"
    parser_poll.add_argument(
        "--output-path",
        default=str(default_out_path),
        help="Output path for review queue markdown file",
    )
    
    args = parser.parse_args()
    if args.command == "update":
        cmd_update(args)
    elif args.command == "poll":
        cmd_poll(args)

if __name__ == "__main__":
    main()
