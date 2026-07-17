# Bitaxe Fleet

Bitaxe Fleet is a planned Home Assistant custom integration for discovering,
monitoring, configuring, and recovering Bitaxe miners running AxeOS/ESP-Miner.

> [!IMPORTANT]
> This repository is in early implementation. The `v0.1.1` development preview
> makes the singleton fleet config entry installable through HACS, while the
> repository provides test tooling and a development container. Miner discovery,
> monitoring, configuration, and recovery have not been implemented, so it is
> not a stable functional miner management release. See [TODO.md](TODO.md) for
> implementation progress and [PROJECT.md](PROJECT.md) for the complete
> technical design.

## Goals

Bitaxe Fleet will replace static IP-based Home Assistant YAML with a native,
HACS-installable integration that can manage a changing fleet of miners.

The project is designed to provide:

- Automatic local-network discovery of AxeOS miners.
- Stable miner identity based on MAC address instead of IP address.
- Automatic detection when a known miner moves to a new IP address.
- Native Home Assistant devices, entities, controls, history, and automations.
- Per-miner health monitoring and fault classification.
- Controlled restart and recovery behavior with cooldowns and safety limits.
- A small, explicit recovery profile for performance and cooling settings.
- Incident records containing telemetry, firmware logs, actions, and outcomes.
- An administrator-only TypeScript fleet management panel.
- Optional Satoshi Radio pool and wallet statistics.
- Automated validation, builds, semantic versioning, and GitHub Releases.

## Why This Project Exists

The dashboard that inspired this project uses static Home Assistant YAML and
hard-coded IP addresses for a fixed number of miners. That approach is useful
for basic monitoring, but it does not handle dynamic IP addresses, discovery,
device identity, recovery, configuration drift, or structured fault history.

Bitaxe Fleet will be a real Home Assistant integration rather than a collection
of REST sensors and templates. It will preserve the useful dashboard metrics
while adding fleet lifecycle management and safe recovery behavior.

Reference project:

