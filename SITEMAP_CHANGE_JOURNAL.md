# Sitemap change journal

## 2026-11-14 - candidate repair

Added CAL-DISCOVERY and opt-in CAL-UPDATER, their approval/artifact boundaries,
managed pointer/receipt stores and rollback. Updated CAL-STORE for strict
manifest/payload validation, bounded transfer and serialized atomic adoption.
CAL-ENGINE/PHASE now refuse uncovered sessions and share continuous-phase
semantics. CAL-DATA adds primary-notified NSE Muhurat phase/segment scope and
a coverage-bound review date. CAL-CLI offline applies to RSS as well.

Updated SITE_MAP.md, its data-flow diagram, UPDATE_CONTRACT, packaging and test
inventory in the same candidate change. Removed cross-product activation as a
runtime dependency; legacy entry point is retired. No service, production
schema, routing or deployment was modified. Test evidence is part of the
separate acceptance handoff, not proof of a production rollout.

### Final source reconciliation

CAL-PHASE now applies the unknown-special-schedule refusal to its convenience
API and safely skips unrelated unsupported overrides. CAL-LEGACY no longer
resolves another product's cache directory. Added direct regression cases;
all existing routing/deployment boundaries remain unchanged.

### Opt-in scheduled update cycle

Added CAL-AUTO, optional signature-verification dependency, pinned trust and
artifact-host boundaries, monotonic CHANNEL.json state and a scheduled-notice
mode. The updater rechecks channel generation before promotion. No normal API
import path, public endpoint or production service was changed. Added real
signed-channel cycle verification and rejection regressions.


## 2026-11-14 - proof/claim clarification

Updated README and map proof notes to distinguish code availability, foreground
polling, managed pointer promotion and OS-service deployment. No component,
route, dependency or runtime behavior changed. Original b9c378a implementation
and its artifact hashes remain the verification baseline.


## 2026-11-14T13:48:34.545348+00:00 | Managed update lifecycle candidate

Added CAL-LIFECYCLE, CAL-TRUST, CAL-USER-SERVICE and their tests/diagram. Updated CAL-UPDATER to inherited advisory guards with protocol-2 crash recovery. Added optional packaging dependency for explicit constraints. Boundaries: original environment read-only, Windows installation excluded, user-login/user-manager restart only, no production trust defaults. No deployed topology change.


## 2026-11-14T14:02:22.419498+00:00 | Final lifecycle evidence and offline publisher boundary

Clarified low-level watcher versus explicit customer supervision. Added offline signer and CLI tests under CAL-RELEASE; no publication path activated. Recorded native disposable service proof; runtime files remain unchanged from 2833fd0.


## 2026-11-14T15:13:47.699043+00:00 | Three-platform review candidate

Added source-only CAL-WINDOWS-ADAPTER, artifact verification workflow/helper, preserved independent probe and Windows ephemeral TLS test boundary. Updated the shared lifecycle graph and current status/doc artifacts. Worker/task/ACL/lease proof remains pending native CI; portable tests are explicitly scoped. No SQLite/PostgreSQL/Redis/ClickHouse, inference, trading, website or billing edge added. No production deployment or trusted release authority created.


## 2026-11-14T15:23:13.451890+00:00 | Native CI corrections

CAL-STORE adoption outcome now revalidates current data after bounded lock contention; no lock stealing, schema change or unverified adoption. CAL-WINDOWS-ADAPTER gains explicit capture_output translation and bounded stdin. Windows OS profile variables are a non-secret native process dependency. CAL-CI uses supported macos-15. Diagrams remain structurally valid; this changes proof/failure handling, not public API or storage topology.


## 2026-11-14T15:31:39.216747+00:00 | Native acceptance round three

CAL-WINDOWS-TLS-FIXTURE now uses in-memory OpenSSL with a Windows-only test extra, replacing the nonfunctional SslStream path. No production dependency added. CAL-STORE rejects an older manifest without freshness mutation. CAL-WINDOWS-ADAPTER ACL validation uses SID-valued rules, avoiding identity translation. Source diagrams remain valid; proof and test dependency boundaries updated.


## 2026-11-14T15:38:16.653807+00:00 | Scheduler acceptance closure

