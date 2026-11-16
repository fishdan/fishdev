# Tasks: Pinned and integrity-verified installer downloads

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Specification and design

- [x] **T001** Record the download inventory, threat model, user stories, acceptance cases, and scope in this specification.
- [x] **T002** Resolve the plan's design decisions (source reference, manifest and pin formats, uv and SpecKit pinning methods and initial versions, upgrade behavior, rule pattern) from official sources, and record them in the plan.

## US3 foundation — Manifest, pins, and drift check (P3)

- [x] **T003** Add failing tests for manifest generation determinism, stale-manifest detection, and pin-record validation.
- [x] **T004** Implement the manifest generator, pin record (`.config/ai/release.json`), and drift check in the maintainer-only `.config/ai/tools/release.py`, and add the drift check to FishDev's verification profile.

## US1 — Verified FishDev install (P1)

- [x] **T005** Add failing installer fixture tests using a local source: correct install, single-file mismatch, missing file, interrupted transfer, missing hash tool, and an unchanged target directory after each failure.
- [x] **T006** Rework `install.sh` to stage downloads, verify SHA-256 digests on Linux and macOS, write only after all checks pass, and clean up on failure.
- [x] **T007** Update the Windows guide to stage, run `Get-FileHash`, and write only after all checks pass. Publish the download-verify-run bootstrap instructions in the README and Windows guide.

## US2 — Pinned third-party tools (P2)

- [x] **T008** Pin and verify the uv installer on both paths. Respect and report an existing uv.
- [x] **T009** Pin SpecKit to one immutable version on both paths, update `fishdev-init.md`, and record the transitive-dependency decision.
- [x] **T010** Pin `.github/workflows/verify.yml` actions to full commit SHAs, with their versions noted.

## US3 enforcement and closeout

- [x] **T011** Add the unpinned-download rule with failing and passing fixtures. Make FishDev's repository pass it.
- [x] **T012** Add pin review to `start.ai`'s monthly security audit. Document the threat model, bootstrap verification, and the release and pin-update procedure.
- [ ] **T013** (Pre-release validation done; tag `v0.5.0` and the install from the published tag await merge.) Cut the first FishDev release. Run an end-to-end install from it in a clean directory, run the tests and local and CI verification, and record the outcomes in `.config/ai/progress.ai`.
