# Changelog

All notable changes to Bitaxe Fleet will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project will adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once releases begin.

Bitaxe Fleet has an early development scaffold but no installable release yet.
Version headings and repository comparison links will be added by the release
process when the first release is published.

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
- GitHub Actions validation for Python, frontend, Hassfest, and HACS checks,
  plus Dependabot configuration.
- MIT License.

### Security

- Documented administrator approval for unknown miners and all panel commands.
- Documented private-network scan restrictions and redirect/SSRF protections.
- Documented the closed six-field recovery allowlist and explicit exclusion of
  credentials, unrelated AxeOS settings, and `manualFanSpeed`.
- Documented safe default handling for overheat incidents and fully unreachable
  miners.
