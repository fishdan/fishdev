# Feature Specification: Pinned and integrity-verified installer downloads

**Feature Branch**: `specs/0.005-installer-download-integrity`

**Created**: 2026-11-16

**Status**: Specified

## Problem

Every FishDev installation path downloads code from mutable locations and trusts it without verification. Both the 2026-10-13 and 2026-11-12 monthly audits recorded this as candidate work.

| Download | Current source | Gap |
| --- | --- | --- |
| FishDev bootstrap | `curl …/main/install.sh \| bash` (README) | Branch head; piped straight into a shell |
| FishDev workflow files (7) | `raw.githubusercontent.com/fishdan/fishdev/main/…` in `install.sh` and the Windows guide | Branch head; no checksum; partial installs possible on failure |
| uv | `curl https://astral.sh/uv/install.sh \| sh` (`install.sh`, `fishdev-init.md`); `irm …/install.ps1 \| iex` (Windows guide) | Latest installer piped into a shell; installs whatever uv version is current |
| SpecKit | `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git` (`install.sh`, `fishdev-init.md`); `uv tool install specify-cli` (Windows guide) | Default branch or latest release; the Bash and Windows paths can install different versions |
| CI actions | `actions/checkout@v4`, `actions/setup-python@v5` | Movable major-version tags |

So two installs a minute apart can receive different code. A changed upstream, a compromised CDN path, or a truncated transfer goes undetected, and a failed download can leave a half-installed project behind.

## Scope and boundaries

Pin every download that a FishDev installation path or FishDev's own CI performs to an immutable or explicitly versioned reference. Verify content against a recorded digest wherever the source allows it, and fail closed on any mismatch. Keep the Bash and native Windows paths equivalent. Give maintainers one documented, checkable way to update pins, and make verification catch drift or new unpinned downloads.

**Threat model.** This work defends against mutable upstream references, accidental drift between files, tampering or corruption in transit or in caches, and silent partial installs. It does not defend against compromise of the FishDev GitHub repository or the maintainer's account: digests published from the same repository share that trust root. That limit must be documented, not implied away.

## User scenarios and acceptance

### US1 — Verified FishDev install (P1)

As a developer installing FishDev, I get exactly the reviewed FishDev release. If any file is altered, missing, or truncated, the install stops before changing my project.

**Independent test**: Serve a fixture FishDev source from a local directory. Run the installer once against correct content, then once with one byte of one file changed. The first run installs every file. The second exits nonzero, names the failing file and both digests, and leaves the target directory as it was.

1. Given a published FishDev release, when the installer runs, then every FishDev file comes from an immutable reference for that release and matches its recorded SHA-256 digest before anything is written into the project.
2. Given any digest mismatch, missing file, or failed transfer, when the installer runs, then it exits nonzero, reports the file with expected and actual digests, and writes no FishDev files, pointer files, or state files into the project.
3. Given the README or Windows guide, when a developer follows it, then the documented path downloads the bootstrap from a pinned release, lets the developer check its digest, and runs it only after that check passes. Piping a moving branch head into a shell is no longer the documented default.
4. Given a target system without a supported SHA-256 tool, when the installer runs, then it stops with a message naming the missing tool rather than skipping verification.

### US2 — Pinned third-party tools (P2)

As a developer, I get the same uv and SpecKit versions that the FishDev release was validated with, on Linux, macOS and Windows.

**Independent test**: Run the uv and SpecKit steps with a fixture or stubbed source. Confirm that a version-pinned reference is requested, a mismatched installer digest stops the run, and the Bash and PowerShell paths name the same versions.

1. Given uv is absent, when the installer installs it, then it uses a versioned uv installer or release artifact and verifies its digest before running it.
2. Given uv is already installed, when the installer runs, then it does not replace it, and it reports the found version. An unsupported minimum version is reported, not silently used.
3. Given SpecKit installation, when the installer runs, then it installs a pinned SpecKit version identified by an immutable reference (a released version or a full commit identifier), and the Bash and Windows paths install the same version.
4. Given FishDev's CI workflow, when it runs, then every third-party action is pinned to a full commit SHA, with the human-readable version recorded beside it.

### US3 — Maintainable pins (P3)

As a FishDev maintainer, I update the FishDev manifest or a third-party pin with one documented procedure. Verification fails if pins drift from the files they describe or if someone adds an unpinned download.

**Independent test**: Edit a tracked FishDev workflow file without regenerating the manifest and confirm verification fails. Regenerate and confirm it passes. Add `curl -fsSL https://example.com/x.sh | sh` to an installer fixture and confirm the rule check reports it.

1. Given a change to any file the installer downloads, when the manifest has not been regenerated, then `fishdev.py verify` fails, naming the stale entry.
2. Given the documented update procedure, when a maintainer runs it, then the manifest and pins are regenerated deterministically, and running it again produces no diff.
3. Given a new download command in the installer, setup guides, or CI workflow that uses a mutable reference or pipes remote content into a shell, when `fishdev.py check` runs, then a stable rule ID reports the file and line.
4. Given the monthly security audit, when it runs, then it reviews the recorded third-party pins for known vulnerabilities and newer releases, and records the outcome in progress history.

## Functional requirements

### FishDev content

