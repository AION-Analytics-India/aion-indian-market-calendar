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
    from aion_indian_market_calendar import IndiaMarketCalendar
    logger = logging.getLogger("nse_calendar_poller")
    
    if not args.refresh_url:
        logger.error("No refresh URL configured — set AION_CALENDAR_REFRESH_URL or pass --refresh-url")
        sys.exit(1)
        
    logger.info(
        "Starting calendar poll: refresh_url=%s lookback_hours=%.1f",
        args.refresh_url,
        args.lookback_hours,
    )
    
    calendar = IndiaMarketCalendar.bundled(
        2026,
        refresh_url=args.refresh_url,
        refresh_interval_hours=args.lookback_hours,
    )
    refreshed = calendar.refresh(force=args.force)
    
    if refreshed:
        live_count = len(calendar._live_events)
        deleted_count = len(calendar._live_deleted_ids)
        logger.info(
            "Calendar refresh succeeded: live_events=%d deleted_ids=%d",
            live_count,
            deleted_count,
        )
    else:
        logger.info("Calendar refresh skipped — no update needed or endpoint unavailable")
        
    logger.info("Calendar poll complete")

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
    parser_update = subparsers.add_parser("update", help="Poll live-refresh endpoint for holiday updates")
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
        default=os.getenv("AION_CALENDAR_REFRESH_URL", "https://api.aiondashboard.site/v1/calendar/live").strip(),
        help="URL for the live calendar refresh endpoint",
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
