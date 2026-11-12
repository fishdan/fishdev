# Implementation Plan: Verification, executable constraints, and retrospective learning

**Branch**: `specs/0.004-verification-constraints-learning` | **Date**: 2026-11-12 | **Spec**: [spec.md](spec.md)

## Summary

Deliver one project-owned verification contract, a deterministic constraint checker, and an on-demand retrospective that drafts reviewable improvements. Implement and validate each user story independently, then wire them into FishDev installation, startup, and CI guidance.

## Current context

- FishDev is a Bash installer and Markdown/SpecKit workflow, with documented native PowerShell setup.
- `install.sh` currently downloads startup and init instructions, creates `.config/ai/` state files, installs SpecKit, and copies the default constitution. There is no verification runner or rule checker today.
- `start.ai` is the only session entry point. `fishdev-init.md` is setup guidance and should change only if installation behavior changes.
- `.config/ai/progress.ai` and `.config/ai/handoff.ai` are available, but neither has a structured correction event format.
- No application dependency manifest or test framework exists in this repository.

## Design decisions to resolve before implementation

1. Select a small, versioned configuration format and parser/runner that works on the documented Bash and native Windows paths. Record dependency and platform tradeoffs before adding a runtime.
2. Define status, applicability, timeout, evidence, and exit-code contracts. An incomplete profile must fail clearly; every standard category must have a stated disposition.
3. Define rule types narrow enough for deterministic results. Start with vendor-neutral workflow placement and configurable dependency boundaries; keep constitutional coverage honest.
4. Define a local correction-event and proposal format. Use project records as the baseline; allow optional imported transcripts only through an explicit, documented path.
5. Choose proposal storage and deduplication so repeated runs preserve reviewer decisions without committing raw session logs or secrets.

## Constitution check

- **Spec-driven**: This spec and [tasks.md](tasks.md) precede implementation. Each future change must map to a task and progress entry.
- **AI neutrality**: Authoritative configuration and proposal state live under `.config/ai/`; any vendor integration is a pointer or optional adapter.
- **Testing/local and CI**: Each story has an independent fixture test and the same verification contract in local and CI environments.
- **Security/reproducibility**: No default external transcript upload; dependencies and artifact retention must be documented before use.
- **Narrow scope**: The three requested capabilities and their installation/documentation paths are in scope. General installer hardening and unrelated refactoring are separate work.

## Delivery sequence

1. Finalize the config and result contracts, with fixtures covering a non-web project and a web project.
2. Implement and test verification. Give FishDev itself a usable profile, then document how another project adopts it.
3. Implement and test executable constraints, and add the checker to verification.
4. Implement and test local retrospective proposals, including recurrence, redaction, and repeated-run behavior.
5. Update installer/startup/README/Windows setup as needed; demonstrate local and CI behavior; record results in progress history.

## Validation gates

- Run contract and fixture tests for each story, including failure paths.
- Run FishDev's own verification command from a clean checkout and a CI-like environment.
- Run shell syntax checks and relevant native PowerShell checks where available; document any platform gap.
- Check that no raw session transcript or generated sensitive artifact is tracked and that `git diff --check` passes.

## Risks

- A generic “Clean Code” checker would overclaim coverage; require an objective invariant and report advisory principles separately.
- Optional scanners and browser tools differ across stacks; distinguish inapplicable from required-but-missing.
- Session records may not preserve human corrections. The retrospective must disclose missing evidence rather than infer recurrence.
