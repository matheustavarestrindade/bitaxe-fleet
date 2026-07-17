# Bitaxe Fleet Project Specification

## Document Purpose

This document is the implementation source of truth for Bitaxe Fleet. It
captures the agreed product scope, architecture, contracts, safety rules, and
quality gates so that implementation can be delegated without redesigning the
project.

This is a specification, not evidence that a feature exists. Current execution
status belongs in [TODO.md](TODO.md), user-facing information belongs in
[README.md](README.md), and release history belongs in
[CHANGELOG.md](CHANGELOG.md).

If the documents conflict, use this precedence:

1. Explicit safety invariants in this document.
2. Architecture and data contracts in this document.
3. Checked and unchecked state in `TODO.md`.
4. User-facing descriptions in `README.md`.
5. Historical statements in `CHANGELOG.md`.

Do not silently reinterpret a safety rule. Record a proposed change in the
decision log and obtain human approval before implementing it.

## Project State

As of 2026-07-17, Phase 1 is complete. The repository contains a typed
singleton config-entry scaffold, strict Python and TypeScript tooling, a
development container, local lifecycle/config-flow tests, and validation CI.
It does not yet discover or contact miners, expose entities, register a panel,
or implement profiles, recovery, storage, or release artifacts.

## Product Definition

| Property | Decision |
| --- | --- |
| Product name | Bitaxe Fleet |
| Home Assistant domain | `bitaxe_fleet` |
| Source repository | `https://github.com/matheustavarestrindade/bitaxe-fleet` |
| Distribution | HACS custom integration |
| Backend | Asynchronous Python inside Home Assistant |
| Frontend | Strict TypeScript compiled to a Home Assistant custom panel |
| Initial Home Assistant target | `2026.7.2` |
| Development toolchain | Python `3.14.2` and Node.js `24.13.0` in a pinned Dev Container |
| Required runtime services | Home Assistant only; no Node.js runtime, MQTT, add-on, or required external service |
| Miner protocol | Local AxeOS/ESP-Miner HTTP API |
| Permanent miner identity | Normalized `macAddr` |
| Endpoint identity | Current IP address or resolvable hostname; mutable |
| Config-entry model | One singleton fleet config entry |
| Recovery model | API-only restart, rediscovery, restore, read-back, and verification |
| Default overheat policy | Preserve AxeOS safe values |
| Release branch | `master` |
| Versioning | Conventional Commits and SemVer |
| Release artifact | `bitaxe_fleet.zip` |

## Product Goals

- Discover supported miners without requiring fixed IP addresses.
- Keep one Home Assistant device when a miner's IP address changes.
- Expose trustworthy typed telemetry and controls through native entities.
- Present the entire fleet in a responsive administrator-only panel.
- Detect failures from multiple signals instead of one brittle threshold.
- Capture enough evidence to explain why each recovery happened.
- Recover responsive unhealthy miners through the official AxeOS API.
- Restore only explicitly approved performance and cooling settings.
- Prevent restart loops and unsafe overheat-profile restoration.
- Remain useful when optional Satoshi Radio support is disabled.
- Be safe to update through HACS and straightforward to audit.

## Non-Goals

- Flashing or upgrading ESP-Miner firmware.
- Replacing AxeOS's own thermal and electrical protections.
- Bypassing the local AxeOS HTTP API.
- Power cycling fully unreachable miners in the initial release.
- Integrating smart plugs in the initial release.
- Storing or restoring Wi-Fi credentials.
- Storing or restoring pool URLs, usernames, or passwords.
- Storing or restoring certificates or private keys.
- Managing hostnames, display settings, or unrelated AxeOS configuration.
- Running a Node.js server in production.
- Requiring MQTT, an external database, or a separate container.
- Supporting public-internet miner endpoints.
- Treating an IP address as a permanent device identifier.
- Automatically enrolling every HTTP server found on a subnet.
- Reimplementing Home Assistant recorder history in project storage.

## Terminology

| Term | Meaning |
| --- | --- |
| AxeOS | The web/API surface provided by ESP-Miner firmware |
| Candidate | A network endpoint that may be a miner but is not enrolled |
| Enrolled miner | A miner MAC explicitly approved for management |
| Miner ID | Canonically normalized `macAddr` |
| Endpoint | Current IP address, hostname, port, and scheme used to reach a miner |
| Snapshot | One immutable validated view of miner identity, telemetry, configuration, and health evidence |
| Recovery profile | The six approved settings that may be restored |
| Recovery policy | Per-miner rules controlling automatic action |
| Incident | Persisted evidence, actions, state transitions, and outcome for one fault episode |
| Capability | An API field, endpoint, or action confirmed for a particular miner/firmware response |
| Wire model | A typed description of untrusted API JSON before validation |
| Domain model | An immutable validated Python object used by application logic |
| DTO | A deliberately serialized object sent to Home Assistant or the panel |

## Authoritative Upstream References

Implementation must verify behavior against upstream firmware source and saved
fixtures, not just prose API documentation.

- Reference dashboard: <https://github.com/satoshiradio/bitaxe-HAS-dashboard>
- ESP-Miner repository: <https://github.com/bitaxeorg/ESP-Miner>
- ESP-Miner OpenAPI: <https://github.com/bitaxeorg/ESP-Miner/blob/master/main/http_server/openapi.yaml>
- Community API documentation: <https://osmu.wiki/bitaxe/api/>
- HACS integration publishing: <https://www.hacs.xyz/docs/publish/integration/>
- Home Assistant custom integration docs: <https://developers.home-assistant.io/docs/creating_integration_manifest/>
- Home Assistant custom panel docs: <https://developers.home-assistant.io/docs/frontend/custom-ui/creating-custom-panels/>

The most recent firmware inspected during planning was ESP-Miner `v2.14.2`.
That is a research snapshot, not a permanent maximum or minimum supported
version. Firmware compatibility must be capability-based and fixture-tested.

## Planned Repository Layout

The following structure is a target, not permission to create every file before
its phase in `TODO.md`.

