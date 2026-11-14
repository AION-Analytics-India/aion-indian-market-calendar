# Calendar correctness advisory - 14 November 2026

We reproduced correctness defects in the published 1.7.1 wheel of AION Indian
Market Calendar. We apologize for these errors and the uncertainty they can
cause developers relying on schedule-critical results. Version 1.8.0 contains
the independently tested corrections. Verify its actual availability and files
on [PyPI](https://pypi.org/project/aion-indian-market-calendar/1.8.0/) before upgrading;
a branch or this advisory alone does not establish publication.

## Verified affected version and results

Affected artifact: published 1.7.1 wheel SHA256
`02ff1daa1a715a6cfd67401f65e9c70f88406128d86208921f8318fc81fd6bd7`.
The independent 42-case probe reports 33 passes / 9 failures for that wheel and 42/42
for the corrected candidate. Other versions were not independently established
as affected by these same cases. No live trade, service failure or loss is
inferred from these isolated package results.

| Probe / input | Published 1.7.1 | Corrected 1.8.0 |
| --- | --- | --- |
| Continuous NSE F&O-underlying cash at 2026-12-07T15:30:00+05:30 | True | False, auction transition |
| Class trading-day query, 2027-01-26T10:00+05:30 | True | ValueError, uncovered date |
| Class market-open query, 2027-01-26T10:00+05:30 | True | ValueError, uncovered date |
| Module trading-day query, 2026-12-28 | True | ValueError, uncovered date |
| Trading-day helper, 2026-10-23T22:00:00Z | True | False, October24IST |
| Settlement helper, 2026-10-23T22:00:00Z | True | False, October24IST |
| NSE non-CAS Muhurat continuous window, 2026-11-08 | 18:15-19:15 | 14:20-15:30 |
| Existing reader after valid fixture refresh | Retains 18:15-19:15 | Follows verified 14:20-15:30generation |
| Due dataset recheck in loaded process | No manifest request | Performs bounded eligible check |

The refresh cases use immutable synthetic suppliers of preserved historical
public-data fixtures, not a production network rewrite. The original probe
and its fixture paths ship in the source distribution. See
[scripts/verify_independent_contract.py](../scripts/verify_independent_contract.py)
and [artifact verification](../scripts/verify_release_artifacts.py).

## Official schedule evidence

- [SEBI October 15 closing-auction circular](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1792079571420.pdf): effective December 7 rules, not retrospective random-auction telemetry.
- [NSE CMTR 76941](https://nsearchives.nseindia.com/content/circulars/CMTR 76941.pdf): notified November 8 cash Muhurat windows; CAS/non-CAS scope differs.
- [NSE FAOP 76940](https://archives.nseindia.com/content/circulars/FAOP 76940.pdf): notified F&O special session; do not infer unknown schedules.
- [NSE currency calendar CD 71962](https://nsearchives.nseindia.com/content/circulars/CD 71962.pdf) and [INR contract specification](https://www.nseindia.com/static/products-services/currency-derivatives-contract-specification-inr): separate CDS scope/holidays.

Timezone, unknown-date and refresh corrections are software-contract defects;
no exchange circular is claimed as a source for software internals. Dataset
coverage is 2026-01-01 through2026-12-25. No 2027 Indian holidays were fabricated.
CDS INR 09:00-17:00IST and seasonal non-agri commodity limits remain distinct.

## Remediation and update limits

After confirming replacement availability, use the interpreter used by your
application:

```bash
python -m pip install --upgrade aion-indian-market-calendar
python -c "import importlib.metadata as m; print(m.version('aion-indian-market-calendar'))"
```

A current holiday-data cache cannot fix Python-code defects. Retest and restart
your application under its approved deployment process. Exact pins/lockfiles
need explicit review. A yank does not uninstall code or prevent every exact-pin
installation; no historical release is deleted by this advisory.

Ordinary pip does not install a background supervisor, enroll users or switch
running application interpreters. The optional managed updater needs separate
consent, trust/bootstrap artifacts and managed-runtime adoption. It is
experimental and not production-activated. Windows updater rollout is paused.
There is no promise that all future patches install automatically for all users.

This package provides scheduled exchange-calendar information, not a live
exchange-status feed, broker API, trading recommendation or compliance guarantee.
Exchange announcements remain authoritative. See [README](../README.md),
[release notes](../RELEASE_NOTES_1_8_0.md) and [update contract](UPDATE_CONTRACT.md).
