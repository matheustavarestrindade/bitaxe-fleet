# Bitaxe Fleet

Bitaxe Fleet is a Home Assistant custom integration for locally managing
Bitaxe miners running AxeOS/ESP-Miner. It keeps device identity tied to a
normalized MAC address rather than a changing DHCP address.

> [!IMPORTANT]
> Bitaxe Fleet communicates only with RFC 1918 IPv4 endpoints. Discovery
> candidates are never enrolled automatically, and automatic recovery is off by
> default. Validate every enabled recovery policy against a real miner first.

## Current Features

- Manual enrollment of an administrator-supplied private IPv4 AxeOS endpoint.
- AxeOS mDNS discovery and administrator-started, bounded private-CIDR scans.
- Explicit approval or rejection for every discovered unknown MAC address.
- MAC-safe endpoint updates when an enrolled miner moves to a new IP address.
- Native Home Assistant miner devices with 29 typed telemetry sensors and five
  health binary sensors.
- Nine hub-linked fleet aggregate sensors for combined hashrate, power,
  efficiency, uptime, best difficulty, and current fleet health counts.
- A Recorder-backed, administrator-only 24-hour performance and thermal graph
  for each enrolled miner.
- An auto-registered `custom:bitaxe-fleet-graph-card` for compact fleet
  hashrate, power, or efficiency history in any dashboard, with no manual
  Lovelace resource setup.
- Typed reads for AxeOS system information, ASIC capabilities, and bounded logs.
- Explicit restart, pause, resume, identify, profile capture, and profile apply
  controls through administrator-only services and the fleet panel.
- A closed six-setting recovery profile with capability validation and read-back
  verification.
- Opt-in, rate-limited automatic recovery for confirmed responsive failures.
- Redacted incidents, diagnostics, firmware logs, WebSocket DTOs, and a compiled
  administrator-only panel.

## Installation

Install Bitaxe Fleet as a custom HACS repository, then install the latest normal
GitHub Release. HACS extracts the release ZIP directly into
`custom_components/bitaxe_fleet`.

Restart Home Assistant, then add **Bitaxe Fleet** from **Settings > Devices &
services**. The integration owns one singleton fleet entry.

## Onboarding And Discovery

The initial Configure flow remains the fastest way to add a known miner:

1. Open **Settings > Devices & services > Bitaxe Fleet > Configure**.
2. Enter the miner's private IPv4 address.
3. Bitaxe Fleet performs one bounded, redirect-free
   `GET /api/system/info` validation request.
4. The returned normalized `macAddr` becomes the permanent miner identity.

The **Bitaxe Fleet** sidebar panel also lists discovery candidates from AxeOS
mDNS and on-demand scans. Enter a compact private CIDR such as
`192.168.10.0/24` to scan it. Scans are limited to 256 hosts with bounded
concurrency. Approving a candidate performs a second same-MAC read before it is
enrolled.

Known MAC addresses can update their endpoint after rediscovery. A different MAC
at an enrolled address is rejected for polling and control actions; it can only
appear as a separate approval candidate.

## Monitoring

Each enrolled miner has native Home Assistant entities for the AxeOS telemetry
used by the referenced dashboard and additional validated firmware fields:

- Current, rolling, and expected hashrate; error rate; power; input voltage;
  current; temperatures; frequency; core voltage; and fan speed/RPM.
- Accepted/rejected shares, best/session/pool difficulty, pool response time,
  Wi-Fi signal, uptime, block height, network difficulty, and blocks found.
- Mining, fallback-pool, overheating, power-fault, and hardware-fault binary
  health states.

The Bitaxe Fleet hub device also provides fleet-wide total hashrate in GH/s and
TH/s, total power, efficiency in J/TH, cumulative uptime, highest reported best
difficulty and session-best difficulty, and online, unhealthy, and overheating
counts. Aggregate values use only fresh snapshots from enabled miners. Each
aggregate exposes enabled, online, and per-metric coverage attributes, so a
partial fleet never looks like a complete zero-value total.

The administrator panel lazily displays a 24-hour hashrate, power, and
temperature graph using Home Assistant Recorder data. Bitaxe Fleet does not
duplicate sensor history in its own storage: graphs are unavailable if Recorder
is disabled, excludes the native sensors, or has already purged the requested
window. Missing AxeOS fields and unavailable readings remain unavailable rather
than becoming fabricated zero values. The fleet panel also shows current
telemetry, a compact fleet performance summary, online freshness, saved profile
state, candidate status, scan progress, incidents, and on-demand redacted logs.
It automatically presents hashrate in GH/s or TH/s and difficulty with K, M, G,
or T suffixes while retaining raw numeric values in Home Assistant entities.

### Fleet Dashboard Graph

Bitaxe Fleet automatically registers its bundled dashboard card when the
integration loads. Add **Bitaxe Fleet graph** from the dashboard card picker,
or use it directly in a dashboard configuration without adding a Lovelace
resource:

![Fleet hashrate dashboard card](screenshots/Fleet%20hashrate%20card.png)

```yaml
type: custom:bitaxe-fleet-graph-card
metric: hashrate
name: Fleet hashrate
```

`metric` defaults to `hashrate`; `power` and `efficiency` are also supported.
Each card reads only its selected aggregate from Home Assistant Recorder over a
fixed 24-hour window, displays unavailable periods as graph gaps, and formats
fleet hashrate dynamically as GH/s or TH/s. It refreshes its cached Recorder
data every 30 seconds. The card uses the same administrator-only WebSocket
boundary as the fleet panel, so it must be viewed by an administrator.