```text
.
|-- .devcontainer/
|   |-- devcontainer.json
|   `-- Dockerfile
|-- .github/
|   |-- workflows/
|   |   |-- validate.yml
|   |   `-- release.yml
|   `-- dependabot.yml
|-- custom_components/
|   `-- bitaxe_fleet/
|       |-- axeos/
|       |   |-- __init__.py
|       |   |-- client.py
|       |   |-- compatibility.py
|       |   |-- errors.py
|       |   |-- models.py
|       |   |-- parser.py
|       |   `-- wire.py
|       |-- discovery/
|       |   |-- __init__.py
|       |   |-- active_scan.py
|       |   |-- manager.py
|       |   `-- models.py
|       |-- recovery/
|       |   |-- __init__.py
|       |   |-- classifier.py
|       |   |-- engine.py
|       |   |-- models.py
|       |   `-- policy.py
|       |-- translations/
|       |   `-- en.json
|       |-- brand/
|       |   |-- icon.png
|       |   `-- icon.svg
|       |-- www/
|       |   `-- bitaxe-fleet-panel.js
|       |-- __init__.py
|       |-- binary_sensor.py
|       |-- button.py
|       |-- config_flow.py
|       |-- const.py
|       |-- coordinator.py
|       |-- diagnostics.py
|       |-- entity.py
|       |-- manifest.json
|       |-- panel.py
|       |-- select.py
|       |-- sensor.py
|       |-- services.py
|       |-- services.yaml
|       |-- storage.py
|       |-- strings.json
|       |-- switch.py
|       `-- websocket.py
|-- frontend/
|   |-- src/
|   |   |-- api/
|   |   |-- components/
|   |   |-- models/
|   |   |-- views/
|   |   |-- bitaxe-fleet-panel.ts
|   |   `-- styles.ts
|   |-- package-lock.json
|   |-- package.json
|   `-- tsconfig.json
|-- tests/
|   |-- fixtures/
|   |   |-- axeos/
|   |   `-- satoshi_radio/
|   |-- axeos/
|   |-- discovery/
|   |-- recovery/
|   |-- conftest.py
|   `-- test_config_flow.py
|-- CHANGELOG.md
|-- LICENSE
|-- PROJECT.md
|-- README.md
|-- TODO.md
|-- hacs.json
|-- pyproject.toml
`-- renovate.json or equivalent dependency configuration
```

Only add platform files backed by an actual entity or control. For example,
omit `select.py` if no select entity survives design review.

## Architectural Boundaries

The project uses explicit layers. Dependencies point inward toward validated
domain models.

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| AxeOS transport | HTTP requests, timeouts, status handling, JSON acquisition | Interpret health, write storage, create entities |
| AxeOS parsing | Validate wire values and build immutable models | Perform network I/O, apply policy |
| Compatibility | Normalize documented firmware differences | Guess arbitrary malformed values |
| Discovery | Find and validate endpoint candidates | Enroll unknown MACs automatically |
| Coordinator | Schedule reads and publish current snapshots | Own long-running recovery policy |
| Classifier | Convert snapshots and history into typed evidence | Execute actions |
| Recovery engine | Enforce policy and state transitions | Bypass safety guards or mutate unrelated settings |
| Storage | Persist versioned enrollment, policy, profile, and incidents | Store secrets or recorder time series |
| Home Assistant platforms | Convert snapshots into entities and services | Parse raw API JSON |
| WebSocket API | Validate authenticated commands and return DTOs | Return raw domain or wire objects |
| Panel | Render DTOs and request commands | Contact miners directly |
| Satoshi client | Fetch and normalize optional public pool data | Block local fleet functionality |

No frontend code may access a miner URL. No entity may issue raw HTTP without
going through the per-miner client/manager boundary.

## Runtime Topology

One config entry owns the fleet.

```text
Home Assistant
  -> BitaxeFleetRuntime
     -> DiscoveryManager
     -> MinerRegistry
     -> one MinerCoordinator per enrolled miner
     -> one RecoveryEngine per enrolled miner
     -> IncidentRepository
     -> optional SatoshiRadioCoordinator
     -> panel WebSocket commands
```

The config entry's `runtime_data` must hold a typed runtime object. Do not use
untyped dictionaries as a service locator.

Each enrolled miner has one action lock. Polling, manual actions, and automatic
recovery must not concurrently mutate the same miner. Discovery scans use a
separate global concurrency limit.

## Core Data Flow

```text
HTTP response
  -> JSON object at an untrusted boundary
  -> TypedDict wire shape
  -> explicit validation and compatibility normalization
  -> frozen/slotted domain dataclass
  -> coordinator/recovery logic
  -> explicit Home Assistant or panel DTO
```

Raw response dictionaries must not flow into entities, storage, recovery code,
or frontend DTOs.

## Python Type Rules

- Use the Python version supported by the selected minimum Home Assistant
  release.
- Run `mypy --strict` over integration-owned Python.
- Use `from __future__ import annotations` consistently.
- Define `MinerId = NewType("MinerId", str)`.
- Use `@dataclass(frozen=True, slots=True)` for immutable domain values.
- Use `StrEnum` for persisted string states when the supported Python version
  permits it.
- Use `TypedDict` only for wire shapes and framework dictionaries.
- Use `Protocol` for injectable clocks, clients, discovery probes, and stores.
- Use `Mapping` and `Sequence` for read-only inputs.
- Prefer `object` plus explicit narrowing over `Any`.
- Confine unavoidable framework `Any` to one documented boundary and convert it
  immediately.
- Never use `cast` to make unvalidated JSON appear safe.
- Never use `# type: ignore` without a narrow error code and explanation.
- Model absence as `None`; do not use zero as an unknown sensor value.
- Use aware UTC `datetime` values internally and serialize ISO 8601 UTC.

Recommended domain model families:

| Model | Purpose |
| --- | --- |
| `MinerEndpoint` | Scheme, host/IP, port, and observation time |
| `MinerIdentity` | Miner ID, hostname, board/model, firmware, and API capabilities |
| `MinerTelemetry` | Validated optional readings and share counters |
| `MinerConfiguration` | Current six recovery fields plus relevant read-only state |
| `MinerSnapshot` | Identity, endpoint, telemetry, configuration, faults, and timestamp |
| `AsicCapabilities` | Model-specific frequency and voltage options |
| `RecoveryProfile` | Exactly six restorable fields |
| `RecoveryPolicy` | Automatic action and safety settings |
| `FaultEvidence` | Classified cause, severity, signals, and confidence |
| `Incident` | Immutable incident identity and persisted event sequence |
| `DiscoveryCandidate` | Validated but not necessarily enrolled endpoint and identity |

`DataUpdateCoordinator` must be parameterized as
`DataUpdateCoordinator[MinerSnapshot]` or a precisely named wrapper type.

## TypeScript Rules

- Enable `strict`.
- Enable `noUncheckedIndexedAccess`.
- Enable `exactOptionalPropertyTypes`.
- Do not use `any`.
- Treat WebSocket responses as `unknown` until parsed.
- Define DTO types once under `frontend/src/models`.
- Use discriminated unions for loading, error, empty, and ready states.
- Use exhaustive `never` checks for recovery and incident status rendering.
- Keep miner communication in a typed Home Assistant WebSocket adapter.
- Do not use `fetch` for miner endpoints.
- Do not mutate API response objects.
- Keep the compiled bundle out of handwritten source review where possible.
- Use web components/Lit patterns compatible with Home Assistant's frontend.
- Meet keyboard navigation, focus visibility, labels, contrast, and responsive
  layout requirements.

