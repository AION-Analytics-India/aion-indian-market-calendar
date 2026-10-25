# CLAUDE.md - aion-indian-market-calendar

`AGENTS.md` is the operating contract for this repository and is loaded here:

@AGENTS.md

Before changing anything, read `SITE_MAP.md`, then the top of `CHANGELOG.md`.

Commands:

```bash
pip install -e ".[dev]"
AION_IN_CALENDAR_OFFLINE=1 pytest -q          # the whole suite, no network
python -m build                               # wheel and sdist into dist/ (git-ignored)
```

This repository is public. Anything written here, including in a commit message, is published.
