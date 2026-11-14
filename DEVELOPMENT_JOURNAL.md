# Development journal

## 2026-11-14 - isolated 1.8.0 repair candidate

Founder scope: repair audited defects, add explicit software discovery and
managed upgrades, prove artifact installations. No publication/deployment.
Base fbe7c310ec0d953350dc53465ceb3360e1f8198d. The original checkout's
unrelated AGENTS.md edit was preserved. Public README additions at pinned
5e7d189c were reconciled in this candidate only; no remote was written.

Mapping impact: CAL-API/ENGINE/PHASE/STORE/DATA/CLI, new CAL-DISCOVERY and
CAL-UPDATER boundaries. SITE_MAP and its diagram were updated. Date refusal
and continuous matching are intentional correctness changes, not cosmetic.
The old warning-only test was strengthened to require refusal. Lifecycle
assertions remain intact and use an exact historical November 3 fixture.
Full results and artifact identities are retained in the release handoff.

Final review strengthened unknown NSE F&O schedule refusal across both class
and convenience APIs and removed another product's cache-path resolution from
retired compatibility validation. Source tests and final artifact tests cover
these boundaries. Original fixture snapshots and published 1.7.1 remain intact.

Clarified existing-client notifications: earlier releases cannot gain a checker
retroactively. Added a separately opted-in signed-channel check/watch cycle,
notification-only default and explicit approved-install mode. Production trust
keys/channel hosting/service activation remain unconfigured. Local ephemeral
keys exercise the actual cryptographic verification and download-to-promotion
path. This changes the candidate dependency/test inventory, not any deployment.


## 2026-11-14 - final auto-update verification wording

Staged README clarification after a fresh artifact-level bootstrap and real
60-second timer test. Ordinary pip installation does not register a service,
adopt a managed environment or enable later patches. Key/channel activation,
persistent scheduling and lifecycle controls remain production blockers.
NO_MAP_IMPACT to implementation; no runtime file or audited artifact changed.


## 2026-11-14T13:48:34.545348+00:00 | Managed update lifecycle candidate

Implemented explicit managed setup, immutable controller/runtime separation, per-user launchd/systemd operations, actual status readback, compatible patch-series and exact dependency constraints, root-signed rotating/revoked release identities, workload leases and protected controller admission. Real macOS job completed unattended signed update and automatic interrupted-operation recovery. Native Linux testing exposed repeated-disable/uninstall behavior for external links; repaired using inactive/disabled provider readback. The final candidate is being retested; production trust remains independently blocked. No public release or production changes.


## 2026-11-14T14:02:22.419498+00:00 | Final lifecycle evidence and offline publisher boundary

Final runtime wheel passed 15 native lifecycle cases each on macOS launchd and Linux systemd, including unattended patch execution, actual kill/recovery, rotation/revocation, rollback, disable/uninstall and no remaining jobs. Installed wheel and sdist suites passed 274 cases each; Linux Python3.11/3.12 suites passed 274 each; independent calendar probe passed42/42. Linux3.12 host lacks ensurepip, so managed setup safely refuses before root creation. Added separately tested offline signing CLI; production trust/channel remains unverified. No production service, repository publication or workload change.


## 2026-11-14T15:13:47.699043+00:00 | Three-platform review candidate

Added staged native Windows Task Scheduler/WinAPI adapters to the existing managed lifecycle, with no alternate signing or promotion implementation. Added native artifact CI and portable lifecycle driver with in-memory Windows TLS fixtures. Focused macOS changed-code tests passed 68 with no skips. Native CI is explicitly owner-authorized but pending execution. Current docs now use RELEASE_STATUS.md, preserve historical results and show separate calendar/updater/Windows 11/trust gates. CDS documentation explicitly covers NSE INR pairs 09:00-17:00 IST and currency holidays. Mapped CAL-WINDOWS-ADAPTER, CAL-CI-ARTIFACTS, CAL-OS-LIFECYCLE and test TLS boundaries. No calendar calculations/data, production or public default branch changed.


## 2026-11-14T15:23:13.451890+00:00 | Native CI corrections