Node.js is a development and CI build dependency only. The release contains the
compiled panel bundle and does not run Node.js in Home Assistant.

## Control-Flow Rules

Code must optimize for auditability rather than cleverness.

- Prefer guard clauses and early returns.
- Avoid `if` inside `if` when predicates can be combined or invalid cases can
  return early.
- Keep network acquisition, parsing, policy, and side effects in separate
  functions.
- Use small named predicates for safety decisions.
- Use explicit state transitions instead of interdependent boolean flags.
- Avoid broad exception handlers.
- Map known transport failures to typed project exceptions.
- Do not suppress an exception without recording why it is safe.
- Do not retry mutations through a generic HTTP retry policy.
- Keep mutating methods obvious in their names and return types.
- Prefer the smallest implementation that satisfies the current TODO phase.

## AxeOS API Contract

### Supported Baseline Endpoints

| Method | Path | Use | Polling behavior |
| --- | --- | --- | --- |
| `GET` | `/api/system/info` | Identity, telemetry, faults, current configuration | Regular coordinator polling |
| `GET` | `/api/system/asic` | ASIC model and valid voltage/frequency options | Setup, model/firmware change, manual refresh |
| `GET` | `/api/system/logs` | Incident and diagnostics evidence | On demand and around failures |
| `PATCH` | `/api/system` | Apply approved settings | Manual apply or guarded recovery only |
| `POST` | `/api/system/restart` | Software restart | Manual action or guarded recovery only |
| `POST` | `/api/system/pause` | Pause mining | Explicit user action only |
| `POST` | `/api/system/resume` | Resume mining | Explicit user action only |
| `POST` | `/api/system/identify` | Physical identification | Explicit user action only |

Current firmware may expose `WS /api/ws` and `WS /api/ws/live`. REST remains the
compatibility baseline. WebSocket telemetry can be evaluated after a stable
REST release and must not replace a reliable polling fallback.

### Client Requirements

- Use asynchronous Home Assistant HTTP facilities.
- Use a short, explicit connect/read timeout.
- Bound response body sizes before parsing.
- Require JSON where JSON is expected.
- Validate success status codes per endpoint.
- Do not follow HTTP redirects automatically.
- Do not automatically retry `PATCH` or `POST` requests.
- Allow bounded retry with jitter only for idempotent reads.
- Include endpoint and operation in typed errors without leaking payload data.
- Make the client injectable for tests.
- Keep one logical client per current endpoint, replaceable after rediscovery.
- Close owned sessions/tasks during config-entry unload.

### Error Taxonomy

At minimum, distinguish:

- `AxeOSError`
- `AxeOSTimeoutError`
- `AxeOSConnectionError`
- `AxeOSHTTPError`
- `AxeOSAuthenticationError` if a supported firmware requires authentication
- `AxeOSInvalidResponseError`
- `AxeOSUnsupportedError`
- `AxeOSMutationUncertainError`

`AxeOSMutationUncertainError` means the connection failed after a mutation may
have reached the miner. Callers must read current state before deciding whether
to retry.

### Parsing And Compatibility

API fields have changed type or presence across firmware versions. Parsing must
be tolerant of known variants and strict about unsafe values.

- Validate the top-level value is a mapping.
- Parse booleans from actual booleans and explicitly documented numeric forms.
- Do not treat arbitrary non-empty strings as true.
- Parse numeric values only from finite numbers or documented numeric strings.
- Reject `NaN`, infinity, nonsensical negative counters, and unsafe ranges.
- Preserve unknown fields only in a redacted debug diagnostic, never as domain
  attributes.
- Treat absent hardware-specific fields as unsupported.
- Treat malformed identity as candidate validation failure.
- Normalize field-name variants in `compatibility.py`.
- Keep serializer aliases in one place.
- Save anonymized fixtures for each observed firmware/model shape.
- Add a fixture and regression test before adding a compatibility branch.

Do not key compatibility solely from a version string when the response itself
can demonstrate a capability.

## Miner Identity

`macAddr` is required before a candidate can be enrolled.

Canonical normalization requirements:

- Accept documented colon, hyphen, or plain hexadecimal representations.
- Remove separators and validate exactly 12 hexadecimal characters.
- Reject multicast, all-zero, and broadcast MAC addresses.
- Store and expose one lowercase colon-separated representation.
- Wrap the canonical value in `MinerId`.

The MAC is used for:

- Home Assistant device identifiers.
- Entity unique-ID prefixes.
- Registry keys.
- Recovery profile ownership.
- Incident ownership.
- Endpoint-move detection.

Never merge two records based only on hostname, IP address, board model, or
display name.

## Discovery

### Sources

Discovery will consume independent observations from:

- mDNS service `_axeos._sub._http._tcp`.
- Home Assistant DHCP information where a defensible AxeOS matcher exists.
- Configured private IPv4 active-scan ranges.
- Manual scan requests.
- Previously known endpoints during startup and recovery.

Do not add a broad DHCP manifest matcher until it is supported by real fixtures
and does not claim unrelated devices.

### Candidate Validation

A network endpoint is an AxeOS candidate only when all of these checks pass:

1. The host is allowed by the local-network policy.
2. `GET /api/system/info` returns a bounded successful JSON response.
3. The response contains a valid `macAddr`.
4. The response contains enough AxeOS-specific structure to avoid a generic
   JSON false positive.
5. The endpoint does not require an HTTP redirect.
6. The normalized identity can be represented by domain models.

Validation is read-only. Discovery must never call a mutation endpoint.

### Enrollment

- Unknown miner IDs enter a pending list.
- Pending candidates require an administrator to approve or reject them.
- Approval creates an enrolled registry record and entities.
- Rejection may be remembered to suppress repeated prompts.
- A rejected miner can be approved later.
- A known enrolled ID updates its current endpoint automatically.
- A known disabled ID remains disabled when rediscovered.
- Duplicate simultaneous observations collapse by miner ID.

### Active Scan Safety

- Accept only explicit private IPv4 networks.
- Reject public, multicast, loopback, link-local, and unspecified ranges.
- Do not derive an unbounded scan from a broad interface route.
- Require explicit administrator confirmation for large CIDRs.
- Bound concurrent probes.
- Use a short per-host timeout.
- Add jitter to periodic scans.
- Prevent overlapping scans.
- Make cancellation clean during unload.
- Do not log every failed host at warning level.
- Expose scan progress and summary, not a flood of errors.

