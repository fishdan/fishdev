# Implementation Plan: Pinned and integrity-verified installer downloads

**Branch**: `specs/0.005-installer-download-integrity` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)

## Summary

Introduce FishDev releases with a SHA-256 manifest. Make both installers stage, verify, and only then write. Pin uv, SpecKit, and CI actions in one recorded location. Extend `fishdev.py` with a manifest generator, a drift check in verification, and a rule that rejects unpinned downloads.

## Current context

- `install.sh` downloads 7 files from `main` with `curl -fsSL`, writing each straight into the project. `set -e` stops on the first error, but files already written remain.
- `docs/windows-vscode-powershell.md` downloads the same 7 files with `Invoke-WebRequest` from `main`, and installs uv with `irm … | iex` and SpecKit from PyPI without a version.
- `fishdev-init.md` repeats the uv and SpecKit commands for repair.
- `.github/workflows/verify.yml` uses `actions/checkout@v4` and `actions/setup-python@v5`.
- `fishdev.py` (Python 3.11 standard library) already has `verify`, `check` with `forbid_paths` and `forbid_text` rules, and exceptions. No release or tag exists yet.

## Design decisions to resolve before implementation (T002)

1. **FishDev source reference.** Choose between tagged-release assets and raw URLs at a full commit SHA. A file cannot contain its own commit SHA, so a tag-based release that embeds the manifest digests in `install.sh` is the likely fit. Record the tradeoff.
2. **Manifest location and format.** For example, JSON version 1 at `.config/ai/release-manifest.json`, with digests also embedded in `install.sh` so the bootstrap carries its own expectations. Decide whether embedding is generated or checked.
3. **Third-party pin record.** One file (for example `.config/ai/pins.json`) that the installer, the Windows guide, the drift check, and the monthly audit read or are checked against.
4. **uv.** Confirm from official uv documentation how to fetch a versioned installer or release archive and its published checksum on Linux, macOS, and Windows. Pick the initial version.
5. **SpecKit.** Choose a released version, and PyPI version pinning versus a git tag or full commit SHA, so Bash and Windows match. Decide whether to constrain transitive dependencies (for example with a constraints file) and record why.
6. **Upgrade behavior.** Decide whether rerunning the installer on an existing FishDev project is refused, compared, or treated as an upgrade. Keep it narrow; full upgrade support can be separate work.
7. **Unpinned-download rule.** Define an objective pattern (shell pipes from `curl`/`wget`/`irm`/`iwr`, `main`/`master`/`HEAD` refs, `@v<major>` action tags), its file scope, and its false-positive handling. Decide whether a new rule kind is needed or `forbid_text` suffices.

## Constitution check

- **Spec-driven**: This spec and [tasks.md](tasks.md) precede implementation. Every change maps to a task and progress entry.
- **AI neutrality**: Pins, manifest, and tooling live under `.config/ai/` or the installer. Nothing is vendor-specific.
- **Security**: Fail closed. No verification bypass by default. The documented threat model does not overclaim.
- **Testing**: Fixture tests with a local source cover success and each failure path. The same checks run locally and in CI.
- **Narrow scope**: Signing, adopter dependency pinning, and installer feature changes are excluded.

## Delivery sequence

1. Resolve the design decisions above from official sources and record them here and in `docs/`.
2. US3 foundation: manifest generator, pin record, and drift check, with tests. This makes later steps self-checking.
3. US1: staged, verified `install.sh` with a local-source test mode. Then the Windows guide's equivalent and the bootstrap documentation.
4. US2: pin uv, SpecKit, and CI actions. Update `fishdev-init.md`.
5. Add the unpinned-download rule and its fixtures. Make FishDev's own repository pass it.
6. Update `start.ai` audit guidance, the README, and docs. Cut the first release per the documented procedure, validate an end-to-end install from it, and record results.

## Validation gates

- `python3 -m unittest discover -s tests -v`, plus a Python 3.11 run.
- `python3 .config/ai/tools/fishdev.py verify` and `verify --ci`, both locally and in hosted CI.
- `bash -n install.sh`, plus fixture installs on success and every failure path, comparing the target directory before and after a failure.
- PowerShell parsing and logic where `pwsh` is available; otherwise document the native Windows gap.
- An end-to-end install from the first published release in a clean temporary directory.

## Risks

- The pin chain is only as strong as its first link: users who skip the bootstrap digest check still trust the transport. Document this plainly.
- Upstream URL or checksum formats for uv or SpecKit may change. Keep the pin record and audit step the single place to update.
- Strict pins age. The monthly audit must actually review them, or pinning trades drift risk for stale-vulnerability risk.
- A broad unpinned-download pattern can flag documentation that explains the old behavior. Scope the rule and use the existing exception contract.
