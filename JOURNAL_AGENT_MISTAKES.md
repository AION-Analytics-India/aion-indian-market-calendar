# Agent mistakes and corrections

## 2026-11-14

- An initial isolated test run used the changed bundle as the historical
  November 3 remote fixture. The tests correctly failed. Preserved all their
  original assertions and added a byte-exact historical fixture from the base
  commit. This is not a replacement of primary acceptance inputs.
- An initial change made the legacy market-open close edge half-open. Existing
  commodity tests caught the compatibility change. Restored the activity
  envelope; continuous matching uses half-open phase semantics explicitly.
- One CLI append command used the data worktree as cwd and failed before
  creating a source file. Reissued against the correct source worktree. No
  production path or service was affected.

Follow-up: a second combined command used the wrong worktree for its initial edit and failed before writing. Subsequent multi-repository edits use absolute paths and an explicit repository identity check.


## 2026-11-14T13:48:34.545348+00:00 | Managed update lifecycle candidate

Initial new lifecycle fixture chose the first cffi wheel rather than a matching interpreter tag. Bootstrap correctly failed before OS registration. Fixture now selects packaging.tags-compatible wheels. Initial source suite driver omitted pytz and two fallback cases failed; installing the declared dependency into the disposable driver restored the complete source suite. No assertions were relaxed. New update_supervision.py lock was claimed late; all other source edits retained scoped ownership, and the late claim is recorded rather than represented as pre-edit protection.


## 2026-11-14T14:02:22.419498+00:00 | Final lifecycle evidence and offline publisher boundary

An installed-artifact harness initially copied only tests out of the sdist, omitting required data/source-inspection context. The resulting missing-fixture errors were excluded. Reran the complete extracted sdist under isolated imports, explicitly proving site-packages execution; all274 passed for both distributions. No fixture or assertion was weakened.


## 2026-11-14T15:13:47.699043+00:00 | Three-platform review candidate

The prior tutorial contained an invalid pip command ending in the bare word candidate and called the unpublished candidate a PyPI release. Corrected it to a reviewed local-wheel command and explicit unpublished state. Prior contributor instructions referenced a nonexistent dev extra; corrected to test/updates. Historical Windows jobs for 1.7.1 were initially discussed alongside candidate acceptance; the founder queried this distinction, and the current status explicitly records that 1.8 Windows has not run yet. Do not claim those historical jobs validate this candidate. An initial lock-claim helper refused an already-owned lock before editing; changed it to verify the same session instead of assuming the path must be absent. No other agent lock was removed.

Two combined documentation/test commands used the marketing root for the test phase; pytest refused missing source test paths before collection. The explicitly scoped corrected command uses the explicit Calendar worktree and passes all 68 focused cases. This failed invocation is not counted as a package test failure or a passing run.


## 2026-11-14T15:23:13.451890+00:00 | Native CI corrections

Selected macos-14 without checking current runner retirement; provider cancelled those jobs before execution. Official runner-images states retirement on 2 November. Corrected to macos-15. Initial native adapter test hardcoded POSIX separators; corrected expected native Path serialization without weakening action identity. run_child accepted run-style capture_output but forwarded it to Popen; implemented explicit PIPE translation. Reduced Windows fixture environments and EOF-based PowerShell input timed out; use bounded JSON lines plus required non-secret OS profile variables. These are retained failed native results, not passing runs.


## 2026-11-14T15:31:39.216747+00:00 | Native acceptance round three

The first pointer-lock test tried to reopen a file while intentionally denying every other handle, causing an expected sharing violation before checking preserved state; moved the unchanged state assertion after unlock. A SslStream fixture with EphemeralKeySet initialized but could not serve TLS in native Windows; initialization was not proof of a successful handshake. Replaced only the fixture, never client validation or trust. A local TLS teardown race dereferenced a concurrently cleared client attribute; use a captured socket reference, then trusted/untrusted handshake and teardown passed. Installing pyOpenSSL alone initially upgraded the disposable driver cryptography beyond the candidate range; restored the original 46.0.7 and solved the joint constraints, pinning the test helper to pyOpenSSL <26.3. No production environment was touched.


## 2026-11-14T15:38:16.653807+00:00 | Scheduler acceptance closure