The exact maximum automatic CIDR size, concurrency, timeout, and interval must
be selected and documented in `const.py` with tests before active scanning is
enabled by default.

### Endpoint Movement

When the same miner ID appears at a new endpoint:

1. Serialize the update through the registry.
2. Validate the new endpoint again.
3. Replace the active client endpoint atomically.
4. Preserve Home Assistant device and entity unique IDs.
5. Record an endpoint-change event with redacted addresses in diagnostics.
6. Trigger a fresh snapshot.

An endpoint change is not a new enrollment and not an incident by itself.

## Config Entry And Options

The integration has one singleton fleet config entry. Import from YAML is not
required.

Initial config flow responsibilities:

- Create the fleet manager entry.
- Explain local-network access and active scanning.
- Accept zero or more approved private IPv4 CIDRs.
- Allow discovery without active scanning.
- Optionally configure Satoshi Radio support.
- Abort cleanly if a fleet entry already exists.

Options flow responsibilities:

- Change approved scan ranges.
- Change discovery interval and scan enablement.
- Configure global polling defaults.
- Configure incident retention limits.
- Enable or disable Satoshi Radio and wallet lookup.
- Never collect AxeOS pool or Wi-Fi credentials.

Per-miner profile and recovery policy belong in project storage and the panel,
not in config-entry options.

## Polling And Coordination

Use one `DataUpdateCoordinator`-based coordinator per enrolled miner.

- Poll `/api/system/info` on a configurable interval.
- Stagger fleet polling to avoid synchronized bursts.
- Fetch `/api/system/asic` at enrollment and when model/firmware changes.
- Fetch logs only on demand or as part of an incident.
- Keep the last successful snapshot while marking freshness separately.
- Mark entities unavailable according to coordinator failure semantics.
- Do not turn one missing optional field into coordinator failure.
- Do treat invalid required identity as a protocol failure.
- Trigger classifier evaluation after each successful snapshot.
- Notify the recovery engine through a typed event, not direct entity calls.

Exact initial poll intervals and failure counts are open implementation
constants. Choose conservative values, expose user-relevant intervals through
options, and add timing-independent tests using an injected monotonic clock.

## Recovery Profile Contract

`RecoveryProfile` contains exactly these fields:

| Domain field | AxeOS key | Type | Unit | Validation source |
| --- | --- | --- | --- | --- |
| `frequency_mhz` | `frequency` | finite `float` | MHz | `/api/system/asic` options |
| `core_voltage_mv` | `coreVoltage` | `int` | mV | `/api/system/asic` options |
| `overclock_enabled` | `overclockEnabled` | `bool` | none | current info/capability |
| `automatic_fan_speed` | `autofanspeed` | `bool` | none | current info/capability |
| `target_temperature_c` | `temptarget` | `int` | C | conservative project bounds |
| `minimum_fan_speed_percent` | `minFanSpeed` | `int` | percent | inclusive `0..100` plus firmware bounds |

No extension dictionary is allowed in `RecoveryProfile`. Adding a seventh
field requires a reviewed change to this specification, storage migration,
serializer allowlist, UI, tests, and changelog.

### Profile Capture

- Read a fresh `/api/system/info` response.
- Require all six fields or report precisely which are unsupported.
- Read/cache `/api/system/asic` capabilities.
- Validate frequency and voltage against current model options.
- Normalize all values into domain types.
- Show the proposed profile before replacing a saved profile.
- Persist only after explicit administrator confirmation.
- Record an audit event without raw addresses or payloads.

### Profile Apply

- Require an enrolled miner and administrator action or authorized recovery.
- Acquire the per-miner action lock.
- Read current settings before mutation.
- Revalidate the saved profile against current ASIC capabilities.
- Build a patch from the six-field allowlist only.
- Never include `manualFanSpeed`.
- Never include any credential, pool, network, display, certificate, or hostname
  field.
- Send one deliberate `PATCH /api/system` request.
- Read current settings again.
- Compare normalized values field by field.
- Report exact drift instead of declaring success on HTTP status alone.
- Do not blindly retry an uncertain mutation.

If `autofanspeed` is false, the current manual fan speed must be preserved by
omission. Bitaxe Fleet does not read it into the profile and does not send it in
the profile patch.

### Verification

Boolean and integer fields require exact normalized equality. Frequency may use
a small documented comparison tolerance only if real firmware fixtures prove
that serialized/read-back precision differs. Do not add a tolerance preemptively.

An unsupported field is not silently successful. Store the result as unsupported
or failed with a reason and present it to the administrator.

## Health Classification

Classification consumes snapshots, freshness, previous snapshots, logs, and
explicit user state. It produces evidence; it does not execute actions.

Planned causes:

| Cause | Example evidence | Automatic restart eligibility |
| --- | --- | --- |
| `OVERHEAT` | Firmware overheat flag or unsafe sustained temperature | Policy-dependent, safe default suppresses profile restore |
| `FAN_FAILURE` | Fan fault, zero RPM under commanded load, rising temperature | Restricted; avoid repeated restarts |
| `POWER_FAULT` | Power-good or regulator fault | Normally suppressed |
| `HARDWARE_FAULT` | Firmware hardware fault | Normally suppressed |
| `ASIC_NOT_DETECTED` | ASIC count/state missing after startup grace | Limited restart attempts |
| `ZERO_HASHRATE` | Sustained zero hashrate while expected to mine | Eligible after exclusions and grace |
| `LOW_HASHRATE` | Sustained material deviation from expected hashrate | Conservative and configurable |
| `WATCHDOG_RESET` | Reset reason/log evidence | Record; action depends on current health |
| `FIRMWARE_PANIC` | Panic signature in preserved logs | Limited restart attempts |
| `BROWNOUT` | Brownout reset reason/log evidence | Record and suppress loops |
| `POOL_UNAVAILABLE` | Pool errors with otherwise healthy miner | Do not restart by default |
| `NETWORK_UNREACHABLE` | Repeated failed reads and no rediscovered endpoint | Cannot API-restart |
| `UNKNOWN` | Failure without sufficient evidence | Conservative limited behavior |

The classifier must separate observation from certainty. Each result includes a
severity, contributing signals, observation window, and human-readable reason.

### Required Exclusions

Do not classify zero hashrate as a crash when:

- The miner is intentionally paused.
- It is inside startup grace.
- A restart or profile apply is in progress.
- Telemetry is stale or malformed.
- The pool is known unavailable and local hardware is otherwise healthy.
- The configured expected hashrate is absent and no firmware fault supports the
  conclusion.

## Recovery Policy

Every enrolled miner has a policy with safe defaults.

Required policy concepts:

