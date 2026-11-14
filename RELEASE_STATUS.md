# Calendar 1.8 release status

Dated 14 November 2026. This branch is UNRELEASED. No production change.
This record supersedes only current-readiness interpretations of earlier dated
handoffs. Earlier audit outputs, release notes and hashes remain historical.

| Gate | State | Evidence or exact missing requirement |
| --- | --- | --- |
| Public release | 1.7.1 | PyPI readback, 14 November; 1.8.0 is local only |
| Prior calendar correctness | PASS within tested scope | dbb41b4 wheel/sdist 276 each; independent probe 42; macOS/Linux results in private handoff 08 |
| Current review source | NOT RELEASE APPROVED | Windows adapter and CI staged; rebuild and platform acceptance required |
| Windows x64 candidate library | NOT TESTED | Native wheel, sdist and independent 42-case checks, Python 3.10-3.14 |
| Windows managed lifecycle | NOT TESTED | Real interactive task, signed fixture upgrade, recovery, ACL/lease/job/teardown tests |
| Windows 11 consumer/reboot | NOT TESTED | Dedicated normal-user desktop and authorized reboot/logon test |
| macOS/Linux prior lifecycle | PASS, earlier candidate only | Actual launchd/systemd 15 cases each; focused regression on current review source is separate evidence |
| Real reboot persistence | UNVERIFIED | No production host reboot is authorized |
| Production signing | BLOCKED | Founder must name root custodian and approve offline process/storage/fingerprint |
| Production distribution | BLOCKED | Approved signed trust/channel/bootstrap URLs, immutable artifacts and customer-path readback |
| Release CI | AUTHORIZED, NOT YET EXECUTED | Founder requested native package and actual scheduler tests on GitHub; verification branch only, no tag, publish or default-branch merge |
| Python | >=3.10 | 3.9 unsupported; candidate matrix 3.10-3.14; native Windows results still missing |
| Indian 2027 data | UNSUPPORTED | No authoritative approved payload in this candidate |
| CDS | SUPPORTED within coverage | NSE INR pairs only, 09:00-17:00 IST and currency holidays; not BSE/cross-currency |

CALENDAR_CORRECTNESS: prior validated scope passes; all-platform release blocked
on current artifacts and Windows candidate evidence. AUTO_UPDATE_PRODUCTION:
BLOCKED independently of calendar tests. Correctness-only publication can be
considered after native package acceptance, with automatic installation disabled.

## User ownership

Existing 1.7.1 and older users need one manual bootstrap. Normal pip installs
no service and enrolls no managed runtime. Explicit setup creates a separate
controller/runtime and requires approved policy/bootstrap/wheel inputs. Original
pip and running applications are unchanged. Only explicitly selected managed
applications use its new runtime. Notification mode is the default; automatic
installation requires separate consent and release approval. Exact dependency
pins and protected AION deployment admission still apply.

## Verification-only CI

.github/workflows/verify-candidate.yml builds once and checks both artifacts on
native macOS/Linux/Windows Python 3.10-3.14. Its inventory is CI integrity evidence,
not production signing. Windows library/native-primitive scope is explicit;
POSIX lifecycle fixtures are not advertised as Windows tests. Task Scheduler and
Windows 11 lifecycle remain separate. No job publishes, signs or accesses secrets.
A runner label alone is not execution evidence. Native lifecycle jobs also exercise
the actual OS schedulers using disposable signed channels. A user-manager or
interactive-token refusal remains a failure/blocker, never a privileged fallback. Do not trigger publish.yml merely
to obtain tests. Historical v1.7.1 CI had successful Windows test jobs but its
publish job failed; that does not validate the new candidate or explain the
publication failure's root cause.

## Release decision

BLOCKED_WITH_EXACT_REMAINING_GATES. No owner has approved a production root or
operational signed channel. No public release, tag, default-branch merge, website deploy,
private model, trading, billing or customer environment change is permitted by
this record. Only the explicitly authorized verification branch/CI test is allowed. See RELEASE_NOTES_1_8_0.md and docs/UPDATE_CONTRACT.md.

## Native execution checkpoint

Verification branch ci/calendar-1.8-acceptance has actually run. Initial native
Linux scheduling passed; native failures are retained and repaired on the same
review branch. All-platform acceptance is not yet complete. See the provider
run results and current private handoff before interpreting this checkpoint.
This does not activate production signing, publication or customer updates.
