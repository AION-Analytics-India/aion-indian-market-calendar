# Contributing

Corrections to holiday data are the most valuable contribution this project can
receive, and they do not require writing any code.

## Reporting a wrong date

Open an issue with the year, the date, and what it should be. If you can point
at the Labour Code or another primary source, include it. Holiday rules are the
one thing in this package that must be right, and a native speaker noticing a
wrong name or a missing day is worth more than a refactor.

Three questions we would particularly like answered by someone in India:

1. Is the list of sixteen statutory non-working days complete?
## Code changes

1. Fork and branch from `main`.
2. Add a test. Holiday logic without a test will not be merged.
3. Run the suite: `python -m pytest tests -q`
4. Keep to PEP 8, four spaces, type hints where they help.

Holidays are computed rather than stored in a table, deliberately: it is what
makes the package correct for any future year without maintenance. Please do not
replace the computation with a data file.

## Licence

By contributing you agree your work is licensed under the MIT Licence.

## Links

- Package: https://pypi.org/project/aion-india-market-calendar/
- Website: https://dashboard.aiondashboard.site
