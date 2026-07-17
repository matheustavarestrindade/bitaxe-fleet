# Changelog

All notable changes to Bitaxe Fleet will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Changelog Rules

- Add user-visible work to `Unreleased` in the same change that introduces it.
- Use `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, and `Security`
  headings where applicable.
- Describe behavior and impact rather than commit implementation details.
- Move released entries from `Unreleased` into a dated SemVer section.
- Keep the newest released version first.
- Preserve curated entries when generating GitHub release notes.
- Do not claim planned or incomplete work as released.
- Do not include secrets, private addresses, MAC addresses, wallet identifiers,
  or other household data.

## [Unreleased]

## [0.2.0] - 2026-07-17

### Added

- Administrator-driven manual enrollment of an AxeOS miner from Bitaxe Fleet's
  Configure flow using a private IPv4 address.
- Stable MAC-keyed miner storage, Home Assistant devices, and native hashrate,
  power, and temperature sensors.
- Bounded local `/api/system/info` polling with typed response validation and
  synthetic AxeOS compatibility fixtures.

### Security

- Manual onboarding accepts only RFC 1918 IPv4 addresses, follows no redirects,
  bounds request and response sizes, and never stores raw API payloads.

## [0.1.1] - 2026-07-17

### Fixed

- HACS release archives now place integration files at the archive root, so HACS
  extracts them directly into `custom_components/bitaxe_fleet`.
- Version tags are published as normal GitHub Releases so HACS can detect them.

## [0.1.0] - 2026-07-17

### Development Preview

- This development release packages the initial integration scaffold for HACS
  testing.
  Miner discovery, monitoring, configuration, and recovery are not implemented.

### Added

- Initial `README.md` defining the planned user experience, discovery model,
  monitoring scope, six-field recovery profile, recovery limitations, safety
  behavior, and HACS distribution model.
- Initial `PROJECT.md` defining architecture, typed boundaries, identity,
  discovery, recovery invariants, storage, security, testing, and release
  contracts.
- Initial `TODO.md` providing a phased implementation backlog with explicit
  verification gates and permanent safety prohibitions.
- Initial Keep a Changelog and Semantic Versioning policy.
- Typed Home Assistant custom-integration scaffold with a singleton fleet config
  entry, lifecycle cleanup, translations, manifest, HACS metadata, and brand
  assets. It does not yet contact miners.
- Strict Python tooling, Home Assistant lifecycle/config-flow tests, strict
  TypeScript/Lit placeholder panel tooling, and a locked npm dependency tree.
- A pinned Python `3.14.2` and Node.js `24.13.0` Dev Container for local
  validation.
- GitHub Actions validation for Python, frontend, Hassfest, HACS, and release
  archive checks, plus tag-triggered HACS release packaging.
- MIT License.

### Security

- Documented administrator approval for unknown miners and all panel commands.
- Documented private-network scan restrictions and redirect/SSRF protections.
- Documented the closed six-field recovery allowlist and explicit exclusion of
  credentials, unrelated AxeOS settings, and `manualFanSpeed`.
- Documented safe default handling for overheat incidents and fully unreachable
  miners.