- [satoshiradio/bitaxe-HAS-dashboard](https://github.com/satoshiradio/bitaxe-HAS-dashboard)

## Installation Model

Bitaxe Fleet will be distributed as a Home Assistant custom integration through
HACS.

- The always-on backend will be fully asynchronous, strongly typed Python.
- The fleet management panel will be strict TypeScript compiled to JavaScript.
- No Node.js runtime will be required after installation.
- No MQTT broker, external container, or Home Assistant add-on will be required.
- HACS will install a versioned `bitaxe_fleet.zip` GitHub Release artifact.

The initial releases will be installed as a HACS custom repository. Inclusion
in the default HACS repository can be requested after the integration has
stable releases, documentation, tests, and real-device validation.

## Miner Identity And Discovery

Every miner will be identified by the `macAddr` returned by
`GET /api/system/info`.

- The normalized MAC address is the permanent miner ID.
- The current IP address is mutable connection metadata.
- Entity unique IDs and stored recovery profiles are based on the MAC address.
- A rediscovered known MAC updates its endpoint without creating a new device.
- Unknown MAC addresses require administrator approval before enrollment.

Discovery will combine:

- AxeOS mDNS service discovery.
- Home Assistant DHCP information for known devices.
- Configurable periodic scans of approved private IPv4 networks.
- A manual `Scan now` action.

Active scans will use bounded concurrency, short timeouts, private addresses,
and a fixed AxeOS validation endpoint. Large networks will require an explicit
CIDR instead of being scanned automatically.

## Monitoring

Planned per-miner telemetry includes:

- Current, one-minute, ten-minute, and one-hour hashrate.
- Expected hashrate and error percentage.
- Power, input voltage, current, and core voltage.
- ASIC, secondary ASIC, and voltage-regulator temperatures.
- Fan speed, fan RPM, second-fan RPM, and cooling configuration.
- Accepted and rejected shares, rejection reasons, and best difficulty.
- Pool difficulty, pool response time, and fallback-pool state.
- Wi-Fi signal, uptime, firmware version, board version, and reset reason.
- Overheat, power fault, hardware fault, paused state, and recovery state.
- Block height, network difficulty, and blocks found when available.

Fleet-level entities will include total hashrate, total power, efficiency,
online count, unhealthy count, overheat count, and the latest fleet incident.

Hardware-dependent and firmware-dependent fields will remain optional. The
integration will not invent zero values for unsupported or missing sensors.

## Recovery Profile

The recovery profile is intentionally limited to six readable and writable
AxeOS settings. Bitaxe Fleet will not store or restore pool credentials, Wi-Fi
credentials, certificates, hostnames, display configuration, or unrelated
miner settings.

| Setting | AxeOS field | Normalized type | Unit |
| --- | --- | --- | --- |
| Frequency | `frequency` | `float` | MHz |
| Core voltage | `coreVoltage` | `int` | mV |
| Overclock enabled | `overclockEnabled` | `bool` | none |
| Automatic fan control | `autofanspeed` | `bool` | none |
| Target temperature | `temptarget` | `int` | C |
| Minimum fan speed | `minFanSpeed` | `int` | percent |

When a miner is enrolled, Bitaxe Fleet will read these values from
`GET /api/system/info` and offer them as the initial recovery profile. Valid
frequency and voltage choices will be obtained from `GET /api/system/asic`.

The Settings panel will provide:

- `Capture current` to replace the stored profile with current miner values.
- `Apply now` to apply and verify the stored profile immediately.
- `Apply automatically after recovery` as a per-miner toggle.
- Current-versus-saved values and configuration drift.
- Model-aware frequency and voltage validation.

If automatic fan control is disabled, Bitaxe Fleet will preserve the miner's
existing manual fan speed. `manualFanSpeed` is not part of the recovery profile
and will never be included in a recovery patch.

## Recovery Sequence

For a responsive miner that is classified as eligible for automatic recovery,
the default automatic sequence will be:

1. Capture the current telemetry and available firmware logs.
2. Send `POST /api/system/restart`.
3. Wait for the same MAC address to return, even if its IP changes.
4. Read the miner's current recovery settings.
5. Apply the saved six-field recovery profile when enabled and permitted.
6. Read the settings back and verify every supported field.
7. Record the trigger, actions, verification, and outcome as an incident.

Recovery will include startup grace periods, consecutive-failure thresholds,
cooldowns, maximum attempts, and explicit state transitions. An intentionally
paused miner will not be restarted.

### Fully Unreachable Miners

An HTTP restart cannot reach a miner whose network stack is unavailable, whose
firmware is completely frozen, or whose power is off.

The selected first-release behavior is API-only recovery:

- Rescan the network in case only the IP address changed.
- Record and expose an unreachable incident if the MAC cannot be found.
- Continue looking for the miner without issuing an impossible restart.
- Resume verification and optional profile restoration when it returns.

External smart-plug power cycling is not part of the initial scope.

## Overheat Safety

AxeOS intentionally changes performance and cooling settings after an overheat
condition. Restoring an aggressive profile without a safety gate could undo
that protection and create a restart loop.

Each miner will have a configurable overheat policy:

- Keep AxeOS safe values, which will be the default.
- Restore the full profile only after a sustained cooldown.
- Log the incident without restoring the profile.

The full-profile mode will have strict temperature, cooldown, and attempt
limits. Power and hardware faults will also avoid repeated automatic restarts.

## Faults And Incidents

The recovery engine will classify evidence into causes such as:

- Overheat
- Fan-control failure
- Power-regulator fault
- Hardware fault
- ASIC not detected
- Sustained low or zero hashrate
- Watchdog reset
- Firmware panic
- Brownout or power glitch
- Pool unavailable
- Network unreachable
- Unknown failure

Incident records will include the miner ID, endpoint changes, telemetry before
the failure, firmware reset reason, relevant log lines, recovery actions,
profile verification, and final outcome.

Current ESP-Miner firmware exposes a bounded log buffer through
`GET /api/system/logs`. Newer firmware preserves that buffer across a software
restart, which allows Bitaxe Fleet to collect useful post-restart evidence when
available. Compatibility with older firmware will not assume this behavior.

## Home Assistant Panel

The planned TypeScript panel will be administrator-only and responsive on
desktop and mobile. It will communicate with the Python backend through
authenticated Home Assistant WebSocket commands.

Planned views include:

- Fleet overview and aggregate statistics.
- Per-miner status and history charts.
- Pending discovery approval.
- Miner detail and diagnostics.
- Recovery profile settings and verification.
- Recovery-policy controls.
- Incident timeline and filtered firmware logs.
- Optional Satoshi Radio pool comparison.

The browser will not contact miners directly. All miner communication will pass
through Home Assistant.

## ESP-Miner API

The initial implementation will use this minimal API surface:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/system/info` | Identity, telemetry, faults, and current recovery settings |
| `GET` | `/api/system/asic` | Model and valid frequency/voltage options |
| `GET` | `/api/system/logs` | Firmware logs for incidents and diagnostics |
| `PATCH` | `/api/system` | Apply only the approved recovery settings |
| `POST` | `/api/system/restart` | Controlled restart |
| `POST` | `/api/system/pause` | Pause mining |
| `POST` | `/api/system/resume` | Resume mining |
| `POST` | `/api/system/identify` | Identify a physical miner |

Home Assistant recorder history will power panel charts, so device-side
statistics endpoints are not required for the first release.

API references:

- [Official ESP-Miner OpenAPI](https://github.com/bitaxeorg/ESP-Miner/blob/master/main/http_server/openapi.yaml)
- [OSMU Bitaxe API documentation](https://osmu.wiki/bitaxe/api/)
- [ESP-Miner source](https://github.com/bitaxeorg/ESP-Miner)

The API documentation and firmware implementation currently differ in some
areas. Bitaxe Fleet will use explicit compatibility parsing and real response
fixtures instead of blindly trusting generated models.

## Optional Satoshi Radio Support

The reference dashboard's pool functionality will remain optional.

- Pool statistics will come from `/api/v1/pool`.
- Wallet statistics will come from `/api/v1/users/{wallet}`.
- Hashrate strings will support `G`, `T`, and `P` suffixes.
- All returned workers will be aggregated instead of assuming `worker[0]`.

Disabling pool support will not affect local miner monitoring or recovery.

## Security And Privacy

- The panel and all mutating WebSocket commands will require an administrator.
- Active scanning will be restricted to configured private networks.
- HTTP redirects from miners will not be followed automatically.
- The recovery profile contains no passwords or pool credentials.
- Diagnostics will redact IP addresses, MAC addresses, SSIDs, wallet details,
  and any unexpected sensitive API values.
- Stored data will use Home Assistant's private, versioned storage helper.
- Logs will never include complete API payloads at normal log levels.
- Mutating operations will produce structured audit records.

## Engineering Standards

The project will optimize for correctness, auditability, and maintainability.

- Strict Python typing with no unbounded `Any` outside documented framework
  boundaries.
- Strict TypeScript with `noUncheckedIndexedAccess` and
  `exactOptionalPropertyTypes`.
- Fully asynchronous network I/O.
- Immutable validated domain models.
- Small functions with explicit responsibilities.
- Guard clauses and early returns instead of deeply nested conditionals.
- No `if` inside another `if` when a guard clause or extracted predicate makes
  the control flow clearer.
- Explicit state machines for recovery instead of scattered booleans.
- Dependency injection through typed protocols for deterministic tests.
- Versioned persistent schemas with tested migrations.
- Structured logs without secrets.
- Tests for every recovery transition and mutating operation.
- Conventional Commits and automatically generated semantic releases.

The detailed rules and architecture are maintained in
[PROJECT.md](PROJECT.md).

## Development

The initial toolchain targets Home Assistant `2026.7.2`, Python `3.14.2`, and
Node.js `24.13.0`. The repository includes a pinned development container with
that Python and Node.js environment.

In VS Code or another Dev Containers-compatible editor, open the repository and
select `Reopen in Container`. To use Docker directly:

```bash
docker build --tag bitaxe-fleet-dev:local --file .devcontainer/Dockerfile .
docker run --rm --interactive --tty --mount "type=bind,src=$PWD,dst=/workspaces/bitaxe-fleet" --workdir /workspaces/bitaxe-fleet bitaxe-fleet-dev:local bash
```

Inside the container, install dependencies and run the checks:

```bash
python -m pip install ".[dev]"
npm ci --prefix frontend
python -m ruff format --check .
python -m ruff check .
python -m mypy custom_components tests
python -m pytest
npm run --prefix frontend lint
npm run --prefix frontend typecheck
npm run --prefix frontend test
npm run --prefix frontend build
```

The placeholder frontend bundle is a build-only scaffold. It is not yet
registered as a Home Assistant panel.

## Release Process

Pull requests and pushes to `master` run Python, TypeScript, Home Assistant,
HACS, and release-archive validation.

An explicit annotated SemVer tag is the release approval. After the source
versions and curated changelog entry are prepared, pushing a tag such as
`v0.1.1` automatically:

1. Re-runs all validation against the tagged commit.
2. Builds the TypeScript panel from the lockfile.
3. Packages and verifies `bitaxe_fleet.zip`.
4. Generates a SHA-256 checksum and curated release notes.
5. Publishes the GitHub Release with both assets.

Each annotated SemVer tag publishes as a normal GitHub Release. Conventional
Commits guide the SemVer bump, while the explicit tag prevents an accidental
public release.

The release ZIP contains the integration files at its root because HACS extracts
it directly into `custom_components/bitaxe_fleet`.

HACS will use GitHub Releases as the update source. See
[CHANGELOG.md](CHANGELOG.md) for project history.

## Documentation

- [PROJECT.md](PROJECT.md): architecture, contracts, decisions, invariants, and
  engineering rules.
- [TODO.md](TODO.md): phased implementation backlog and verification gates.
- [CHANGELOG.md](CHANGELOG.md): user-visible changes by release.

## License

Bitaxe Fleet is licensed under the [MIT License](LICENSE). Code from the
reference dashboard or ESP-Miner firmware will not be copied into this
repository unless its license and attribution requirements are satisfied.
