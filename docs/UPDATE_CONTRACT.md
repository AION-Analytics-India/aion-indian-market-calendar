Current release gates: [RELEASE_STATUS.md](../RELEASE_STATUS.md). Unreleased candidate; production trust/channel not configured.

# Calendar-data refresh and managed software upgrades

Candidate contract, 1.8.0. Neither mechanism installs itself in older clients.

## Data lifecycle

The calendar store reads the approved public calendar-data origin. An operator
can explicitly configure another origin using AION_IN_CALENDAR_URL. HTTPS is
required, redirects are refused, transfer reads have a 10-second wall-clock
budget with a 5-second socket timeout, each resource is at most 2 MiB, and a
manifest lists at most 16 payloads. The timeout applies per resource and is
not a real-time SLA. No cookies, auth or installation identifier is sent.

Schema 1, filenames, hashes, year inventory, UTC revision metadata, review date,
optional minimum-client version and the actual event/session payload must pass
validation. Every file verifies before any data is adopted. A private staging
directory, serialized final version check and atomic ACTIVE rename expose a
complete generation. Older data cannot downgrade a newer bundle. Equal-revision
hash changes are rejected. Validated earlier generations remain available.
The trusted origin plus SHA-256 provides integrity, not a digital signature.

A failed refresh retains a validated cache or bundle. If nothing verifies,
session construction refuses; it does not load an unverified bundle or invent
weekday-only status. A stale-data status is distinct from coverage: covered
historical calculations remain possible while unverified future dates refuse.
Check `store.status()` for freshness, coverage and `review_due`.

Set AION_IN_CALENDAR_OFFLINE=1 before use to prohibit refresh/discovery/RSS
network requests. Offline can select already-verified cached data. Import does
not install a background service. Online first load may check the data, with a
24-hour throttle; loaded readers synchronize at bounded intervals. Explicit
force bypasses the time throttle, never integrity, offline or schema rules.
An abandoned .adoption.lock is not stolen automatically: the operator verifies
that no writer remains before recovering that cache. Bundle fallback remains.

The current candidate supports only 2026-01-01 through 2026-12-25. Its review
reminder is 2026-10-01 and is overdue. The maintenance tool chooses the earlier
of October 1 in the final covered year and 30 days before coverage expiration.
An overdue reminder does not shift to a later year just because a manifest is
regenerated. No 2027 holiday calendar is synthesized.

## Approved software discovery

`software_updates.discover` is explicit and never called by calendar functions.
It requires `network_authorized=True`, online policy, an approved HTTPS URL and
the expected SHA-256 of the entire approval manifest, delivered through a
separate trusted deployment-control channel. It does not trust arbitrary PyPI
latest, an adjacent checksum, a redirect or a mutable package index as approval.
The returned installed/available versions distinguish discovery from adoption.
Only stable x.y.z versions are accepted by this initial contract.

Approval schema 1 has these fields:

```json
{
  "schema_version": 1,
  "project": "aion-indian-market-calendar",
  "approval_id": "deployment-owner-change-reference",
  "approved": true,
  "version": "1.8.0",
  "artifacts": [
    {
      "filename": "aion_indian_market_calendar-1.8.0-py3-none-any.whl",
      "sha256": "REPLACE_WITH_VERIFIED_64_HEX_DIGEST",
      "size": 12345
    }
  ]
}
```

This is a template, not an approved release manifest. Include exact size and
SHA-256 for the calendar wheel and every dependency wheel. At most 16 wheels,
32 MiB each. A deployment owner pins the complete closure and Python runtime.
Do not authorize arbitrary uploaded manifests based on their own hash alone.

## Low-level operator controller

The separate `managed_updater` module provides a CLI and Python controller.
It is not imported by normal APIs and has no automatically installed schedule.
The deployment supervisor, not the library, chooses when to poll and upgrade.

1. Discover and approve the release through the independent control channel.
2. Place the verified approved wheels in a dedicated local wheelhouse.
3. Explicitly invoke the supervisor with its deployment-owned managed root:

```bash
python -m aion_indian_market_calendar.managed_updater upgrade \
  --root /deployment-owned/calendar-envs --allow-environment-changes \
  --manifest approved-release.json --approved-sha256 APPROVED_MANIFEST_SHA256 \
  --wheelhouse /deployment-owned/approved-wheels
```

