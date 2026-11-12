# Tasks: Verification, executable constraints, and retrospective learning

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Specification and contracts

- [x] **T001** Record the three user stories, acceptance cases, scope, and phased plan in this specification.
- [x] **T002** Choose and document the versioned verification, rule, result, correction-event, and proposal contracts; validate Bash and native Windows feasibility and dependency tradeoffs.

## US1 — Project verification (P1)

- [x] **T003** Add failing fixture tests for required failures, missing commands, invalid profiles, deliberate skips, browser interactions, performance budgets, and local/CI parity.
- [x] **T004** Implement the project verification runner and machine-readable plus human-readable results under the agreed `.config/ai/` contract.
- [x] **T005** Add a usable FishDev verification profile and an adoptable starter profile for initialized projects.
- [x] **T006** Document the single local command, category applicability, artifact handling, and CI invocation; validate the US1 scenarios.

## US2 — Executable architectural constraints (P2)

- [x] **T007** Add failing fixture tests for vendor-neutrality and configurable dependency-boundary rules, rule exceptions, advisory coverage, and stable diagnostics.
- [x] **T008** Implement the rule checker and initial policies; integrate blocking checks into verification.
- [x] **T009** Document rule authoring, constitutional coverage, scoped exceptions, and migration of existing violations; validate the US2 scenarios.

## US3 — Retrospective learning (P3)

- [x] **T010** Add failing fixture tests for two-session recurrence, single events, missing history, duplicate runs, proposal disposition, and secret redaction.
- [x] **T011** Implement local evidence extraction, optional vendor-neutral session import, recurrence grouping, and reviewable proposal generation without automatic policy edits.
- [x] **T012** Document evidence limits, retention, human review workflow, and optional AI data sharing; validate the US3 scenarios.

## Integration and closeout

- [x] **T013** Update `install.sh`, `start.ai`, setup documentation, README, and Windows guide as required so new and existing projects can discover the capabilities.
- [x] **T014** Demonstrate the same verification behavior locally and in CI, run relevant tests and syntax checks, and record outcomes and decisions in `.config/ai/progress.ai`.
