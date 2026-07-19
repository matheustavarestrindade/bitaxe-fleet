# Bitaxe Fleet Implementation Plan

## Purpose

This file is the execution ledger for implementing Bitaxe Fleet. It is written
for a delegated implementation agent and intentionally breaks work into small,
verifiable phases.

Read [PROJECT.md](PROJECT.md) before changing code. That document defines the
architecture, safety invariants, allowlists, and contracts. Read
[README.md](README.md) for the intended user experience and
[CHANGELOG.md](CHANGELOG.md) before recording user-visible changes.

## Current Status

- Project state: `v0.6.3` includes fleet aggregate entities, compact panel
  formatting, session-best difficulty coverage, and auto-registered Recorder-
  backed graph and fleet performance dashboard cards.
- Published release: `v0.6.3` provides private-IPv4 enrollment, discovery,
  controls, recovery, expanded monitoring, Recorder-backed history, and fleet
  aggregates.
- Current development scope: typed AxeOS capabilities/logs/mutations,
  approval-based mDNS and bounded scanning, profiles, controls, incidents,
  diagnostics, expanded native telemetry/health entities, fleet aggregates,
  Recorder-backed history graphs, the panel, and opt-in automatic responsive
  recovery are implemented.
- Remaining release-readiness work: real-device validation, optional external
  pool support, and the scenario coverage explicitly retained in later phases
  below.
- Documentation phase: updated to distinguish implemented behavior from the
  remaining roadmap.

## Manual Onboarding Milestone

This legacy scoped milestone remains complete and verified. The candidate now
also completes the typed AxeOS boundary needed for discovery, controls, and
recovery; real-device compatibility evidence remains a release-readiness task.

- [x] Validate an administrator-submitted RFC 1918 IPv4 host through bounded,
  redirect-free `GET /api/system/info` requests.
- [x] Normalize `macAddr`, persist approved miner endpoint and metadata through
  Home Assistant `Store`, and preserve one record when the same MAC is submitted
  at a new address.
- [x] Create one per-miner coordinator, device, expanded native telemetry/health
  entities, and Recorder-backed history graphs from validated snapshots.
- [x] Add synthetic AxeOS fixtures and parser, HTTP, storage, options-flow,
  lifecycle, and entity tests.
- [x] Add typed `/api/system/asic`, logs, and mutation support with synthetic
  valid, partial, and malformed compatibility fixtures.
- [ ] Validate the supported behavior against anonymized real-device fixtures
  and hardware before declaring firmware compatibility complete.

## Status Rules

- `[ ]` means not complete.
- `[x]` means implemented, reviewed, and verified by the named gate.
- Do not mark a parent phase complete while any required item is unchecked.
- Do not mark tests complete because test files exist; run them successfully.
- Record intentional deferrals in the phase notes instead of checking them.
- Add discovered work to the correct phase before beginning it.
- Keep only one implementation phase active at a time.
- Update `CHANGELOG.md` under `Unreleased` with user-visible changes.
- Never bypass a `PROJECT.md` safety invariant to finish a checkbox.

## Agent Work Protocol

For each work session:

1. Read all four top-level Markdown documents.
2. Inspect the current worktree without reverting unrelated changes.
3. Select the earliest unblocked unchecked task group.
4. State the narrow task and verification plan.
5. Implement the smallest correct change.
6. Add or update tests in the same change.
7. Run the narrow tests, then the applicable phase gate.
8. Inspect the resulting diff for secrets, generated noise, and scope creep.
9. Update this file only for work that actually passed verification.
10. Update project decisions and changelog when applicable.

## Global Definition Of Done

A task is complete only when all applicable statements are true:

- Behavior matches `PROJECT.md`.
- Public and persisted types are explicit.
- Untrusted input is validated before domain use.
- Safety and authorization are enforced server-side.
- The happy path, failure path, and important boundary cases are tested.
- Async tasks, locks, sessions, and listeners are cleaned up.
- No credentials, raw payloads, MAC addresses, or IP addresses leak into logs or
  diagnostics.
- Python format, lint, typing, and tests pass.
- TypeScript lint, typing, tests, and production build pass when frontend code
  is affected.
- Home Assistant and HACS validation pass when integration metadata is affected.
- User-visible behavior is documented under `CHANGELOG.md` `Unreleased`.
- Relevant README and project specification text remains accurate.

## Required Full Verification

