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

## Resolved design (T002, 2026-11-16)

Sources: GitHub release APIs for `astral-sh/uv`, `github/spec-kit`, `actions/checkout`, and `actions/setup-python`; the PyPI JSON API; SpecKit's `docs/installation.md`; and the downloaded uv installers. Commands were tested in scratch directories with isolated `UV_TOOL_DIR`.

1. **Source reference.** FishDev files come from `raw.githubusercontent.com/fishdan/fishdev/<release tag>/…`. Tags can be moved, so integrity comes from SHA-256 digests embedded in each installer path, not from the tag. A tag's `install.sh` always describes files at that same tag, so there's no circular dependency. The first release is `v0.5.0`.
2. **Manifest and pins.** Maintainers edit one input file, `.config/ai/release.json` (version 1): release ID, source, shipped file list, and every third-party pin with its version, URL, digest or commit, source, and review date. `.config/ai/tools/release.py update` writes `.config/ai/release-manifest.json` and regenerates every `BEGIN/END fishdev-release:<block>` region in `install.sh`, the README, the Windows guide, `fishdev-init.md`, and the CI workflow. It repeats until nothing changes, because the README's bootstrap digest depends on the regenerated `install.sh`. `release.py check` renders the same output in memory and fails on any difference. It is a separate maintainer module, so `fishdev.py` (shipped to every project) stays unchanged (TOCA context minimization). `update` refuses to change digests under a release ID that already has a local git tag.
3. **Cooldown.** Third-party pins use the newest release that is at least 7 days old when reviewed. This reduces exposure to a freshly compromised or broken upstream release.
4. **uv.** Pinned to 0.13.7 (2026-11-03). The installers come from `github.com/astral-sh/uv/releases/download/0.13.7/uv-installer.{sh,ps1}`. uv's `sha256.sum` does not cover the installer scripts, so FishDev records the digests it computed at review. The shell installer embeds and checks SHA-256 digests for each archive it downloads. The PowerShell installer does not, so Windows archive integrity rests on HTTPS and the versioned URL, and the documentation says so. An existing uv is respected if it is at least 0.4.0: `uv tool install <wheel>`, `uv tool list`, and `uv tool dir --bin` all worked on uv 0.4.0 and 0.5.0. An older uv stops the install.
5. **SpecKit.** Pinned to `specify-cli` 1.3.3 (2026-11-09), an official channel according to SpecKit's installation docs. `uv tool install` ignored a deliberately wrong `--hash` in a constraints file, so hashes cannot be enforced that way. Instead, both paths download the PyPI wheel, check its SHA-256, and run `uv tool install <local wheel>`. SpecKit 1.3.3 accepted FishDev's `init` flags, and `specify init` uses bundled assets with no network access. **Transitive dependencies are not constrained** in this release: uv resolves them from PyPI, where an uploaded file cannot be replaced. Hash-pinning them would need a maintained constraints file that uv does not enforce for tool installs. This is recorded as a risk.
6. **CI actions.** `actions/checkout` v7.0.1 (`3d3c42e5…`) and `actions/setup-python` v7.1.0 (`6d4fd22b…`). The current majors (v4 checkout) run on node20, while v7 runs on node24.
7. **Upgrade behavior.** The installer refuses to run when `start.ai`, `.config/ai`, or `.specify` already exists, matching the Windows guide. Previously it silently overwrote `progress.ai` and `handoff.ai`. Upgrade support is separate work.
8. **Unpinned-download rule.** `SEC-001` is a `forbid_text` rule over `install.sh`, `README.md`, `fishdev-init.md`, `docs/*.md`, and `.github/workflows/*`. It matches `curl`/`wget` piped into a shell, `irm`/`iwr` piped into `iex`, raw GitHub URLs on `main`/`master`/`HEAD`, `git+https` without `@ref`, unversioned `astral.sh/uv/install.*`, unversioned `uv tool install specify-cli`, and `uses:` without a 40-character SHA. The rule goes only in FishDev's own `rules.json`. Adopters' workflows are their own policy, so `defaults/rules.json` is unchanged.
9. **Installer structure.** `install.sh` becomes functions: preflight, stage and verify, uv, SpecKit, write, init. It runs `main` unless `FISHDEV_INSTALL_LIBRARY=1`, so tests can source it. `FISHDEV_SOURCE` can point FishDev files at another `https://` or `file://` base for testing, with the same digests enforced. Hashing uses `sha256sum` or `shasum -a 256`. The script stays compatible with macOS's bash 3.2.
10. **Line endings.** `.gitattributes` pins shipped files to LF so a Windows maintainer's checkout computes the same digests as the published bytes.

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