4. The controller serializes updates, validates/copies immutable artifacts into
   a new environment, runs venv/ensurepip locally, installs with --no-index and
   --no-deps, runs fixed offline compatibility checks and pip check, records
   acceptance, and atomically promotes CURRENT.json. It does not modify a
   caller's existing interpreter. Failed installation/tests leave the active
   pointer unchanged. No subprocess runs shell text from a manifest.
5. Consumers resolve `ManagedUpdater.active_python()` at their independently
   approved launch. Updating a pointer does not change already-running Python
   processes, restart services or select a trading maintenance window.
6. Explicit rollback tests the previous accepted environment before atomically
   restoring its pointer:

```bash
python -m aion_indian_market_calendar.managed_updater rollback \
  --root /deployment-owned/calendar-envs --allow-environment-changes
```

`status --root ...` is read-only. CURRENT.json is authoritative after a crash;
ACCEPTED.json records candidates that passed. Interrupted staging is never
active. Protocol-2 updates use a kernel advisory guard inherited by installer
children. A killed supervisor cannot admit a competing installer while a child
still holds the guard. After all holders exit, the next operation recovers its
marker automatically. Unknown legacy locks require owner review. Failed staged
environments are not deleted automatically. Keep disk monitoring/retention in
the supervisor's policy. A crash immediately after pointer promotion may lack
its success log; reconcile CURRENT.json and its attempt before retrying.

Receipts record timestamps, version, attempt/approval identity and success,
failure type or rollback. No user identifier, credentials, host identity,
article data or environment dump is collected. Local absolute paths are not
included in upgrade receipts. No network is needed for installation or smoke
checks. The runtime and approved artifacts must themselves be trusted.

For an existing disposable 1.7.1 deployment, bootstrap the managed root using
an explicitly approved 1.7.1 wheel closure, then upgrade to the approved newer
candidate. This is adoption of a separate supervisor; old 1.7.1 code did not
magically gain the updater. External PyPI users may explicitly adopt the persistent lifecycle below or
choose their own authorized package-management/deployment automation. Universal silent Python upgrades
are not a capability of this package.

## Independent release units

The 1.8.0 code/bundled-data candidate and shared-data publication are separate.
Do not replace the legacy shared /in feed merely because the new client passes:
old clients do not enforce new minimum-client declarations and can mishandle
new special-session semantics. Publish shared data only after legacy-client
compatibility or an approved versioned-origin transition is established.
Publication, tagging and production deployment require separate approval.

## Scheduled notices and approved automatic upgrades

The optional `[updates]` dependency adds Ed25519 signature verification. A
separate supervisor can run `automatic_updates check` or `watch` after explicit
device-owner opt-in. Neither runs during import/calendar calls. The watcher
polls at the operator-selected 60..86400-second interval. Default mode emits
`update_available`/`up_to_date` JSON and local receipts only. `--install-approved`
separately enables the tested download/install/check/promote cycle.

The managed root must first adopt an accepted existing deployment using the
manual supervisor. Then one pinned release public key authenticates later
approved patches without a new per-device checksum for each release. The
release authority signs a base64 envelope with algorithm Ed25519; the signed
payload is the approval schema above plus `channel`, monotonic `sequence`,
`issued_at`, `expires_at`, and an HTTPS `url` for each artifact. The device's
local policy pins the public key, channel URL/name, artifact-host allowlist and
poll interval. The policy is installed through an independent trusted channel.
Expired/future signatures, wrong keys, unapproved releases, channel rollback,
changed same-sequence payloads, changed channels, redirects and disallowed
artifact hosts refuse. A superseded in-flight download cannot be promoted.

```bash
python -m pip install "aion-indian-market-calendar[updates]"
python -m aion_indian_market_calendar.automatic_updates watch \
  --root /deployment-owned/calendar-envs --policy owner-approved-policy.json \
  --enable-software-checks
# Add --install-approved only when the owner authorizes environment promotion.
```

This command is a template, not an installed service. The deployment supervisor
owns scheduling, interruption, application-specific checks and separately
approved consumer restart/relaunch. An environment pointer update does not
replace code already loaded by a running Python process. These low-level commands register no OS service or cron task. Explicit
customer setup is provided by the persistent lifecycle below. No production
key or release channel is bundled.
Tests generate a signing key only in memory. Production key ownership, secure
CI signing and the actual channel publication remain owner-controlled release
activation decisions. Never accept a replacement public key from an unsigned
channel or embed a signing private key in a distributed package.