The exact command wrappers may be added during Phase 1. The final project must
provide reproducible equivalents of:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy custom_components tests
python -m pytest
npm ci --prefix frontend
npm run --prefix frontend lint
npm run --prefix frontend typecheck
npm run --prefix frontend test
npm run --prefix frontend build
```

Home Assistant integration validation, HACS validation, archive validation, and
Markdown/link checks must also run in CI.

## Phase 0: Documentation And Decisions

### Research And Scope

- [x] Inspect the reference static dashboard and identify useful metrics and
  Satoshi Radio behavior.
- [x] Inspect official ESP-Miner OpenAPI documentation and current firmware
  implementation.
- [x] Confirm direct HACS architecture with Python backend and compiled
  TypeScript panel.
- [x] Confirm `Bitaxe Fleet` as the product name.
- [x] Confirm `bitaxe_fleet` as the permanent Home Assistant domain.
- [x] Confirm normalized `macAddr` as permanent identity and IP as mutable.
- [x] Confirm unknown miners require administrator approval.
- [x] Confirm API-only recovery for the initial release.
- [x] Confirm the exact six-field recovery profile.
- [x] Confirm `manualFanSpeed` is never restored or patched.
- [x] Confirm safe overheat handling is the default.
- [x] Confirm optional, isolated Satoshi Radio support remains in scope.
- [x] Confirm Conventional Commits, SemVer, `master`, and HACS ZIP releases.

### Documentation Scaffold

- [x] Create `README.md` with user-facing scope and safety limitations.
- [x] Create `PROJECT.md` with architecture and implementation contracts.
- [x] Create `TODO.md` with phased tasks and verification gates.
- [x] Create `CHANGELOG.md` using Keep a Changelog and SemVer conventions.
- [x] Verify all four documents agree on names, endpoints, recovery fields,
  release branch, and project status.
- [x] Verify every relative Markdown link resolves.
- [x] Verify no document claims an installable release exists.

### Decision Dependencies

These decisions do not block the documentation gate. Resolve each one before
the named implementation gate instead of guessing it in unrelated work.

| Decision | Due before |
| --- | --- |
| Open-source license | First public release |
| Initial firmware/model compatibility statement | Phase 12 gate |
| Poll and HTTP timeout defaults | Phase 5 gate |
| Active-scan safety limits | Phase 4 gate |
| Recovery timing and attempt defaults | Phase 7 gate |
| Incident and log retention defaults | Phase 8 gate |
| Semantic release tool | Phase 11 gate |

### Phase 0 Gate

- [x] Documentation consistency verification passes.
- [x] No application files, dependencies, or workflows exist unless the owner
  has explicitly started implementation.
- [x] Every unresolved decision is either non-blocking for Phase 1 or assigned
  to a specific later phase.

## Phase 1: Minimal Repository And Tooling Scaffold

### Repository Metadata

- [x] Initialize Git on `master` and configure the supplied `origin` remote.
- [x] Select the MIT License for public distribution.
- [x] Add the MIT `LICENSE`.
- [x] Add `.gitignore` for Python, Node, editors, coverage, build output, and
  local Home Assistant state.
- [x] Add canonical repository URLs after the remote is known.
- [x] Add `hacs.json` with integration category and planned ZIP-release fields.
- [x] Add minimal project metadata with the unreleased `0.1.0` integration
  version.

### Python Toolchain

- [x] Add `pyproject.toml` with exact direct development dependency versions.
- [x] Configure Ruff formatting and lint rules.
- [x] Configure `mypy --strict` for integration-owned code.
- [x] Configure Pytest and Home Assistant custom-component test support.
- [x] Add reusable typed fixtures for Home Assistant setup.
- [x] Document local Python setup commands.

### Minimal Home Assistant Integration

- [x] Add `custom_components/bitaxe_fleet/manifest.json` with a valid minimum
  Home Assistant version and no invented upstream URLs.
- [x] Add package `__init__.py` with typed config-entry setup and unload.
- [x] Add `const.py` with the permanent domain and named constants.
- [x] Define a typed config-entry alias and typed `runtime_data` container.
- [x] Add a minimal singleton config flow with translations.
- [x] Confirm setup/reload/unload creates no leaked tasks or listeners.
- [x] Confirm a second config entry aborts with a translated reason.

### Frontend Toolchain

- [x] Add the minimal `frontend` package and locked npm dependency tree.
- [x] Configure strict TypeScript, `noUncheckedIndexedAccess`, and
  `exactOptionalPropertyTypes`.
- [x] Configure frontend lint, tests, and a deterministic production build.
- [x] Produce a placeholder panel bundle only in build output; do not advertise
  an operational fleet panel yet.
- [x] Document local frontend setup commands.

### Development Container

- [x] Add a pinned Python `3.14.2` and Node.js `24.13.0` Dev Container.
- [x] Configure Dev Container dependency installation and editor tooling.
- [x] Build the container locally and verify the Python and Node.js versions.
- [x] Run Python validation inside the container.

### Initial CI

- [x] Add a validation workflow for Python format, lint, typing, and tests.
- [x] Add frontend install, lint, typecheck, tests, and build jobs.
- [x] Add Home Assistant and HACS validation jobs.
- [x] Pin third-party actions to immutable commit SHAs.
- [x] Use minimal workflow permissions and concurrency cancellation.

### Phase 1 Tests

- [x] Config flow creates one entry.
- [x] Duplicate config flow aborts.
- [x] Config entry sets up and unloads.
- [x] Unload removes all runtime resources.
- [x] Frontend placeholder compiles with strict settings.

### Phase 1 Gate

- [x] Full local verification passes, including metadata and Markdown validation.
- [x] CI passes from a clean checkout.
- [x] Home Assistant starts with the empty fleet integration loaded.
- [x] No miner network request occurs yet.

## Phase 2: Typed AxeOS Boundary

### Captured API Evidence

- [ ] Add anonymized `/api/system/info` fixtures for each initial firmware/model
  shape.
- [ ] Add anonymized `/api/system/asic` fixtures.
- [ ] Add anonymized `/api/system/logs` fixtures.
- [ ] Add malformed, partial, and known field-variant fixtures.
- [ ] Document fixture origin, firmware version, model, and redaction review.
- [ ] Confirm fixtures contain no real device MAC, IP, SSID, wallet, pool
  credential, or other household identifier; use synthetic identity values.

### Wire And Domain Models

- [ ] Add `axeos/wire.py` with `TypedDict` response shapes.
- [ ] Add `axeos/models.py` with frozen/slotted domain models.
- [ ] Add `MinerId = NewType("MinerId", str)`.
- [ ] Add endpoint, identity, telemetry, configuration, snapshot, capability,
  and log models.
- [ ] Represent absent optional data as `None`, never a fabricated zero.
- [ ] Keep all raw mappings out of domain models.

### Parsers

- [ ] Add explicit MAC normalization and validation.
- [ ] Validate top-level JSON mappings.
- [ ] Add finite numeric parsing with documented string variants.
- [ ] Add strict boolean parsing with documented numeric variants.
- [ ] Reject invalid ranges and negative counters where nonsensical.
- [ ] Add capability/field aliases only for fixture-proven firmware differences.
- [ ] Parse every fixture into immutable models.
- [ ] Return precise typed errors for required-field failures.

### Async Client

- [ ] Add typed transport errors from `PROJECT.md`.
- [ ] Use Home Assistant's asynchronous HTTP session.
- [ ] Bound connect/read timeouts and response sizes.
- [ ] Disable automatic HTTP redirect following.
- [ ] Implement `GET /api/system/info`.
- [ ] Implement `GET /api/system/asic`.
- [ ] Implement bounded `GET /api/system/logs`.
- [ ] Implement `PATCH /api/system` without automatic mutation retries.
- [ ] Implement restart, pause, resume, and identify POST methods without
  automatic mutation retries.
- [ ] Distinguish a definitely failed mutation from an uncertain outcome.
- [ ] Make client/clock behavior injectable.

### Phase 2 Tests

- [ ] Valid fixtures parse to expected domain models.
- [ ] Partial optional fields parse without fake values.
- [ ] Invalid identity rejects candidate validation.
- [ ] `NaN`, infinity, invalid booleans, and unsafe ranges are rejected.
- [ ] Timeout, connection, HTTP, malformed JSON, oversize, and redirect failures
  map to expected errors.
- [ ] Read retries are bounded and mutation methods are not automatically
  retried.
- [ ] Response and error representations do not leak body data.
- [ ] Strict Python typing passes without broad `Any`, unchecked casts, or
  unexplained ignores.

### Phase 2 Gate

- [ ] Every supported wire variant has a fixture and regression test.
- [ ] API models can represent all monitoring fields required by README.
- [ ] No Home Assistant entity or recovery behavior exists yet.

## Phase 3: Versioned Registry And Storage

### Storage Models

- [ ] Add explicit wire models for storage schema version 1.
- [ ] Add domain models for stored miner, endpoint, rejection, profile, policy,
  and incident references.
- [ ] Use Home Assistant's versioned `Store` helper.
- [ ] Define deterministic domain-to-storage serialization.
- [ ] Validate all loaded values before registry use.
- [ ] Bound incident and rejection storage.

### Miner Registry

- [ ] Index enrolled miners only by normalized `MinerId`.
- [ ] Add typed approve, reject, enable, disable, rename, and endpoint-update
  operations.
- [ ] Collapse duplicate observations by miner ID.
- [ ] Preserve one miner record when its endpoint changes.
- [ ] Prevent a different MAC at an old IP from taking over an existing record.
- [ ] Serialize writes and endpoint replacement.
- [ ] Debounce non-critical writes and flush critical profile/policy writes.

### Corruption And Migration

- [ ] Define behavior for unreadable store data.
- [ ] Preserve a recoverable backup/quarantine path through Home Assistant
  conventions where possible.
- [ ] Report invalid individual records without exposing their contents.
- [ ] Add an explicit sequential migration harness before a version 2 exists.
- [ ] Never add speculative backward-compatibility branches without persisted
  evidence.

### Phase 3 Tests

- [ ] Empty store creates valid schema version 1 state.
- [ ] Round-trip serialization preserves every allowed value.
- [ ] Unknown keys do not enter domain models.
- [ ] Invalid records are isolated according to documented behavior.
- [ ] Same MAC/new IP updates one record.
- [ ] Different MAC/same IP remains a distinct candidate.
- [ ] Concurrent updates do not lose profile or policy data.
- [ ] Stored data contains none of the prohibited settings or secrets.

### Phase 3 Gate

- [ ] Storage tests pass under strict typing.
- [ ] A Home Assistant restart preserves enrollment and endpoint metadata.
- [ ] No discovery source can enroll a miner without registry approval.

## Phase 4: Discovery And Enrollment

### Discovery Manager

- [ ] Add typed candidate and observation models.
- [ ] Add one manager that deduplicates all discovery sources.
- [ ] Validate candidates through read-only `/api/system/info`.
- [ ] Require a valid MAC and AxeOS-specific response structure.
- [ ] Keep pending, approved, rejected, and disabled states distinct.
- [ ] Expose scan status and pending candidates through application methods.

### mDNS

- [ ] Register `_axeos._sub._http._tcp` discovery through Home Assistant APIs.
- [ ] Normalize IPv4 endpoints and documented service ports.
- [ ] Handle update/removal callbacks without leaking listeners.
- [ ] Validate mDNS observations through AxeOS HTTP before presenting them.

### DHCP

- [ ] Gather real DHCP/hostname/manufacturer evidence for supported miners.
- [ ] Add only a defensible matcher that avoids unrelated devices.
- [ ] Omit broad DHCP manifest matching if evidence is insufficient.
- [ ] Validate every DHCP observation through AxeOS HTTP.

### Active Scan

- [ ] Implement strict private IPv4 CIDR validation and SSRF protection.
- [ ] Require administrator opt-in.
- [ ] Enforce tested CIDR size, concurrency, timeout, and interval limits.
- [ ] Prevent overlapping scans.
- [ ] Add jitter to periodic scheduling.
- [ ] Support cancellation on unload.
- [ ] Avoid warning-log floods for normal closed/unreachable hosts.
- [ ] Expose a manual `Scan now` operation.

### Approval Flow

- [ ] Show pending identity/model/firmware information without exposing unsafe
  raw fields.
- [ ] Require administrator approval for every unknown MAC.
- [ ] Persist rejection and allow later reconsideration.
- [ ] Start a coordinator and create devices only after approval.
- [ ] Update known endpoint automatically without duplicate enrollment.

### Phase 4 Tests

- [ ] mDNS, DHCP, scan, and manual observations deduplicate by MAC.
- [ ] False-positive HTTP JSON servers are rejected.
- [ ] Public, loopback, link-local, multicast, and oversized networks reject.
- [ ] Redirects to disallowed endpoints reject.
- [ ] Scan concurrency and cancellation limits hold.
- [ ] Unknown miners remain pending until approved.
- [ ] Rejected miners do not repeatedly prompt under configured behavior.
- [ ] Same MAC/new IP updates the existing registry and device identity.
- [ ] Different MAC at known IP never replaces the enrolled miner.

### Phase 4 Gate

- [ ] A real miner can be discovered and approved without entering a static IP.
- [ ] A known miner changing DHCP address remains one Home Assistant device.
- [ ] Discovery performs no mutation requests.

## Phase 5: Monitoring, Devices, And Entities

### Coordinators

- [ ] Add one typed coordinator per enrolled miner.
- [ ] Poll `/api/system/info` at the configured interval.
- [ ] Stagger initial and recurring fleet reads.
- [ ] Fetch/cache ASIC capabilities at enrollment and model/firmware change.
- [ ] Preserve the last snapshot while tracking freshness and availability.
- [ ] Treat optional field absence as unsupported, not update failure.
- [ ] Cleanly stop coordinator work on disable/unload.

### Home Assistant Devices

- [ ] Register one device per miner ID.
- [ ] Use current model, manufacturer, firmware, and safe configuration URL.
- [ ] Preserve device identity across endpoint changes.
- [ ] Update device metadata when validated firmware/model values change.

### Entity Descriptions

- [x] Inventory validated API fields and choose the smallest useful platform
  set.
- [x] Add sensor descriptions with correct units, classes, precision, and
  translation keys.
- [x] Add binary sensor descriptions for validated health/fault states.
- [ ] Keep noisy diagnostic entities disabled by default.
- [x] Do not create unsupported hardware-dependent values as zero.
- [x] Use stable unique IDs based on miner ID and entity key.
- [x] Verify recorder/statistics semantics for counters and measurements.

### Fleet Aggregates

- [x] Add typed aggregate calculations for fresh enabled miners.
- [x] Add total hashrate and power.
- [x] Add efficiency only with a positive valid denominator.
- [x] Add online, unhealthy, and overheat counts.
- [x] Expose partial-data coverage.
- [x] Recalculate without blocking or quadratic work.

### Phase 5 Tests

- [ ] Coordinator success, partial response, malformed response, timeout, and
  recovery behavior pass.
- [ ] Every entity uses the correct device and stable unique ID.
- [ ] Units, device classes, state classes, availability, and optional fields
  match fixtures.
- [ ] Endpoint changes do not duplicate devices/entities.
- [x] Aggregate math handles missing, zero, stale, and mixed data correctly.
- [ ] Setup/unload leaves no coordinator tasks.

### Phase 5 Gate

- [x] Approved miners provide trustworthy native Home Assistant monitoring.
- [x] Recorder history powers bounded panel charts.
- [ ] No mutating entity or automatic recovery exists yet.

## Phase 6: Profiles And Explicit Manual Controls

### Recovery Profile

- [ ] Add the exact six-field frozen/slotted `RecoveryProfile` model.
- [ ] Add model-aware frequency and voltage validation.
- [ ] Add conservative bounds for target temperature and minimum fan speed.
- [ ] Reject partial capture when a required field is unsupported.
- [ ] Persist profile only after explicit administrator confirmation.
- [ ] Compute current-versus-saved drift per field.
- [ ] Keep profile serializer as a closed six-key allowlist.

### Capture And Apply

- [ ] Implement fresh read before capture.
- [ ] Implement fresh read and capability validation before apply.
- [ ] Acquire one per-miner action lock.
- [ ] Build one `PATCH /api/system` body with only approved keys.
- [ ] Prove `manualFanSpeed` cannot enter that body.
- [ ] Read settings back after PATCH.
- [ ] Report per-field success, drift, unsupported, and failure results.
- [ ] Handle uncertain PATCH outcome by reading before any retry decision.
- [ ] Persist an audit event for capture/apply without raw payloads.

### Manual Miner Actions

- [ ] Add typed manager methods for restart, pause, resume, and identify.
- [ ] Add explicit Home Assistant service schemas and translations.
- [ ] Require unambiguous miner targets.
- [ ] Serialize actions through the same per-miner lock.
- [ ] Do not generic-retry mutation endpoints.
- [ ] Report clear typed failures to service callers.
- [ ] Choose final button/switch entities only after Home Assistant UX review.

### Phase 6 Tests

- [ ] Capture validates and stores exactly six fields.
- [ ] Apply body contains exactly allowed keys and values.
- [ ] Wi-Fi, pool, certificate, hostname, display, and unknown keys cannot be
  serialized.
- [ ] `manualFanSpeed` is absent when automatic fan control is false and true.
- [ ] Invalid ASIC frequency/voltage is rejected before PATCH.
- [ ] Read-back drift prevents a false success result.
- [ ] Concurrent actions serialize.
- [ ] Unknown/disabled miner actions reject.
- [ ] Service permissions and schemas reject invalid calls.

### Phase 6 Gate

- [ ] An administrator can capture, inspect, apply, and verify a profile.
- [ ] An administrator can execute explicit miner actions safely.
- [ ] No automatic recovery action exists yet.

## Phase 7: Fault Classification And Recovery Engine

### Classifier

- [ ] Add typed cause, severity, signal, confidence, and evidence models.
- [ ] Implement overheat evidence.
- [ ] Implement fan-failure evidence.
- [ ] Implement power/hardware-fault evidence.
- [ ] Implement ASIC-not-detected evidence after startup grace.
- [ ] Implement sustained zero/low-hash evidence with history windows.
- [ ] Implement reset-reason and firmware-log evidence.
- [ ] Implement pool-unavailable evidence that suppresses default restarts.
- [ ] Implement network-unreachable evidence.
- [ ] Keep unknown as a conservative explicit cause.

### Exclusions

- [ ] Exclude intentionally paused miners from zero-hash recovery.
- [ ] Exclude startup grace.
- [ ] Exclude in-progress restart/profile operations.
- [ ] Exclude stale/malformed telemetry.
- [ ] Exclude known pool outages from default crash action.
- [ ] Require expected-hashrate or corroborating fault evidence.

### Recovery Policy

- [ ] Add automatic recovery and profile-restore toggles.
- [ ] Add startup grace and consecutive/duration thresholds.
- [ ] Add cooldown and rolling attempt budget.
- [ ] Add return and verification timeouts.
- [ ] Add cause-specific suppression.
- [ ] Add `KEEP_SAFE_VALUES`, `RESTORE_AFTER_COOLDOWN`, and `LOG_ONLY` overheat
  modes.
- [ ] Make `KEEP_SAFE_VALUES` the persisted default.
- [ ] Centralize policy decisions as allow/deny plus reason.

### State Machine

- [ ] Implement every state listed in `PROJECT.md` as an enum.
- [ ] Implement one explicit validated transition function.
- [ ] Reject invalid transitions.
- [ ] Emit typed transition events.
- [ ] Reconcile interrupted work after Home Assistant restart.
- [ ] Cancel waiting work cleanly on unload.

### Automatic Responsive Recovery

- [ ] Re-evaluate policy under the action lock.
- [ ] Capture pre-action snapshot and bounded logs.
- [ ] Send one restart request.
- [ ] Treat expected reboot downtime as part of the same incident.
- [ ] Rediscover and require the same MAC.
- [ ] Evaluate overheat restore policy.
- [ ] Restore the profile only when enabled, valid, and permitted.
- [ ] Read back health and all profile fields.
- [ ] Enter cooldown after success or failure.

### Unreachable Handling

- [ ] Require repeated evidence before declaring unreachable.
- [ ] Search known endpoint and approved discovery sources.
- [ ] Never report a restart against a still-unreachable endpoint.
- [ ] Create one incident rather than one per failed poll.
- [ ] Continue bounded low-frequency rediscovery.
- [ ] Reconcile when the same MAC returns.

### Phase 7 Scenario Tests

- [ ] Responsive unhealthy miner restarts and verifies healthy.
- [ ] Miner returns at a new IP with the same MAC.
- [ ] Different MAC at old IP is rejected.
- [ ] Fully unreachable miner receives no claimed restart.
- [ ] Paused miner is not auto-restarted.
- [ ] Startup grace prevents false recovery.
- [ ] Pool outage suppresses default restart.
- [ ] Default overheat policy preserves firmware safe values.
- [ ] Opt-in overheat restore requires sustained cooldown.
- [ ] Power/hardware faults cannot create restart loops.
- [ ] Uncertain mutation reads state before another action.
- [ ] Attempt budget and cooldown block repeated action.
- [ ] Configuration drift produces a non-success outcome.
- [ ] Integration unload cancels recovery safely.
- [ ] Every state and invalid transition is covered.

### Phase 7 Gate

- [ ] Recovery is deterministic under an injected clock and fake client.
- [ ] Every automatic mutation has policy, audit, identity, and verification
  coverage.
- [ ] Real-device automatic recovery remains disabled until Phase 8 incident
  visibility and diagnostics are complete.

## Phase 8: Incidents, Logs, And Diagnostics

### Incident Repository

- [ ] Add stable incident IDs and append-only event models.
- [ ] Persist cause, evidence, policy decision, transitions, actions,
  verification, and final outcome.
- [ ] Bound snapshots and log excerpts.
- [ ] Add count- and age-based retention.
- [ ] Avoid duplicate incidents for one continuous outage.
- [ ] Paginate incident reads.
- [ ] Reconcile interrupted incidents on startup.

### Firmware Logs

- [ ] Fetch logs only on demand or around an incident.
- [ ] Bound response bytes, retained lines, and line length.
- [ ] Parse panic, watchdog, brownout, thermal, pool, and hardware evidence only
  from fixture-backed patterns.
- [ ] Keep unmatched text available only after redaction.
- [ ] Render all log text as untrusted text.

### Redaction And Diagnostics

- [ ] Implement recursive redaction for known and suspicious sensitive keys.
- [ ] Redact IP, MAC, hostname, SSID, wallet, pool identity, URL user info, and
  seeded secrets.
- [ ] Exclude full logs and raw responses.
- [ ] Include capability, freshness, policy, recovery, storage, and recent
  outcome summaries.
- [ ] Add log-throttling for recurring poll failures.

### Phase 8 Tests

- [ ] Incident event order and outcomes serialize/round-trip.
- [ ] Retention prunes deterministically.
- [ ] Continuous outage creates one incident.
- [ ] Log parsing is fixture-backed and bounded.
- [ ] HTML/script-like firmware text remains inert text.
- [ ] Seeded sensitive strings appear nowhere in diagnostics, logs, incidents,
  or WebSocket DTOs.
- [ ] Startup reconciliation never marks interrupted action successful without
  observation.

### Phase 8 Gate

- [ ] Every recovery is explainable from a redacted incident.
- [ ] Diagnostics pass recursive secret-leak tests.
- [ ] Automatic recovery can be enabled for controlled real-device testing.

## Phase 9: Administrator Fleet Panel

### Panel Registration And DTO Boundary

- [ ] Register the compiled panel as administrator-only.
- [ ] Serve the versioned static bundle through Home Assistant.
- [ ] Define explicit backend DTOs with a schema version.
- [ ] Validate DTOs as `unknown` in TypeScript.
- [ ] Handle incompatible schema versions visibly.
- [ ] Keep raw domain/wire objects out of WebSocket responses.

### WebSocket Commands

- [ ] Implement the command set specified in `PROJECT.md`.
- [ ] Require administrator authorization for every command.
- [ ] Validate required fields, types, enums, ranges, and unknown keys.
- [ ] Reuse typed application methods used by services.
- [ ] Paginate incidents/logs.
- [ ] Return stable typed error codes and safe messages.

### Fleet Overview

- [ ] Show fleet hashrate, power, efficiency, and coverage.
- [ ] Show online, unhealthy, overheat, and recovery counts.
- [ ] Show miner rows with freshness and explicit missing-data states.
- [ ] Add useful status/filter/sort behavior.
- [ ] Avoid interchangeable generic cards as the sole information structure.

### Discovery And Miner Views

- [ ] Show pending candidates and explicit approve/reject actions.
- [ ] Show bounded scan progress and results.
- [ ] Show miner telemetry, health evidence, endpoint state, and capabilities.
- [x] Query Recorder for bounded native-entity history charts.
- [ ] Show stale, unsupported, partial, and unavailable states distinctly.

### Profile And Recovery Views

- [ ] Show current versus saved six-field profile.
- [ ] Validate edits client-side and server-side.
- [ ] Confirm capture, apply, restart, and manual recovery.
- [ ] Show per-field apply verification.
- [ ] Expose policy settings and cause-specific suppression.
- [ ] Require strong confirmation for `RESTORE_AFTER_COOLDOWN`.

### Incidents And Logs

- [ ] Show a paginated incident timeline.
- [ ] Show evidence, transitions, actions, verification, and outcome.
- [ ] Show bounded filtered redacted logs as text.
- [ ] Support useful cause, miner, date, and outcome filters.

### Responsive And Accessible UX

- [ ] Validate phone, tablet, and desktop layouts.
- [ ] Provide full keyboard operation.
- [ ] Provide visible focus and accessible names.
- [ ] Restore focus after dialogs.
- [ ] Do not encode state only by color.
- [ ] Respect Home Assistant theme and reduced-motion preferences.
- [ ] Format numbers, dates, and units by locale.

### Phase 9 Tests

- [ ] Malformed DTOs fail safely.
- [ ] Loading, ready, empty, stale, partial, unavailable, and error states render.
- [ ] Non-admin and unauthenticated commands reject server-side.
- [ ] Every dangerous action requires confirmation.
- [ ] Log content cannot inject HTML.
- [ ] Mobile and desktop visual behavior is reviewed.
- [ ] Keyboard and automated accessibility checks pass.
- [ ] Production bundle builds reproducibly from lockfile.

### Phase 9 Gate

- [ ] The panel can perform every documented fleet operation without direct
  browser-to-miner requests.
- [ ] The release artifact includes the tested compiled panel.
- [ ] Home Assistant works normally when the panel is never opened.

## Phase 10: Optional Satoshi Radio Support

### Typed Client And Parsing

- [ ] Add anonymized `/api/v1/pool` fixtures.
- [ ] Add anonymized `/api/v1/users/{wallet}` fixtures.
- [ ] Add strict wire/domain models and parsers.
- [ ] Parse `G`, `T`, and `P` hashrate suffixes with documented SI scaling.
- [ ] Aggregate all workers instead of using the first entry.
- [ ] Distinguish missing values from zero.
- [ ] Add bounded timeout, rate limit, and error behavior.

### Configuration And Coordination

- [ ] Make the entire module opt-in.
- [ ] Store wallet/config details through appropriate redacted config options.
- [ ] Add an independent coordinator.
- [ ] Prevent external failures from affecting local miner availability or
  recovery.
- [ ] Do not send local telemetry to Satoshi Radio.

### Home Assistant And Panel

- [ ] Add only useful optional entities after reviewing API semantics.
- [ ] Add fleet/pool comparison to the panel.
- [ ] Show external-data freshness and failure separately.
- [ ] Redact wallet and worker identifiers from diagnostics/logs.

### Phase 10 Tests

- [ ] All suffixes and malformed values parse correctly.
- [ ] Multiple workers aggregate correctly.
- [ ] Disabled module performs no external requests.
- [ ] External timeout/outage leaves local monitoring/recovery untouched.
- [ ] Wallet and worker identifiers do not leak.

### Phase 10 Gate

- [ ] Optional pool support is useful but fully isolated.
- [ ] Core integration tests pass with the module disabled.

## Phase 11: Packaging, CI, And Automated Releases

### Complete Validation

- [ ] Run all Python and frontend checks on pull requests and `master`.
- [ ] Run Home Assistant and HACS validation.
- [ ] Validate translations and service schemas.
- [ ] Build panel once and pass its artifact into packaging.
- [ ] Add Markdown/link and secret scanning where practical.
- [ ] Document a manual dependency-review cadence without Dependabot PR automation.

### HACS Package

- [ ] Set `zip_release: true`.
- [ ] Set `filename: bitaxe_fleet.zip`.
- [ ] Set `hide_default_branch: true`.
- [ ] Package integration files at the ZIP root for HACS extraction into
  `custom_components/bitaxe_fleet`.
- [ ] Include compiled panel, manifest, translations, services, and Python code.
- [ ] Exclude tests, fixtures, caches, source maps if sensitive, npm tree, local
  state, and secrets.
- [ ] Install the built ZIP into a clean Home Assistant test environment.

### Semantic Release

- [ ] Prove the selected release tool maps Conventional Commits correctly.
- [ ] Configure release only after required checks pass on `master`.
- [ ] Prevent concurrent releases.
- [ ] Preserve curated Keep a Changelog sections.
- [ ] Stamp one identical version in tag, manifest, notes, and artifacts.
- [ ] Generate release notes and SHA-256 checksum.
- [ ] Pin actions and minimize token permissions.
- [ ] Test dry-run behavior without creating tags/releases.

### Phase 11 Tests

- [ ] `fix:` selects patch.
- [ ] `feat:` selects minor.
- [ ] Breaking marker follows documented pre-1.0 and post-1.0 behavior.
- [ ] Documentation-only commits do not unexpectedly release.
- [ ] Failed validation cannot publish.
- [ ] Archive content and manifest version validate.
- [ ] Clean HACS-style installation loads the integration and panel.

### Phase 11 Gate

- [ ] A dry run produces a reproducible valid ZIP and checksum.
- [ ] A controlled release can be installed and upgraded through HACS.
- [ ] Rollback/reinstall limitations are documented.

## Phase 12: Real-Device Validation And Release Readiness

### Hardware/Firmware Matrix

- [ ] Test at least two relevant Bitaxe hardware variants when available.
- [ ] Test at least two relevant firmware response shapes.
- [ ] Validate identity, telemetry, capabilities, logs, and mutations.
- [ ] Validate reboot return timing and endpoint movement.
- [ ] Record compatibility without publishing household identifiers.
- [ ] Update supported-version language based on evidence.

### Safety Drills

- [ ] Test paused, pool-down, overheat, fan fault, power fault, zero hash, API
  timeout, full network loss, new IP, and different-device-at-old-IP scenarios.
- [ ] Confirm default overheat behavior never restores aggressive values.
- [ ] Confirm no profile operation patches `manualFanSpeed`.
- [ ] Confirm unreachable hardware is not falsely reported as restarted.
- [ ] Confirm attempt limits and cooldown prevent loops.
- [ ] Confirm Home Assistant restart/unload cannot leave delayed mutation tasks.

### User Documentation

- [ ] Replace pre-implementation warning with accurate release status.
- [ ] Add exact HACS installation instructions and repository URL.
- [ ] Add setup, discovery, profile, policy, incident, and panel walkthroughs.
- [ ] Document firmware compatibility and known limitations.
- [ ] Document fully unreachable behavior and lack of smart-plug recovery.
- [ ] Document backup/migration expectations.
- [ ] Add troubleshooting without requesting unredacted private payloads.

### Release Checklist

- [ ] Select and document release candidate version.
- [ ] Freeze user-visible scope.
- [ ] Resolve all critical/high defects.
- [ ] Review dependency and license notices.
- [ ] Review diagnostics and release archive for secrets.
- [ ] Review `CHANGELOG.md` `Unreleased` entries.
- [ ] Verify clean install, upgrade, reload, restart, and uninstall.
- [ ] Publish a release and observe real use before the first stable feature release.
- [ ] Promote to stable only with successful compatibility and safety evidence.

### Phase 12 Gate

- [ ] Every global definition-of-done item passes.
- [ ] No unresolved safety-critical open decision remains.
- [ ] HACS install/update and Home Assistant lifecycle are proven.
- [ ] Release notes accurately separate features, limitations, and risks.

## Deferred Ideas

These are not initial-release tasks. Move one into a numbered phase only after
an explicit scope decision.

- ESP-Miner live WebSocket telemetry with REST fallback.
- Smart-plug or managed-PDU recovery for fully unreachable miners.
- Firmware update/flash management.
- Multi-Home-Assistant fleet federation.
- Public remote endpoints or cloud relay.
- Advanced hashrate anomaly modeling.
- Additional mining-pool providers.
- Additional recovery profile fields.

## Permanent Prohibitions

- Never identify a miner permanently by IP address.
- Never enroll an unknown MAC without administrator approval.
- Never scan public or unrestricted address space.
- Never let the browser contact miners directly.
- Never store Wi-Fi, pool, certificate, or unrelated AxeOS settings.
- Never add `manualFanSpeed` to a recovery profile or profile patch.
- Never restore aggressive settings after overheat by default.
- Never claim an unreachable miner received an API restart.
- Never retry an uncertain mutation before reading current state.
- Never report PATCH success without read-back verification.
- Never leak raw API payloads or household identifiers into diagnostics.
- Never weaken strict typing or tests solely to pass CI.
- Never describe an unimplemented feature as released.