- Automatic recovery enabled/disabled.
- Automatic profile restoration enabled/disabled.
- Startup grace period.
- Consecutive unhealthy observation threshold.
- Minimum unhealthy duration.
- Recovery cooldown.
- Maximum attempts in a rolling window.
- Post-restart return timeout.
- Verification timeout.
- Overheat behavior.
- Cause-specific suppression.

Do not hard-code policy checks throughout the engine. Centralize them in typed
policy predicates that return an allow/deny decision and reason.

### Overheat Policy

Use a persisted enum with these modes:

| Mode | Behavior |
| --- | --- |
| `KEEP_SAFE_VALUES` | Default. Do not restore the saved profile after an overheat restart |
| `RESTORE_AFTER_COOLDOWN` | Restore only after sustained safe temperature and all attempt limits pass |
| `LOG_ONLY` | Record evidence and take no automatic restart/profile action |

`RESTORE_AFTER_COOLDOWN` must be explicitly selected by an administrator. Its
temperature threshold, sustained cooldown duration, and attempt limits must be
visible in the panel and validated server-side.

## Recovery State Machine

Persist meaningful incident events, but keep transient execution ownership in
memory. A Home Assistant restart must reconcile state from miner observations
instead of pretending an interrupted mutation completed.

| State | Meaning | Normal next states |
| --- | --- | --- |
| `IDLE` | Healthy or no active incident | `OBSERVING`, `CAPTURING` |
| `OBSERVING` | Fault evidence has not met action threshold | `IDLE`, `CAPTURING`, `SUPPRESSED` |
| `CAPTURING` | Collecting pre-action snapshot and logs | `RESTARTING`, `UNREACHABLE`, `SUPPRESSED`, `FAILED` |
| `RESTARTING` | Restart request is being sent | `WAITING_FOR_RETURN`, `FAILED` |
| `WAITING_FOR_RETURN` | Waiting for same MAC after restart | `REDISCOVERING`, `RESTORING`, `VERIFYING`, `UNREACHABLE` |
| `REDISCOVERING` | Searching approved sources for the same MAC | `RESTORING`, `VERIFYING`, `UNREACHABLE` |
| `RESTORING` | Applying the approved six-field profile | `VERIFYING`, `FAILED` |
| `VERIFYING` | Reading health and configuration back | `RECOVERED`, `FAILED`, `SUPPRESSED` |
| `RECOVERED` | Recovery succeeded | `COOLDOWN` |
| `COOLDOWN` | Automatic actions temporarily blocked | `IDLE`, `OBSERVING` |
| `UNREACHABLE` | API action is impossible; monitoring continues | `REDISCOVERING`, `VERIFYING`, `FAILED` |
| `SUPPRESSED` | Policy or safety guard denied action | `IDLE`, `OBSERVING` |
| `FAILED` | Attempt ended without verified recovery | `COOLDOWN`, `IDLE` after acknowledgement/policy |

Every transition must be implemented in one explicit transition function and
covered by tests. Invalid transitions raise a typed internal error and produce
an audit record; they do not silently coerce state.

### Automatic Recovery Sequence

For a responsive eligible miner:

1. Re-evaluate policy while holding the action lock.
2. Create an incident and capture the last/current snapshot.
3. Request bounded firmware logs if the endpoint still responds.
4. Send `POST /api/system/restart` once.
5. Wait without treating expected restart downtime as a new incident.
6. Probe the known endpoint and approved discovery paths.
7. Require the returning API response to contain the same miner ID.
8. Evaluate overheat and cause-specific restore guards.
9. Read the current six settings and current ASIC capabilities.
10. Apply the saved profile only if enabled, valid, and allowed.
11. Read back settings and health.
12. Record per-field verification and final outcome.
13. Enter cooldown whether the attempt succeeds or fails.

### Unreachable Sequence

For an API-unreachable miner:

1. Confirm the failure threshold rather than reacting to one timeout.
2. Search approved discovery sources for the same miner ID.
3. Update the endpoint if the same ID is found elsewhere.
4. Do not call restart against an endpoint that is still unreachable.
5. Record an unreachable incident after the configured threshold.
6. Continue low-frequency rediscovery without creating duplicate incidents.
7. Reconcile and verify when the same miner ID returns.

Software cannot restart a miner it cannot reach. Never report that such a
restart occurred.

### Mutation Safety

- Serialize mutations per miner.
- Re-check policy after acquiring the lock.
- Assign an operation/incident ID before mutation.
- Do not generic-retry POST or PATCH.
- If mutation outcome is uncertain, read state before another action.
- Verify identity after every restart/rediscovery.
- Verify configuration after every patch.
- Always enter cooldown after an attempted automatic mutation.
- Cancel cleanly on config-entry unload without marking success.
- Do not execute delayed work after the integration is unloaded.

## Incidents And Audit Events

An incident is append-only from the application's perspective. Corrections are
new events, not mutation of historical evidence.

Required incident data:

- Stable incident ID.
- Miner ID reference.
- Start and completion timestamps.
- Classified cause, severity, and evidence.
- Redacted endpoint-change metadata.
- Snapshot summary before action.
- Relevant bounded firmware log excerpt.
- Recovery policy decision and reason.
- Every state transition.
- Every requested action and normalized result.
- Profile field verification results.
- Final outcome.
- Integration and firmware versions.

Do not store complete raw API payloads. Bound log excerpts by line count and
bytes. Redact SSIDs, addresses, wallet values, credentials, URLs with user info,
and suspicious key/value pairs from captured evidence before persistence or DTO
serialization. The canonical miner ID and current endpoint may exist only where
required for registry ownership and communication; do not duplicate them into
incident log excerpts or exported diagnostics.

Suggested outcomes:

- `RECOVERED`
- `RECOVERED_WITH_DRIFT`
- `RETURNED_WITHOUT_ACTION`
- `SUPPRESSED_BY_POLICY`
- `UNREACHABLE`
- `RESTART_FAILED`
- `RESTORE_FAILED`
- `VERIFICATION_FAILED`
- `CANCELLED`

Retention must be bounded by age and count, configured in options, and pruned
without blocking the Home Assistant event loop.

## Persistent Storage

Use Home Assistant's versioned `Store` helper. Do not write ad hoc JSON files.

Suggested logical schema version 1:

```text
StoreData
  schema_version
  miners: map[MinerId, StoredMiner]
  rejected_candidates: map[MinerId, RejectionRecord]
  incidents: list[StoredIncident]

StoredMiner
  miner_id
  display_name
  enabled
  last_endpoint
  last_seen_at
  recovery_profile or null
  recovery_policy

RecoveryProfile
  frequency_mhz
  core_voltage_mv
  overclock_enabled
  automatic_fan_speed
  target_temperature_c
  minimum_fan_speed_percent
```