- **FR-001**: FishDev MUST publish a versioned manifest listing every file an installation path downloads, with its repository path, install destination, and SHA-256 digest.
- **FR-002**: Installation paths MUST fetch FishDev files from an immutable reference tied to the manifest (for example a release tag's assets or a full commit SHA). They MUST NOT fetch from a branch head by default.
- **FR-003**: Installers MUST download all files to a temporary location, verify every digest, and only then write into the project. Any failure MUST exit nonzero, leave the project unchanged, and remove the temporary files.
- **FR-004**: Digest checks MUST be available on the Bash path for Linux and macOS (`sha256sum` or `shasum -a 256`) and on the Windows path (`Get-FileHash`). A missing tool MUST stop the install.
- **FR-005**: The documented bootstrap MUST be download, verify, then run, using a pinned release with a published SHA-256 digest. A one-line convenience command MAY remain if it points at a pinned release and is documented as unverified.
- **FR-006**: The installer MUST support a local or alternate source location for testing that applies the same verification as a normal install.

### Third-party tools

- **FR-007**: The uv installer MUST be pinned to a specific version and its digest verified before execution on both paths, or replaced by a verified, versioned uv release artifact. An existing uv installation MUST be reported and respected.
- **FR-008**: SpecKit MUST be installed at one recorded version from an immutable reference, the same on Bash and Windows. Planning MUST decide whether to also constrain SpecKit's transitive Python dependencies and record why.
- **FR-009**: Every third-party GitHub Action in FishDev's workflows MUST be pinned to a full commit SHA with its version noted.
- **FR-010**: Each third-party pin MUST have one authoritative recorded location, with version, reference, digest where applicable, source URL, and date reviewed, so installers, guides, and audits agree.

### Maintenance and enforcement

- **FR-011**: FishDev MUST provide a deterministic, documented procedure to regenerate the manifest and digests. The procedure MUST work without network access for FishDev's own files.
- **FR-012**: `fishdev.py verify` for FishDev MUST fail when the manifest or embedded digests do not match the tracked files.
- **FR-013**: `fishdev.py check` MUST include a rule with a stable ID that reports download commands in the installer, setup guides, and CI workflows that pipe remote content into a shell or use a mutable reference. Approved exceptions follow the existing narrow, expiring exception contract.
- **FR-014**: `start.ai`'s monthly security audit MUST include reviewing recorded third-party pins.
- **FR-015**: Documentation MUST state the threat model and limits from this spec, how a user verifies a bootstrap download, and how maintainers cut a release and update pins.

### Validation

- **FR-016**: Tests MUST cover a correct install, a single-file digest mismatch, a missing file, an interrupted transfer, a missing hash tool, a stale manifest, and an unpinned-download rule violation. Results MUST be recorded in `.config/ai/progress.ai`.

## Key entities

- **Release manifest**: Format version, FishDev release identifier, immutable source reference, and an entry per file: path, destination, SHA-256.
- **Third-party pin**: Tool, version, immutable reference, digest (where applicable), source URL, review date.
- **Bootstrap digest**: SHA-256 of the installer for a release, published with release notes and documentation.

## Edge cases

- `raw.githubusercontent.com` or release-asset caches briefly serve stale content after a release: an immutable reference avoids this, and a mismatch fails clearly rather than installing mixed versions.
- A user runs the installer twice, or in a project with an earlier FishDev install: the behavior for existing files is explicit, not a silent overwrite of local edits. Planning decides whether upgrades are in scope.
- uv is already installed at an old version: it is reported. FishDev does not silently replace a user-managed tool.
- A maintainer edits `start.ai` but forgets to regenerate the manifest: CI fails on the drift check before merge.
- Upstream removes a pinned version or tag: the install fails with a message naming the pin, and the audit records the needed update.
- The installer itself cannot verify its own digest: the documented bootstrap check covers it, and the documentation says so.

## Success criteria

- **SC-001**: No installation path or FishDev CI workflow fetches from a branch head, a moving tag, or an unversioned installer by default, confirmed by the new rule passing on FishDev's own repository.
- **SC-002**: In fixtures, any single-byte change to any downloaded FishDev file stops the install and leaves the target directory byte-for-byte unchanged.
- **SC-003**: The Bash and Windows paths name the same FishDev release, uv version, and SpecKit version, drawn from one recorded source.
- **SC-004**: A tracked change to a downloaded file without regenerating the manifest fails `fishdev.py verify`. Regenerating makes it pass, and a second regeneration produces no diff.

## Assumptions and decisions to validate during planning

- FishDev will publish tagged releases. Planning selects the release identifier, where the manifest and bootstrap digest live, and whether installers fetch release assets or commit-SHA raw URLs.
- uv's versioned installers and release checksums, and SpecKit's tags or PyPI releases, are stable enough to pin. Planning confirms the current URLs and formats from official sources and picks initial versions.
- The existing Python 3.11 standard-library runner can host the manifest generator and drift check without a new dependency.
- Native Windows execution remains unavailable in this environment. PowerShell logic needs a documented gap or an alternate validation path.

## Out of scope

- Cryptographic signing of releases (Sigstore, GPG, or GitHub attestations). Record it as a candidate follow-up.
- Defending against compromise of the FishDev repository or maintainer accounts.
- Dependency pinning for projects that adopt FishDev; that belongs to each project's own verification profile.
- Changing what FishDev installs, beyond how it is fetched and verified.