Earlier packages have no upgrade-notice code. Anonymous PyPI downloads do not
provide an addressable device/customer list. Announce the release through
approved GitHub Releases, website notes and opted-in communication channels;
users upgrade once to obtain new functionality. Existing 1.7.1 cannot receive
a checker retroactively. External users may configure their own authorized
package automation; universal silent upgrades are never claimed.


## Persistent managed lifecycle (staged, not production activated)

`update_lifecycle setup` is the explicit customer onboarding boundary. It
requires `--consent`, optional `--enable-auto-install`, a new writable root,
an independently approved bootstrap manifest/closure and an authenticated
schema-2 policy. It reads the installed calendar/pytz/tzdata versions, displays
the original environment and managed destination, and never overwrites the
original environment. Supported Python installations must provide venv and
ensurepip. No system package manager or sudo command is run to repair a host.

The immutable bootstrap environment is the controller. The separate runtime
contains only the calendar, pytz and tzdata. Accepted future releases install
into new versioned environments and atomically change the runtime pointer.
Applications must use `update_lifecycle run --root ROOT -- PYTHON_ARGUMENTS` to
select it; other pip environments and already-running applications do not
change. The controller itself is pinned for this rollout; upgrading its code
requires a separate reviewed bootstrap/controller release.

### Supervision and controls

macOS registers an owned LaunchAgent with RunAtLoad and StartInterval. Linux
registers an owned user service/timer with control-group termination, bounded
startup duration, CPU quota and memory budget. A job name is a local hash of
its dedicated root, not a network tracking identifier. Installation refuses
existing unrelated files; changes/uninstall require the recorded file hashes. `status`
reads actual OS state, including after an incomplete uninstall, rather than
claiming success from a local state flag.

- `start --consent` explicitly enables/resumes the owned schedule.
- `stop` stops the current schedule and active owned operation.
- `disable` removes persistent activation and prevents manual check from
  installing or accessing the update channel until explicitly re-enabled.
- `uninstall` disables and removes only the owned supervisor files/links. It
  retains managed versions and receipts, and does not delete application data.
- `offline` persists offline mode and stops the job. No network/installation is
  performed. Return to online operation requires a newly reviewed setup; there
  is no implicit online fallback.
- `rollback` stops the schedule, validates a still-authorized previous version
  and its health, then restores its pointer. It does not restart supervision;
  explicit owner consent is required to resume.

User jobs resume after login/user-manager startup. Linux boot-before-login
requires pre-existing authorized lingering; setup reads but never changes it.
Tests simulate manager stop/start, not a physical reboot. The new Windows
Task Scheduler adapter passed the real signed scheduled-update/recovery/teardown
lifecycle on Windows Server 2022 x64, Python 3.10-3.14. Actual Windows 11 normal-user
and physical reboot acceptance remain unverified. It is not approved for customer
automatic installation. Library portability and synthetic trust tests do not
establish a production update service.

### Compatibility, workload and crash boundaries

The owner chooses one major/minor series; only newer stable patch versions in
that series are eligible. Signed Python compatibility and wheel metadata must
match. Runtime dependencies remain pinned to the exact adopted pytz/tzdata
versions. Optional `--constraints FILE` accepts explicit constraints for these
owned packages and the calendar only; unrelated requirements, URLs, markers or
extras refuse instead of being silently ignored. A calendar==1.8.0 pin blocks
all later patches. A dependency change needs separately approved onboarding.
No arbitrary consumer dependency graph is promised compatible by package smoke.

`run` holds a shared workload lease inherited by its child; upgrades/rollback
need the exclusive lease. A live managed application therefore defers updates.
AION-protected policy additionally requires `--admission PATH` and
`--admission-sha256 HASH`: the independently approved deployment controller
must return success on `--check ROOT` before changes. A changed, missing,
failed or timed-out controller fails closed. This interface is not authorization
to change an AION trading workload and has not been deployed into one.

Updater children inherit the update guard. A kill leaves accepted versions
intact and failed staging preserved. Once the entire operation exits, the next
scheduled tick can recover the marker and stage afresh. It never promotes an
unaccepted staging directory. Rollback is explicit; failed health/installation
never changes the accepted pointer. Disk retention remains owner-controlled.

### Schema-2 trust and distribution

Owner-provisioned policy requires: schema_version=2, channel=stable,
root_public_key_hex, compatible_series=[MAJOR,MINOR], poll_seconds=60..86400,
credential-free HTTPS trust_url/channel_url, allowed_artifact_hosts, and
explicit deployment=customer-managed or aion-protected. Optional tls_ca_file is
an explicitly trusted public CA, never a TLS-verification bypass.