The actual schema must use explicit `TypedDict` wire types and domain conversion
functions. It must not persist live tasks, locks, clients, coordinator state,
raw payloads, passwords, or unrestricted dictionaries.

Storage requirements:

- Validate every load.
- Quarantine or report invalid records rather than crashing setup.
- Migrate sequentially by schema version.
- Test migration from every released version.
- Debounce non-critical writes.
- Flush critical profile/policy changes deliberately.
- Use atomic Home Assistant storage behavior.
- Keep migrations deterministic and side-effect free.

## Home Assistant Device Model

Create one device-registry device per enrolled miner.

Device identifiers use `(DOMAIN, miner_id)`. Connections may include the MAC
address in Home Assistant's expected normalized format. Suggested device info:

- Name from approved display name or sanitized hostname.
- Manufacturer `Bitaxe` or the verified board manufacturer.
- Model from validated AxeOS board/ASIC data.
- Software version from firmware.
- Configuration URL using the current private endpoint when safe.

Do not use mutable IP addresses in entity unique IDs.

### Entity Principles

- Entities read validated coordinator data only.
- Unsupported fields do not create misleading zero-value entities.
- Entity descriptions define units, device classes, state classes, icons, and
  translation keys.
- Counters use appropriate total/total-increasing state classes only when reset
  semantics are understood.
- Diagnostic entities are disabled by default when noisy or low-value.
- Mutating entities must call typed manager methods and expose failures.
- Avoid duplicate controls in entities and panel unless both add clear value.

Candidate sensors include hashrate windows, expected hashrate, power, voltage,
current, temperatures, fan RPM, fan percentage, accepted/rejected shares, pool
difficulty, response time, Wi-Fi RSSI, uptime, best difficulty, block height,
and fleet aggregates.

Candidate binary sensors include online, healthy, overheated, power fault,
hardware fault, fallback pool active, and recovery active.

Candidate controls include restart, identify, pause/resume, manual recovery,
capture profile, and apply profile. Dangerous actions require confirmation in
the panel or an explicit Home Assistant service call; do not overload a simple
toggle with an irreversible action.

Final platform selection belongs to the relevant `TODO.md` phase and must be
driven by Home Assistant UX conventions.

## Fleet Aggregation

Fleet totals use only fresh, valid snapshots from enabled enrolled miners.

- Total hashrate is the sum of available current hashrates.
- Total power is the sum of available power readings.
- Fleet efficiency is total power divided by total hashrate in a documented
  display unit, only when the denominator is positive.
- Online count uses availability/freshness rules.
- Unhealthy and overheat counts use classified current state.
- Missing metrics remain missing; they are not converted to zero.
- Aggregation must identify partial coverage in panel DTOs.

## Services And WebSocket API

Home Assistant services are for automations. Panel WebSocket commands are for
the administrator UI. Both call the same typed application methods.

Suggested services:

- `bitaxe_fleet.restart_miner`
- `bitaxe_fleet.pause_miner`
- `bitaxe_fleet.resume_miner`
- `bitaxe_fleet.identify_miner`
- `bitaxe_fleet.scan_now`
- `bitaxe_fleet.run_recovery`
- `bitaxe_fleet.capture_profile`
- `bitaxe_fleet.apply_profile`

All service schemas must require an unambiguous target and validate permissions
through Home Assistant conventions.

Suggested panel command namespace:

| Command | Purpose | Mutates state |
| --- | --- | --- |
| `bitaxe_fleet/fleet/list` | Fleet summary | No |
| `bitaxe_fleet/miner/get` | Miner detail | No |
| `bitaxe_fleet/discovery/list` | Pending candidates and scan state | No |
| `bitaxe_fleet/discovery/scan` | Start bounded scan | Yes |
| `bitaxe_fleet/discovery/approve` | Enroll candidate | Yes |
| `bitaxe_fleet/discovery/reject` | Reject candidate | Yes |
| `bitaxe_fleet/profile/get` | Current and stored profile | No |
| `bitaxe_fleet/profile/capture` | Store current six fields | Yes |
| `bitaxe_fleet/profile/update` | Validate/store edited profile | Yes |
| `bitaxe_fleet/profile/apply` | Apply and verify profile | Yes |
| `bitaxe_fleet/recovery/run` | Start guarded manual recovery | Yes |
| `bitaxe_fleet/policy/update` | Change recovery policy | Yes |
| `bitaxe_fleet/incidents/list` | Paginated incident summaries | No |
| `bitaxe_fleet/incidents/get` | Redacted incident detail | No |
| `bitaxe_fleet/logs/get` | Bounded redacted miner logs | No |

All custom panel commands require an authenticated administrator. Every input is
validated server-side. Unknown keys are rejected for mutating commands.

DTOs require an explicit schema version so the compiled panel can detect an
incompatible backend instead of rendering corrupt state.

## Panel Product Requirements

The panel must look and behave like a purposeful fleet operations interface,
not a generic card grid.

Required views:

- Fleet overview.
- Pending discovery approval.
- Miner detail.
- Performance and thermal history.
- Recovery profile comparison/edit/apply.
- Recovery policy controls.
- Incident timeline and detail.
- Bounded filtered firmware logs.
- Optional Satoshi Radio comparison.

Required behavior:

- Responsive at phone, tablet, and desktop widths.
- Keyboard-accessible controls and dialogs.
- Visible focus and useful accessible names.
- Clear loading, stale, unavailable, partial-data, and error states.
- Explicit confirmation for restart, recovery, profile apply, and policy modes
  that can restore overheat settings.
- Display current endpoint only to administrators and avoid exposing it in URLs
  where possible.
- Never render raw untrusted HTML from firmware logs or hostnames.
- Paginate or virtualize large incident/log collections.
- Prefer Home Assistant theme variables while retaining a distinct operational
  visual hierarchy.

History charts should query Home Assistant recorder/statistics rather than
persisting duplicate time-series data in browser or integration storage.

## Optional Satoshi Radio Module

Satoshi Radio support is optional and isolated from local fleet health.

Planned endpoints:

- `GET /api/v1/pool`
- `GET /api/v1/users/{wallet}`

Requirements:

- Disable cleanly without affecting miner setup.
- Use a separate async coordinator and timeout policy.
- Treat responses as untrusted and fixture-test them.
- Parse hashrate suffixes `G`, `T`, and `P` case-insensitively with documented
  SI scaling.
- Aggregate every returned worker; never assume `workers[0]`.
- Redact wallet identifiers from diagnostics and logs.
- Rate-limit requests and honor upstream errors.
- Distinguish missing worker data from zero work.
- Keep pool outages out of local AxeOS availability.

Do not send local miner telemetry to Satoshi Radio.

## Security Model

