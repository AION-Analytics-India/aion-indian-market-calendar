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