Native verification branch was explicitly authorized and submitted. First CI source tree matched local source byte-for-byte. Linux actual scheduled lifecycle passed. Native artifact tests exposed a real concurrent-refresh outcome race plus Windows adapter/fixture defects. Retained every failure and unchanged acceptance assertion. Reconcile adoption timeout only by verified equal/newer data, fix native child capture semantics, bound PowerShell JSON to one line and supply required Windows OS profile variables. Add real native locked-pointer and process-tree tests. Replace retired macos-14 label with officially supported macos-15.


## 2026-11-14T15:31:39.216747+00:00 | Native acceptance round three

Native second run exposed a pre-existing older-manifest freshness-marker mutation, which is now repaired without changing the regression. Native Windows lease/tree tests executed; corrected pointer fixture to read only after releasing its intentionally exclusive handle. ACL enumeration now requests SID identities directly rather than doing account-name resolution. Replace Windows SslStream test TLS after native handshake failure with in-memory OpenSSL. Added Windows-only test dependency compatible with the existing cryptography range; normal library/updater dependencies unchanged. Local trusted/untrusted TLS smoke and fixture teardown passed.


## 2026-11-14T15:38:16.653807+00:00 | Scheduler acceptance closure

Third native run passed the non-Windows package gates and native Windows lease/process-tree checks, but ACL helper console input still timed out. Replaced redirected Console.In with encoded non-secret path/task metadata, with an explicit allowed-field set; credentials/private keys are never accepted. Mac scheduled update had started before the 110-second test cutoff without a terminal failure. Set the observation window to 330 seconds (poll interval plus bounded worker envelope), retaining exact state/signature/rollback assertions and recording elapsed time. This is test observation, not an SLA. Restrict uploaded lifecycle evidence to JSON/log receipts, not thousands of environment files.


## 2026-11-14T15:43:41.301220+00:00 | Native module boundary

Native Windows startup works in the full runner environment but stalls in stripped child environments. The next candidate pins module loading to the system PowerShell Utility module and uses direct .NET process/ACL APIs instead of autoloaded management/security cmdlets. This is a narrowly scoped native-boundary correction; it is not yet a proven native fix. Portable adapter/verifier tests remain 11/11. No permission or trust checks removed.


## 2026-11-14T15:49:14.598288+00:00 | Terminal receipt and native diagnostics

Native Windows package artifacts now pass Python 3.10-3.14, including independent probes and kernel primitives. The real scheduler still fails during registration, so added only phase/HRESULT diagnostic codes (no identity, path, credential or exception text) to distinguish policy denial from contract defects. Mac evidence proves signed 1.8.1 installation; immediate run correctly encountered the still-held safety lease. The harness now waits for the upgraded supervisor receipt emitted after lease release, not CURRENT.json alone. No workload guard was weakened.


## 2026-11-14T15:53:59.157672+00:00 | Native task XML gate

Native registration diagnostic confirmed SCHED_E_MALFORMEDXML (0x8004131A), not a request for broader permissions. Omit the byte-encoding declaration from Unicode COM task XML and require TASK_VALIDATE_ONLY before create-only registration. Keep InteractiveToken, least privilege, no passwords and ownership checks. Extend actual Windows scheduler lifecycle matrix to Python 3.10-3.14; macOS/Linux native lifecycle remains separately tested. No release activation.


## 2026-11-14T16:05:58.344917+00:00 | Provider identity and NTFS contention

Native task XML now validates and registers, but the provider returns principal names as well as SIDs. Ownership verification resolves the provider principal to its actual SID and compares with the current authorized SID; no short-name trust or permission expansion. Added per-invariant failure phases. A native Windows Python3.10 data-refresh contention failure returned access-denied for a transient NTFS delete-pending lock. Existing five-second bounds now retry only documented sharing/delete-pending native error codes while never stealing a stale lock; original concurrent assertions remain unchanged.


## 2026-11-14T16:15:07.586953+00:00 | Durable enrollment ownership

Persist Windows task registration intent before provider mutation so a killed setup retains an exact owned task record. Treat only SCHED_E_TASK_NOT_RUNNING as idempotent stop and still require provider readback. Matching setup contracts return actual status without mutation or automatic re-enablement; changed/legacy contracts refuse. Native driver now kills a setup after real disabled-task creation and verifies two uninstalls. Documentation clarifies local notices, pinned controller ownership and managed offline runtime; no universal auto-upgrade claim.
