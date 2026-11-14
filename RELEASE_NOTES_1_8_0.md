# 1.8.0 correction release notes (draft, not published)

Release state and platform evidence: RELEASE_STATUS.md. Exact published version,
date, final wheel/sdist hashes and approved tag must be inserted only after
actual release readback. No fixed PyPI release exists yet.

The candidate corrects unsupported-date answers, aware datetime-to-IST date
selection, continuous-matching versus auction boundaries, covered NSE Muhurat
scope and offline refresh behavior. It preserves the effective-dated 7 December
2026 closing-auction/derivatives schedule and documented segment limits. It ships
complete sdist fixtures and keeps review scheduling within the data horizon.

NSE CDS INR pairs retain their distinct 09:00-17:00 IST session and separate
currency holidays. Equity pre-open is not continuous matching. Neither the CDS
nor the general derivatives query certifies an individual contract cutoff.
Indian 2027 calendar coverage remains unsupported.

Existing users must manually upgrade the Python environment actually used by
their application after a fixed release is published, then check its version
and rerun affected scheduling regressions. Earlier affected versions beyond the
verified published 1.7.1 have not been established. Do not imply trading loss or
live incidents from isolated calendar probes.

Calendar-data refresh is independent of Python software upgrades. Normal pip
installation registers no task. The staged managed updater requires explicit
onboarding, trusted signed distribution and platform acceptance. It leaves the
original pip environment unchanged. No production automatic-install capability
is approved. Windows implementation and native validation are separate; actual
reboot and production signing/channel gates remain open.

Public correction/advisory and exact before/after matrix are staged in the
private publication handoff. Release owner must approve them and the final
artifacts before any upload, tag, merge, advisory or platform change.
