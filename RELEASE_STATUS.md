# Calendar 1.8 release status

Dated 14 November 2026. UNRELEASED. No production change. This supersedes only
current-readiness interpretations of earlier dated evidence; historical reports
and hashes are retained. A verification branch is not a released package.

| Gate | State | Exact evidence or missing requirement |
| --- | --- | --- |
| Public release | 1.7.1 | Public PyPI/main readback; 1.8.0 remains an unpublished candidate |
| Native library/artifact matrix | PASS | GitHub run 43615709127, wheel and sdist on macOS 15 ARM64, Ubuntu 24.04 x64 and Windows Server 2022 x64, Python 3.10-3.14; independent 42-case probe per artifact |
| Windows managed lifecycle | PASS in disposable CI | Same run, real Task Scheduler, Python 3.10-3.14; 17 cases each including scheduled signed patch, recovery, rollback, revocation and interrupted-setup teardown |
| Linux managed lifecycle | PASS in disposable CI | Same run, actual user systemd timer, Python 3.13, 16 cases |
| macOS managed lifecycle | PASS in disposable CI | Run 43615709127, actual launchd, Python 3.13, 16 cases |
| Windows 11 consumer/reboot | UNVERIFIED | Dedicated normal-user desktop and authorized real reboot/logon acceptance |
| Real macOS/Linux reboot | UNVERIFIED | User-manager stop/start is tested; no physical reboot was performed |
| Production signing | BLOCKED | Founder must name offline root custodian and approve process, storage and public fingerprint |
| Production distribution | BLOCKED | Approved signed trust/release/bootstrap channel and real customer-path readback |
| Release CI | VERIFICATION EXECUTED; PUBLISHER REVIEW REQUIRED | Verification workflow runs only tests. Legacy tag publisher needs the reviewed reusable-workflow integration and protected PyPI identity approval. No tag used for testing |
| Protected AION workloads | NOT DEPLOYED | Existing admission boundary remains; no live controller/workload was modified |
| Python | >=3.10 | Native artifact matrix 3.10-3.14; 3.9 unsupported. Native scheduler matrix is narrower on macOS/Linux |
| Indian 2027 data | UNSUPPORTED | No approved authoritative payload in this candidate |
| CDS | SUPPORTED within covered dates | NSE INR pairs 09:00-17:00 IST, currency-specific holidays; BSE CDS/cross-currency/contract expiries unsupported |

Code tested: GitHub 855e8171625b7763a7d070277f0a6b2b3a0b86a3. Later source edits
are documentation-only and do not change that runtime. See the exact provider
run and private release handoff for its artifact hashes, retained failed attempts
and final readback. Test keys are synthetic, private bytes stay in memory.

CALENDAR_CORRECTNESS: PASS within covered, tested contract. This is not authority
to publish. AUTO_UPDATE_PRODUCTION: BLOCKED independently of calendar tests.
A correctness-only release may be reviewed with automatic installation disabled;
final publisher/artifact and advisory approval are still required.

## Customer ownership and limits

Normal pip creates no service and opts nobody in. Older users manually bootstrap
once, then explicitly adopt a separate managed runtime using an approved policy,
bootstrap manifest and wheel closure. Original pip environments and running
applications stay unchanged. Only selected applications launched through managed
run use the new runtime. Notifications are local receipts/output, not email/toast.
Automatic installation needs separate explicit consent. Pins, patch-series,
signature/health checks, offline policy and active-workload admission can defer or
reject a patch. The pinned controller itself needs a separately reviewed bootstrap.
Do not promise every future code release installs in every existing environment.

## Scope of verification

.github/workflows/verify-candidate.yml builds once and verifies exact artifacts,
installed imports and complete sdist fixtures. Windows library/kernel-primitive
scope explicitly excludes four POSIX-oriented updater modules; its actual native
scheduler lifecycle is a separate job. macOS/Linux run the full packaged suite.
Required assertions are not skipped. Actual later timer ticks, original/managed
interpreter versions, crash recovery and provider teardown are read back.

Windows uses an owned InteractiveToken/LeastPrivilege task. No SYSTEM, S4U,
password, elevation fallback or unrelated task change is used. Logged-out network
operation is not promised. Hosted Server 2022 is not Windows 11 consumer evidence.
No production signing, package upload, model/trading/billing change or customer
enrollment is authorized by these test results.

BLOCKED_WITH_EXACT_REMAINING_GATES: production trust/channel/bootstrap ownership,
real reboot/Windows 11 consumer acceptance, protected deployment acceptance and
approved final publisher/artifacts remain separate release decisions.


## Final provider readback

[GitHub run 43615709127](https://github.com/AION-Analytics-India/aion-indian-market-calendar/actions/runs/43615709127):
23/23 jobs succeeded. Independently read all 15 artifact result files and seven
lifecycle result files, including provider readback of disabled/unregistered,
non-running supervisors. There are 30 artifact installations, 8,210 packaged
suite assertions and 1,260 independent-probe case executions, with zero failures,
errors or skipped assertions in their declared scopes. Lifecycle checks are
17 per Windows interpreter and 16 each on macOS/Linux (117 repeated executions,
not 117 unique features). The original pip runtime stayed at 1.8.0 while the
explicitly managed runtime ran the signed synthetic 1.8.1 patch.

Exact CI-built artifact SHA-256, independently matched to downloaded bytes:

- Wheel: b8fdeed3d90440d5280f772d64929bd4d4aaab45d968ea317d98cda97e572f52
- Sdist: 526c5b982155391092068c557a8578981897b1be0475475a4fa507149633df78

Those artifacts belong to code commit 855e817. Later prose-only readback commits
are not falsely represented as those same built artifact bytes. Before an actual
release, the approved final source/artifacts and publisher need their own exact
identity/integrity acceptance. No synthetic patch was published.