The Windows ACL helper remained blocked despite one-line stdin and SID enumeration; those changes were not claimed as verified fixes. Native lease/tree primitives passed. The test-only native bridge now avoids Console.In under pytest/redirected runners, carrying only explicitly allowed non-secret metadata. A 110-second scheduler observation deadline stopped a still-in-progress Mac upgrade; changed the test observation budget with the polling/worker envelope documented, rather than relaxing the required installed-version or teardown outcome. The first artifact upload included disposable environments; later uploads are restricted to receipts/logs and the local investigation extracted only necessary files.


## 2026-11-14T15:43:41.301220+00:00 | Native module boundary

Console-input removal did not resolve the native timeout and is not recorded as a confirmed root cause. The retained failed results show the reduced-environment boundary still blocked. Further correction removes dependency on lazy PowerShell cmdlet/module discovery; native execution must decide its result. Do not infer a completed Windows lifecycle from any partial step.


## 2026-11-14T15:49:14.598288+00:00 | Terminal receipt and native diagnostics

The scheduler harness treated a promoted CURRENT pointer as terminal completion. On hosted Mac, the update had succeeded but its worker had not released the exclusive workload lease, so the next application run was correctly denied. Wait for the actual terminal supervisor receipt before launching; preserve the original failure and safety guard. Generic Windows native exceptions hid the registration stage/HRESULT; add bounded non-sensitive diagnostics instead of guessing or changing task permissions.


## 2026-11-14T15:53:59.157672+00:00 | Native task XML gate

Portable XML parsing did not prove Task Scheduler acceptance. Native service rejected the serialized task as malformed. Added native validate-only before registration and removed byte encoding from the Unicode COM transport; native execution must confirm this correction. No privilege, principal, security descriptor or consent rule changed.


## 2026-11-14T16:05:58.344917+00:00 | Provider identity and NTFS contention

Exact serialized-principal text is not an account ownership invariant: the native service may normalize SID to account name. Resolve to SID before comparison; never accept a short-name match. A Windows refresh race surfaced after other platform runs passed; FileExistsError alone did not cover native delete-pending errors. Added bounded native-error retries and deterministic boundary regressions, without widening permissions or changing the original concurrency fixture.


## 2026-11-14T16:15:07.586953+00:00 | Durable enrollment ownership

Failed native registration exposed an incomplete setup checkpoint: task intent was written only after provider success, so ambiguous creation could not be reconciled through normal teardown. Moved durable intent before mutation and added an actual native kill/recovery test. Historical failures remain retained. No task ownership check was bypassed. Earlier -m your_application quick-start presupposed an application/dependency installation not provided by the calendar-only runtime; replaced with the actual tested inline version command.


## 2026-11-14T16:23:49.108845+00:00 | Native fixture closure

The Python3.10 bootstrap fixture hardcoded a controller closure without typing_extensions. Native pip check correctly failed; supplied the actual required wheel instead of disabling dependency verification. The new partial-setup test referenced sys.argv[1] after deleting its marker argument, so it wrote the wrong file and did not inject the intended crash. Captured the immutable marker path before argument mutation. Neither failed run is counted as successful partial-setup evidence.


## 2026-11-14T16:34:33.180769+00:00 | Native readback and release limits

Earlier active status copy still said Windows was not natively tested after its actual checks passed. Corrected the current authority, retaining dated failed attempts and distinguishing native Server2022 from Windows11/reboot and production trust. Artifact retrieval first treated structured file_uri metadata as a URL; corrected its download_url field, with no URL/key logged or committed. A source-root read used a marketing-relative handoff path; corrected scope, no file changed.


## 2026-11-14T16:35:41.515354+00:00 | Final native provider readback

No new implementation failure in final run. Earlier failed attempts remain historical. Do not count later documentation commit bytes as the already built855e817 artifacts; record both source identities explicitly. Do not infer real reboot, Windows11 or production trust from the successful native CI.


## 2026-11-14T17:01:49.256271+00:00 | Final correctness release preparation

Earlier current CHANGELOG text still called Windows native acceptance untested after the23-job pass; corrected current entry and explicitly labelled old entries historical. Prior1.7.1publisher log confirms400 File already exists, not an assumed credential failure; prevent duplicate/rebuilt uploads. Local exploratory glob with no match and API response parse assumption failed safely, no provider mutation. Published1.7.1 alone has reproduced defects; do not generalize affected/yank range.


## 2026-11-14T17:10:35.695301+00:00 | Final source consistency

Initial final-artifact freeze occurred before checking AGENTS release policy and tutorial current-state claims. Those two obsolete instructions were found in final review. Corrected and rebuilt; never reuse the preceding hashes or hide that superseded candidate. Do not infer missing files from a chained-command failure.
