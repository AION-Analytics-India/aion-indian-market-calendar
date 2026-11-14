# 1.8.0 build-time release evidence and limits

This is a correctness-only release source. This file records build-time scope,
not a live PyPI status feed. Verify actual publication, date and downloadable
hashes on https://pypi.org/project/aion-indian-market-calendar/1.8.0/ and the
corresponding GitHub release. Source availability alone is not release proof.

| Gate | Evidence / boundary |
| --- | --- |
| Calendar correctness | Prior native three-OS wheel/sdist and42-case probe passed; final source/artifact acceptance is required after these documentation/publisher changes |
| macOS/Linux updater | Actual disposable launchd/systemd lifecycle16/16 each, Python3.13, run43615709127 |
| Windows library | Native Server2022 x64 wheel/sdist, Python3.10-3.14, passed in prior run; final artifact checks retained |
| Windows updater | Actual Task Scheduler17/17 each on3.10-3.14 passed; production rollout PAUSED by owner |
| Production automatic installation | BLOCKED on allOS: no approved production trust/channel/bootstrap/workload activation |
| Real reboot / Windows11 consumer | Not verified; not required to approve the separate correctness-only release |
| Python3.9 / Indian2027data | Unsupported |
| CDS | NSE INR pairs09:00-17:00IST, currency-specific holidays, within coverage; no BSE/cross-currency/expiry claim |
| Publisher | Manual exact-source/run/hash gate; no automatic tag upload, no rebuild after approval, no skip-existing |

Prior verified run: https://github.com/AION-Analytics-India/aion-indian-market-calendar/actions/runs/43615709127
Its exact23-job evidence and historical artifact hashes remain attached to that
source, not falsely attributed to a later build. The final release manifest
records new accepted hashes after the final source is frozen. Current-code
changes since that run are public copy, packaging and publishing gates; calendar
engine/data and managed-updater behavior are unchanged except the bounded Windows
CRT sharing-denial mapping in calendar-data lock acquisition. A final native
reproduction and deterministic refusal tests are required for that correction.

The publication preflight checks actual accepted artifact identity, packaged
README/license/code/data agreement, required native jobs, current ref/source,
unused PyPI version and configured trusted-publisher exchange without uploading.
Publication additionally requires exactv1.8.0tag and explicit founder GO. PyPI
trusted publishing is distinct from a production managed-update signing root.
The PyPI environment currently has no required reviewers; owner release control
must be exercised through the exact authorized manual dispatch, not assumed.

Normal pip creates no OS job or managed environment. Original application
runtimes remain unchanged. Default enrollment is not automatic installation;
experimental signed updates need separate explicit owner-controlled adoption.
The pinned controller itself is not replaced by runtime patch promotion. No
all-future-release upgrade promise is made. No production workload is modified.
