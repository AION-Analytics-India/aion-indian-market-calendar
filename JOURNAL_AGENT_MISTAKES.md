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
