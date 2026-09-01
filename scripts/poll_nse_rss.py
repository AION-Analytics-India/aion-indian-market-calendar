#!/usr/bin/env python3
"""Shim for legacy script routing to standardized CLI."""
import sys
from aion_indian_market_calendar.__main__ import main

if __name__ == "__main__":
    # Inject 'poll' command to mimic original behavior
    sys.argv.insert(1, "poll")
    main()