### Network Boundary

- Contact only configured/discovered private endpoints.
- Revalidate endpoints before use when DNS resolution changes.
- Reject redirects instead of allowing the HTTP client to follow them.
- Bound timeouts, body sizes, concurrency, and scan ranges.
- Do not accept arbitrary URLs from panel commands.
- Use SSRF-resistant host validation for every user-provided network.

### Authorization

- Register the panel for administrators only.
- Require administrator status for every custom WebSocket command.
- Apply Home Assistant service permission checks.
- Require explicit confirmation for high-impact panel mutations.
- Do not rely on frontend checks for authorization.

### Secret Handling

- Never store pool passwords, Wi-Fi passwords, certificates, or API payloads
  containing unknown secrets.
- Redact diagnostics recursively using both known keys and suspicious patterns.
- Keep wallet IDs, SSIDs, IPs, MACs, and configuration URLs out of shared
  diagnostics.
- Never log request or response bodies at normal levels.
- Make debug logging bounded and redacted.

### Dependency And Release Security

- Pin CI actions to immutable commit SHAs.
- Keep Python and npm lock/dependency metadata reviewable.
- Run dependency update automation.
- Generate a release checksum.
- Build releases in GitHub Actions from a tagged commit.
- Grant workflows minimum permissions.
- Do not expose release credentials to pull-request code.

## Diagnostics

Diagnostics should answer why the integration made a decision without exposing
the household network or credentials.

Include:

- Integration version.
- Home Assistant-relevant config options with sensitive values removed.
- Miner model and firmware version.
- Capability flags.
- Snapshot field-presence summary.
- Coordinator freshness and typed error category.
- Recovery state and policy mode.
- Incident counts and redacted recent outcomes.
- Storage schema version.

Exclude or redact:

- MAC addresses.
- IP addresses and hostnames.
- SSIDs.
- Wallet identifiers.
- Pool credentials and URLs containing user information.
- Full firmware logs.
- Raw API responses.

Tests must recursively assert that seeded secrets do not appear anywhere in the
diagnostic output.

## Logging

- Use one module logger per file.
- Use debug for bounded operational detail.
- Use info sparingly for lifecycle events.
- Use warning for actionable degraded behavior.
- Use error for failed operations requiring attention.
- Include miner references through a short redacted/stable label, not full MAC
  or IP.
- Include incident/operation IDs for mutation traces.
- Avoid logging the same poll failure at warning level every interval.
- Log state transitions in structured key/value form where practical.
- Never log complete API bodies, profile payload dictionaries, or secrets.

## Testing Strategy

### Unit Tests

- MAC normalization and invalid forms.
- Every wire parser and known field variant.
- Numeric/boolean validation edge cases.
- Profile allowlist serialization.
- Profile capability validation.
- Profile read-back comparison.
- Fault classification exclusions and precedence.
- Every recovery state transition.
- Every policy allow/deny reason.
- Incident redaction and retention.
- Storage load, corruption handling, and migrations.
- Satoshi hashrate parsing and worker aggregation.
- DTO serialization and schema versioning.

### Integration Tests

- Config flow and singleton behavior.
- Setup, reload, unload, and task cleanup.
- Discovery candidate validation and approval.
- Same MAC at a new IP without duplicate devices.
- Coordinator success, partial fields, timeout, malformed response, and recovery.
- Entity values, availability, unique IDs, and device linkage.
- Services and WebSocket authorization/input validation.
- Diagnostics redaction.
- Panel registration and static bundle serving.

### Recovery Scenario Tests

- Responsive zero-hash miner restarts and returns healthy.
- Miner returns at a different IP with the same MAC.
- Different miner appears at the previous IP and is rejected.
- Fully unreachable miner is never reported as restarted.
- Paused miner is never auto-restarted for zero hashrate.
- Startup grace suppresses false recovery.
- Pool outage suppresses default restart.
- Overheat keeps AxeOS safe values by default.
- Opt-in overheat restore waits for sustained cooldown.
- Power and hardware faults do not enter restart loops.
- Mutation timeout triggers read-before-retry handling.
- Profile patch contains exactly the six allowed keys.
- Manual fan speed is never patched.
- Read-back drift produces a non-success outcome.
- Attempt window and cooldown survive relevant runtime events.
- Unload cancels waiting/recovery tasks safely.

### Frontend Tests

- DTO parser rejects malformed data.
- All discriminated states render.
- Action dialogs show exact impact.
- Admin errors are handled.
- Mobile and desktop layouts remain usable.
- Keyboard navigation and focus restoration work.
- Untrusted log text is rendered as text.
- Optional and missing telemetry is distinct from zero.

### Real-Device Validation

Before the first stable release, test with multiple Bitaxe hardware variants and
at least two relevant ESP-Miner firmware response shapes. Capture anonymized
fixtures only after reviewing them for secrets.

No automated test should require a real miner or external Satoshi Radio service.

## Tooling And Quality Gates

Phase 1 pins Home Assistant `2026.7.2`, Python `3.14.2`, Node.js `24.13.0`, and
direct Python/frontend development dependencies in `pyproject.toml` and
`frontend/package-lock.json`. Required capabilities are:

- Ruff formatting and linting.
- `mypy --strict`.
- Pytest with Home Assistant custom-component support.
- Strict TypeScript compiler.
- ESLint for frontend source.
- Frontend unit tests.
- Production frontend build.
- Home Assistant integration validation.
- HACS validation.
- JSON and Markdown/link validation where practical.
- Release archive content validation.

Do not weaken checks merely to make CI green. Fix code or document a narrowly
justified exception.

## CI And Release Design

### Validation Workflow

Run on pull requests and pushes to `master`:

1. Validate repository metadata and dependency locks.
2. Format/lint Python.
3. Type-check Python strictly.
4. Run Python tests with coverage.
5. Lint and type-check TypeScript.
6. Run frontend tests.
7. Build the panel.
8. Run Home Assistant and HACS validation.
9. Build the release archive in a dry-run mode.
10. Verify archive paths and required files.

### Release Workflow

After all required checks pass on a release-worthy push to `master`:

1. Derive the SemVer bump from Conventional Commits.
2. Update or generate `CHANGELOG.md` without discarding curated entries.
3. Stamp the same version into `manifest.json` and release metadata.
4. Build the panel from locked dependencies.
5. Package the integration as `bitaxe_fleet.zip`.
6. Verify the archive contains the compiled panel and excludes source caches,
   tests, secrets, and development dependencies.
7. Generate a SHA-256 checksum.
8. Tag the exact commit.
9. Publish a GitHub Release with notes, archive, and checksum.

Do not publish from an unvalidated working tree or allow two release jobs to
race. Configure workflow concurrency.