The pinned root signs expiring keyring metadata: project/channel,
trust_version, issued_at/expires_at, release_keys keyed by ID,
revoked_key_ids and revoked_versions. Clients reject version rollback,
same-version replacement and removal of prior revocations. A newer root-signed
keyring rotates/revokes release keys. Root replacement remains a separate
out-of-band owner operation; a channel cannot replace its own trust root.

Release envelopes identify key_id and use Ed25519. Payloads retain approval
schema 1 and add channel, sequence, issued_at/expires_at, compatibility_series,
requires_python and HTTPS URLs for exact hash/size-pinned artifacts. Only the
calendar/pytz/tzdata runtime closure may be installed. Wrong signatures,
revoked/unknown keys or versions, expired/future metadata, incompatible Python
or patch series, downgrade/replay, redirects, disallowed hosts and changed
artifacts fail closed. Installer commands never come from release metadata.

Production release owner must separately establish offline-root custody,
release-signing custody, independent trust distribution, HTTPS availability,
version/sequence issuance, expiry renewal, incident revocation and artifact
publication. No live identity/channel is invented or provisioned by this
candidate. Synthetic keys prove implementation only. Normal PyPI upload alone
is not managed-channel publication.

### Independent acceptance gates

CALENDAR_1_8_CORRECTNESS_RELEASE_READY and AUTO_UPDATE_PRODUCTION_READY are
separate decisions. Passing calendar cases or disposable signed-service tests
cannot establish production trust availability. Public documentation may say
only what the approved gate and supported platform scope establish. No public
release or production deployment is authorized by a local test result.


### Offline publisher tooling and operational gate

`scripts/sign_software_channel.py trust|release` validates the public document
and signs it with an explicitly approved Ed25519 private-key descriptor >=3.
Arguments include --document, --output, --key-id, --private-key-fd and
--approve-signing. The approved signing controller owns that descriptor.
Private bytes are never passed in arguments or printed; tests use RAM pipes.
The command refuses existing output files and performs no network publication.

Before publication the release owner must verify the signing key against the
independently distributed trust root/keyring, compare previous trust/release
versions and revocations, publish immutable artifacts and signed metadata in
controlled order, and perform public availability/hash/signature readback.
The local signer does not establish production identity, custody, CI approval
or release-channel availability. Those are still mandatory production gates.


## Windows adapter (native CI tested, production release held)

The existing controller/state/trust machine is retained. Task Scheduler receives
an owned root-hashed task using InteractiveToken/LeastPrivilege. Enrollment
refuses service accounts and session 0; it never falls back to S4U, SYSTEM,
stored passwords or elevation. Tasks start at logon and repeat while the user is
signed in. Logged-out networking is not promised. Registration is create-only;
existing tasks are never overwritten. A matching setup contract returns actual
status without mutation or re-enablement. Changed or legacy setup contracts
refuse. Windows stores hash-owned registration intent before the provider call,
so interrupted setup can be reconciled and uninstalled. Idempotent uninstall
rechecks the provider and retains accepted environments/evidence.

Windows controller identity is an owned CONTROLLER.json reference to an accepted
bootstrap environment; no symlink privilege is needed. Reparse paths refuse.
Owner/DACL validation excludes untrusted writers. Shared/exclusive kernel file
handles replace POSIX flock, with explicit child handle inheritance. Dedicated
CLI workers use a kill-on-close Job Object so stopping that worker also ends its
own installer descendants; no unrelated process is assigned. Native CI exercised
ACLs, process-tree/lease behavior, scheduler error semantics and transient NTFS
contention. This does not prove every consumer antivirus/filesystem configuration.
Failure of any boundary must refuse rather than weaken it.

Windows tests/CI must distinguish calendar correctness, native primitives,
scheduler lifecycle and Windows 11 reboot/logon. No macOS test certifies these.
The test-only production signing identity is never inferred from fixture keys.
The production root custodian/fingerprint, signed bootstrap onboarding and live
channel are still owner decisions. Ordinary pip installation has no schedule.

Availability notifications are local machine-readable receipts/output, not
email, desktop toasts or push messages. Normal pip installs no schedule. The
immutable supervisor/controller is not automatically replaced by runtime patch
promotion; its security/code changes require a separate reviewed bootstrap.
Managed run uses the fixed offline runtime environment; setting a library
process offline does not unregister an independently opted-in OS job. Use the
lifecycle offline command to persist offline policy and stop that schedule.