CAL-WINDOWS-ADAPTER uses encoded allowlisted local metadata instead of redirected console reads; there are no credential fields. Test evidence upload excludes managed environments. Native test observation window reflects scheduler/worker timing without changing update or market behavior. Map structure unchanged.


## 2026-11-14T15:43:41.301220+00:00 | Native module boundary

CAL-WINDOWS-ADAPTER now explicitly loads system PowerShell Utility and uses .NET process/ACL operations. No new service, credential store, scheduler privilege or backend dependency. Native validation remains pending.


## 2026-11-14T15:49:14.598288+00:00 | Terminal receipt and native diagnostics

CAL-OS-LIFECYCLE joins CURRENT version to the terminal upgraded supervisor receipt before application execution. CAL-WINDOWS-ADAPTER emits bounded phase/HRESULT diagnostics on failure. No schema, risk, calendar calculation, scheduler privilege or authentication change.


## 2026-11-14T15:53:59.157672+00:00 | Native task XML gate

CAL-WINDOWS-ADAPTER adds native task XML validation before create-only registration; serialization omits byte encoding for Unicode COM transport. CAL-OS-LIFECYCLE covers all five declared Windows Python versions in isolated CI. No new privilege or production service.


## 2026-11-14T16:05:58.344917+00:00 | Provider identity and NTFS contention

CAL-WINDOWS-ADAPTER reconciles provider principal representation using resolved SID equality and per-invariant diagnostics. CAL-STORE bounds retries for NTFS sharing/delete-pending lock operations. No ownership, approval, storage or release boundary changed.


## 2026-11-14T16:15:07.586953+00:00 | Durable enrollment ownership

CAL-LIFECYCLE adds a local setup-contract fingerprint and idempotent actual-state readback. CAL-WINDOWS-ADAPTER persists service intent before registering a disabled task, with native kill/uninstall regression. Explicit no-network notification and immutable controller boundaries are clarified. No new production service, database or permission boundary.


## 2026-11-14T16:23:49.108845+00:00 | Native fixture closure

CAL-OS-LIFECYCLE includes the Python3.10 controller typing_extensions dependency and a corrected immutable crash marker. Runtime updater, signatures, market rules and task permissions are unchanged. Native evidence still gates acceptance.


## 2026-11-14T16:34:33.180769+00:00 | Native readback and release limits

Proof-only update to CAL-CI-ARTIFACTS/CAL-OS-LIFECYCLE/CAL-WINDOWS-ADAPTER. Windows native acceptance is now observed, not merely staged; production/no-reboot boundaries remain. Existing diagrams match unchanged topology. NO_MAP_IMPACT to runtime/dependencies for this documentation-only commit; exact code source is pinned in RELEASE_STATUS.


## 2026-11-14T16:35:41.515354+00:00 | Final native provider readback

Proof-only final readback for CAL-CI-ARTIFACTS and CAL-OS-LIFECYCLE. Actual provider states show no remaining owned running/scheduled/registered supervisors. No dependency or topology changed; NO_MAP_IMPACT runtime. Canonical map and current gate record agree.


## 2026-11-14T17:01:49.256271+00:00 | Final correctness release preparation

Added CAL-PUBLICATION-GATE/CAL-PUBLISHER-IDENTITY/CAL-ADVISORY, diagram and exact external CI/OIDC/PyPI boundaries. CAL-RELEASE now manual immutable-artifact promotion, not tag-triggered rebuild/upload. Test credentials are ephemeral, no package-runtime topology change. Calendar engine/data/managed lifecycle and protected production workloads untouched.


## 2026-11-14T17:10:35.695301+00:00 | Final source consistency

Proof/documentation-only follow-up for CAL-RELEASE/CAL-DOCS. No runtime/dependency edge changed. Existing graph remains accurate; source freeze and hash evidence must advance for packaged prose.


## 2026-11-14T17:16:21.618106+00:00 | Windows CRT boundary closure

CAL-STORE native error boundary corrected without changing store topology, rule/session calculations or deployment. Updated platform/error proof and required regression coverage. Retired unrelated implementation anecdote removed from active public module documentation; Git history retained. No proprietary model code or production store accessed.

2026-11-15: review scope: IN-UPDATE/IN-DOCS: review-only user-visible notifications and source-labeled architecture.

Review-only local signed-offer notification boundary, no changes to the frozen package or calendar API.