### Fleet Dashboard Performance

Add **Bitaxe Fleet performance** from the dashboard card picker to see the
current fleet and every enrolled miner without configuring entity IDs:

```yaml
type: custom:bitaxe-fleet-overview-card
name: Fleet performance
```

The card shows each miner's current hashrate, best overall difficulty, best
session difficulty, and online, stale, offline, or disabled state. Its fleet
summary shows the fresh enabled-miner total hashrate and the highest reported
overall and session difficulty, with explicit reporting coverage. Disabled and
non-fresh miners stay visible in the individual list but do not contribute to
the fleet summary. The card refreshes its cached data every 30 seconds; miners
are polled by the integration every 60 seconds, so the card never causes extra
requests to a miner.

After installing or updating Bitaxe Fleet, reload the Home Assistant browser
page before opening the card picker so Home Assistant loads the bundled card
module.

## Controls And Profiles

The following administrator-only Home Assistant services target a normalized MAC
address:

- `bitaxe_fleet.restart_miner`
- `bitaxe_fleet.pause_miner`
- `bitaxe_fleet.resume_miner`
- `bitaxe_fleet.identify_miner`
- `bitaxe_fleet.capture_profile`
- `bitaxe_fleet.apply_profile`
- `bitaxe_fleet.scan_network`

Before every mutation, Bitaxe Fleet performs a fresh same-MAC system-info read.
It does not retry a timed-out or disconnected mutation automatically.

Recovery profiles are deliberately restricted to these AxeOS fields:

| Setting | AxeOS field |
| --- | --- |
| Frequency | `frequency` |
| Core voltage | `coreVoltage` |
| Overclock enabled | `overclockEnabled` |
| Automatic fan control | `autofanspeed` |
| Target temperature | `temptarget` |
| Minimum fan speed | `minFanSpeed` |

Capture requires all six values. Apply requires a fresh capability read, sends
only those six allowlisted fields, and verifies every value by reading it back.
`manualFanSpeed`, pool settings, Wi-Fi settings, hostnames, certificates, and
all other configuration are never restored.

## Automatic Recovery

Automatic recovery is disabled by default and configured per miner in the panel.
It can react to repeated zero-hash, power-fault, or hardware-fault snapshots
only after startup grace and the configured consecutive-observation threshold.

- Every automatic restart has a cooldown, rolling attempt budget, and
  post-restart verification deadline.
- Attempt history is retained through a Home Assistant restart, so restarting
  Home Assistant cannot reset the loop-prevention budget.
- A manually paused miner is never auto-restarted.
- AxeOS overheat protection never triggers a restart or immediate profile apply.
- The default overheat policy retains AxeOS's safe values. An explicitly enabled
  `RESTORE_AFTER_COOLDOWN` policy can restore a saved profile only after the
  configured cooldown.
- A successful restart is verified only by a later positive-hashrate snapshot.

Fully unreachable miners cannot receive an API restart. Bitaxe Fleet does not
claim that an unreachable device was restarted or power-cycle it.

## Security And Privacy

- Only RFC 1918 IPv4 addresses are accepted; hostnames, public, loopback,
  link-local, multicast, and arbitrary URLs are rejected.
- Miner HTTP requests are bounded, redirect-free, and use fixed documented
  AxeOS paths.
- The panel uses Home Assistant's administrator-only WebSocket boundary and
  never contacts a miner from the browser.
- Stored records contain only approved endpoint metadata, profiles, policies,
  candidate rejections, and bounded incident summaries. Raw API payloads are
  not stored.
- Logs, incident details, and diagnostics redact addresses, MACs, URLs,
  credentials, SSIDs, hostnames, and likely wallet identifiers.

## Firmware API

Bitaxe Fleet uses this documented local AxeOS API surface:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/system/info` | Identity, telemetry, health, and configuration |
| `GET` | `/api/system/asic` | Model capabilities and allowed frequency/voltage values |
| `GET` | `/api/system/logs` | Bounded on-demand firmware log text |
| `PATCH` | `/api/system` | Apply the closed recovery-profile allowlist |
| `POST` | `/api/system/restart` | Controlled restart |
| `POST` | `/api/system/pause` | Pause mining |
| `POST` | `/api/system/resume` | Resume mining |
| `POST` | `/api/system/identify` | Physical identification |

Compatibility is based on validated fields and capability responses, not on a
firmware-version allowlist. Synthetic fixtures cover the supported parser
shapes; real-device validation remains required before enabling automatic
recovery in production.

## Deliberate Limits

The optional Satoshi Radio pool/wallet module is not part of this release. It
will remain isolated from local monitoring and recovery if added later. Smart
plug power cycling, firmware flashing, public-internet endpoints, automatic
candidate enrollment, and storing pool or Wi-Fi credentials are out of scope.

## Development

The project targets Home Assistant `2026.7.2`, Python `3.14.2`, and Node.js
`24.13.0`. The repository includes a pinned development container.

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

## Releases

Push an annotated SemVer tag only after source versions and the curated
changelog entry agree. The release workflow reruns validation, builds the
frontend bundle, packages `bitaxe_fleet.zip`, writes a SHA-256 checksum, and
publishes a normal GitHub Release.

## Documentation

- [PROJECT.md](PROJECT.md): architecture, contracts, and safety invariants.
- [TODO.md](TODO.md): original phased implementation ledger and remaining work.
- [CHANGELOG.md](CHANGELOG.md): user-visible release history.

## License

Bitaxe Fleet is licensed under the [MIT License](LICENSE).