### Conventional Commit Mapping

| Commit signal | Version effect |
| --- | --- |
| `fix:` | Patch |
| `feat:` | Minor |
| `BREAKING CHANGE:` or breaking marker | Major |
| `docs:`, `test:`, `ci:`, `chore:`, `refactor:` | No release unless configured otherwise |

Pre-`1.0.0` breaking behavior must be configured deliberately in the selected
release tool and documented before the first release.

### HACS Metadata

`hacs.json` will use release ZIP installation with:

- `zip_release: true`
- `filename: bitaxe_fleet.zip`
- `hide_default_branch: true`

Metadata must also identify the integration name and relevant project links
once the GitHub repository URL is known.

## Performance And Reliability

- No blocking network or file I/O on the Home Assistant event loop.
- No unbounded task creation.
- No overlapping scan loops.
- No per-poll log fetch.
- No full incident history in every fleet DTO.
- Paginate incident and log requests.
- Bound stored incidents and firmware log excerpts.
- Stagger polling across miners.
- Cancel and await owned tasks on unload.
- Avoid rebuilding all entities when an endpoint changes.
- Keep aggregate calculations linear in enrolled miner count.
- Use recorder for historical telemetry instead of custom time-series storage.

## Accessibility And Localization

- Use translation keys for Home Assistant entities, config flow, services, and
  errors.
- Keep English as the initial source language.
- Do not concatenate translated fragments to form sentences.
- Give icon-only buttons accessible names.
- Support keyboard-only action and dialog flows.
- Never encode status by color alone.
- Respect Home Assistant theme and reduced-motion preferences where available.
- Format dates, numbers, and units using locale-aware utilities in the panel.

## Documentation Maintenance

Every behavior-changing pull request must evaluate all four Markdown files.

- Update `PROJECT.md` when architecture, contracts, invariants, or decisions
  change.
- Update `TODO.md` as tasks become complete or new implementation work appears.
- Update `README.md` when user-visible setup, behavior, or limitations change.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.

Do not mark a TODO complete until its named verification passes. Do not describe
a planned feature as available in README installation instructions.

## Decision Log

| ID | Date | Decision | Reason |
| --- | --- | --- | --- |
| D-001 | 2026-07-16 | Use `Bitaxe Fleet` and domain `bitaxe_fleet` | Stable product and integration identity |
| D-002 | 2026-07-16 | Ship a direct HACS integration | Lowest operational complexity for Home Assistant users |
| D-003 | 2026-07-16 | Use Python backend plus compiled TypeScript panel | Native HA lifecycle with a fleet-focused UI and no production Node runtime |
| D-004 | 2026-07-16 | Use normalized `macAddr` as permanent miner ID | IP addresses and hostnames can change |
| D-005 | 2026-07-16 | Use one singleton fleet config entry | Discovery, aggregation, policy, and panel operations are fleet-scoped |
| D-006 | 2026-07-16 | Require approval for unknown miners | Prevent accidental enrollment and mutation of arbitrary devices |
| D-007 | 2026-07-16 | Keep recovery API-only for the initial release | Avoid smart-plug coupling and unsafe assumptions about external power control |
| D-008 | 2026-07-16 | Restore only six approved settings | Minimize mutation risk and avoid storing secrets/unrelated settings |
| D-009 | 2026-07-16 | Omit `manualFanSpeed` from recovery patches | Preserve existing manual speed when automatic fan control is disabled |
| D-010 | 2026-07-16 | Preserve AxeOS safe values after overheat by default | Avoid undoing firmware thermal protection or creating restart loops |
| D-011 | 2026-07-16 | Use explicit wire, domain, and DTO layers | Contain untrusted/mutable JSON and make behavior auditable |
| D-012 | 2026-07-16 | Use REST as the initial compatibility baseline | REST is broadly available and simpler to validate across firmware |
| D-013 | 2026-07-16 | Keep Satoshi Radio support optional and isolated | Local monitoring/recovery must not depend on an external pool service |
| D-014 | 2026-07-16 | Release from successful release-worthy pushes to `master` | Automate reproducible SemVer HACS updates |
| D-015 | 2026-07-16 | Maintain a Keep a Changelog-style `CHANGELOG.md` | Give users a curated, durable history beyond generated GitHub notes |
| D-016 | 2026-07-17 | Use `matheustavarestrindade/bitaxe-fleet` as the canonical source repository | Provides valid public documentation and issue-tracker URLs for HACS metadata |
| D-017 | 2026-07-17 | Target Home Assistant `2026.7.2` and Python `3.14.2` initially | Matches current Home Assistant development support and typed runtime-data APIs |
| D-018 | 2026-07-17 | Use strict TypeScript, Lit, ESLint, Vitest, and esbuild for the panel scaffold | Minimal browser build/test stack compatible with the planned custom panel |
| D-019 | 2026-07-17 | Test locally in a pinned Python `3.14.2` and Node.js `24.13.0` Dev Container | Keeps local validation aligned with the declared toolchain without adding a production runtime dependency |
| D-020 | 2026-07-17 | License Bitaxe Fleet under MIT | Supports open source distribution with a concise permissive license |

## Open Decisions

These items must be resolved in the relevant TODO phase rather than guessed in
unrelated code:

| ID | Decision needed | Required evidence |
| --- | --- | --- |
| O-004 | Initial polling and timeout values | Real-device behavior and conservative load testing |
| O-005 | Active-scan CIDR/concurrency limits | Network safety tests and expected fleet sizes |
| O-006 | Recovery timing/attempt defaults | Real-device restart timing and safety tests |
| O-007 | Incident retention defaults | Storage-size measurements and panel UX |
| O-008 | Final entity platform set | Home Assistant UX review after typed models exist |
| O-010 | Release automation tool | Ability to preserve curated changelog and produce required artifact |
| O-011 | Initial firmware support statement | Fixture and real-device validation matrix |
| O-012 | Whether AxeOS authentication variants are in initial scope | Current firmware/device evidence |

## Implementation Handoff Rules

An implementation agent must:

1. Read `README.md`, this document, `TODO.md`, and `CHANGELOG.md` before editing.
2. Work in TODO phase order unless a dependency is explicitly corrected.
3. Complete only the smallest currently unblocked task group.
4. Preserve all safety invariants and allowlists.
5. Add fixtures and tests with every API compatibility behavior.
6. Update TODO checkboxes only after verification succeeds.
7. Record user-visible changes under `CHANGELOG.md` `Unreleased`.
8. Update this decision log for any approved architectural change.
9. Avoid implementing optional later phases before the core integration works.
10. Stop and request a decision for an unresolved item that changes safety,
    persisted data, public contracts, or release behavior.
