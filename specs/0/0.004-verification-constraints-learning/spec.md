# Feature Specification: Verification, executable constraints, and retrospective learning

**Feature Branch**: `specs/0.004-verification-constraints-learning`

**Created**: 2026-11-12

**Status**: Implemented (native Windows execution not yet validated)

## Problem

FishDev requires testing, a constitution, and a progress log, but an initialized project has no standard way to run and report its verification work. The constitution states architectural principles without a deterministic enforcement path. Progress and handoff records preserve history, but the workflow does not turn repeated agent corrections into proposed improvements.

## Scope and boundaries

Build three vendor-neutral capabilities that work together in repositories initialized by FishDev and in FishDev itself:

1. A project-defined verification workflow with one documented local command and the same behavior in CI. Projects declare relevant build, test, browser, security, and performance steps. Applicability is explicit; a non-web project need not invent browser tests.
2. Executable architectural constraints tied to named constitutional or project rules. Only objectively checkable rules become blocking checks. Qualitative guidance such as “Clean Code” remains guidance unless a concrete, testable invariant is defined.
3. A retrospective command that examines available project history, detects repeated human corrections, and drafts evidence-backed changes to rules, scripts, or skills for human review.

Include installation/adoption, documentation, and startup guidance. Keep `.config/ai/` authoritative and vendor-specific files limited to pointers. No agent may silently change governing rules or execute a generated proposal. The initial implementation does not need a remote service or a particular AI provider.

## User scenarios and acceptance

### US1 — Run project verification (P1)

As a developer or agent, I run one project command and see whether the configured checks passed, failed, or were deliberately inapplicable. I can run the same command in CI.

**Independent test**: Configure a fixture project with a passing build, a failing test, and an inapplicable browser step. Run locally and in CI mode; compare status, step ordering, and exit behavior.

1. Given a configured project, when verification runs, then every applicable required step executes and a failing required step makes the overall result fail.
2. Given a step marked inapplicable with a reason, when verification runs, then the report shows the reason and does not present the step as passed.
3. Given a required step with a missing command or unavailable tool, when verification runs, then the report names the missing prerequisite and fails rather than silently skipping it.
4. Given a web project with a browser interaction and a performance budget, when the interaction or budget fails, then verification fails with actionable evidence.

### US2 — Enforce concrete project rules (P2)

As a maintainer, I map an architectural rule to an objective check. Developers and CI receive the same diagnostics before a prohibited change lands.

**Independent test**: In a fixture repository, introduce a forbidden vendor-specific workflow file and a forbidden dependency edge; confirm both fail, then remove them and confirm both pass.

1. Given a rule with a stable ID, scope, check, and diagnostic, when a violation is present, then the checker identifies the rule and offending location and returns a failing status.
2. Given an approved, documented exception, when the checker runs, then it identifies the exception and its scope; an expired or malformed exception fails.
3. Given a constitutional sentence with no objective check, when policies are listed, then the tool does not claim that sentence is enforced.

### US3 — Learn from repeated corrections (P3)

As a maintainer, I request a retrospective and receive reviewable proposals for recurring corrections, with links to the source evidence and a concrete candidate change.

**Independent test**: Supply two separate session records that contain the same human correction and a third unrelated record; confirm one deduplicated proposal with both evidence references and no automatic rule edit.

1. Given at least two independent correction events with the same underlying issue, when the retrospective runs, then it proposes a rule, script, skill, or verification change and cites both events.
2. Given only one correction or ambiguous evidence, when it runs, then it records an observation or uncertainty without proposing a blocking rule.
3. Given records containing secrets or personal details, when it writes a proposal, then those details are excluded or redacted.
4. Given an existing proposal for the same issue, when it runs again, then it updates or references the existing proposal rather than opening a duplicate.

## Functional requirements

### Verification

- **FR-001**: FishDev MUST define a versioned, documented project verification configuration under `.config/ai/` and provide a single entry point for running it.
- **FR-002**: The configuration MUST support build, automated tests, browser interaction, security checks, performance validation, and project-defined steps, with command, applicability, and failure policy for each configured step.
- **FR-003**: Each standard category MUST be declared as required, conditionally applicable, or inapplicable with a reason. An absent or invalid declaration MUST be reported; it MUST NOT be treated as a pass.
- **FR-004**: The runner MUST use the same configuration, step semantics, and exit status locally and in CI. Environment-specific inputs such as secrets and service URLs MAY be supplied externally.
- **FR-005**: A result MUST include step ID, category, status (pass/fail/skip), elapsed time, command or check identity, and a diagnostic or artifact location on failure. Reports MUST distinguish a deliberate skip from a pass.
- **FR-006**: Required check failures, missing commands, invalid configuration, and unavailable prerequisites MUST produce a nonzero exit status. Optional checks and exceptions MUST be explicit in configuration and visible in reports.
- **FR-007**: Browser checks MUST execute actual scripted interactions when configured, with a documented headless CI path. Performance checks MUST compare measured results with project-defined thresholds or baselines; FishDev MUST NOT impose a universal performance budget.
- **FR-008**: FishDev's installer/adoption path and documentation MUST create or explain a working verification starting point for the target project's stack, with explicit placeholders where commands cannot be inferred. FishDev's own repository MUST have a usable verification workflow.

### Executable constraints

- **FR-009**: FishDev MUST provide a deterministic constraint checker using a versioned, project-owned rule definition under `.config/ai/`, and make it runnable as part of verification and directly by a developer.
- **FR-010**: Each executable rule MUST have a stable ID, source principle or policy reference, objective condition, scope, severity, and diagnostic with remediation guidance.
- **FR-011**: The checker MUST report the rule ID and offending file or item for each violation, return nonzero for blocking violations, and produce the same result for the same repository contents and rule configuration.
- **FR-012**: The initial rule set MUST include at least a FishDev vendor-neutrality rule and one configurable architectural boundary rule, both demonstrated by failing and passing fixtures.
- **FR-013**: Rule exceptions MUST be narrow, documented, reviewable, and time-bounded. A missing reason, overbroad scope, or expired exception MUST fail validation.
- **FR-014**: The checker MUST list which constitutional principles have executable coverage and which remain advisory. It MUST NOT represent subjective code quality as deterministically enforced.

### Retrospective learning

- **FR-015**: FishDev MUST provide an on-demand retrospective command that reads authorized project records, including `.config/ai/progress.ai` and `.config/ai/handoff.ai`, plus optionally imported session records in a documented vendor-neutral format. It MUST operate usefully when no session transcript is available.
- **FR-016**: Each candidate repeated correction MUST cite at least two independent events or sessions, state the recurring failure and suggested prevention, and identify whether the suggestion belongs in a rule, script, skill, or verification step.
- **FR-017**: A proposal MUST contain evidence references, a concise rationale, a concrete candidate change or patch, likely impact, and a validation plan. Uncertain matches MUST be labeled for review rather than turned into enforcement automatically.
- **FR-018**: Running a retrospective MUST NOT directly change the constitution, rule definitions, scripts, skills, or verification configuration. Applying a proposal requires normal SpecKit scope, review, and validation.
- **FR-019**: The command MUST avoid duplicate open proposals for the same underlying correction and MUST preserve a disposition such as proposed, accepted, rejected, or superseded.
- **FR-020**: The command MUST keep source records local by default, avoid collecting credentials, and redact or exclude secrets and unnecessary personal data from proposal artifacts. If optional AI analysis is used, its provider and data-sharing behavior MUST be explicit and opt-in.

### Integration

- **FR-021**: Startup and project documentation MUST tell agents when to run verification, how to interpret failures, and when to request a retrospective. CI integration MUST be documented and demonstrated.
- **FR-022**: All three capabilities MUST be vendor-neutral and keep durable configuration, evidence, and proposals in repository-owned locations. Generated artifacts that may contain sensitive data MUST have a documented retention and git-ignore policy.
- **FR-023**: The implementation MUST include meaningful tests for valid, invalid, failing, skipped, and repeated-run cases and record validation outcomes in `.config/ai/progress.ai`.

## Key entities

- **Verification profile**: Version, project context, ordered checks, applicability, and failure policies.
- **Verification result**: Run identity and per-check status, timing, diagnostics, and evidence paths.
- **Executable rule**: Stable ID, policy source, objective condition, scope, severity, and remedy.
- **Rule exception**: Rule ID, narrow scope, reason, owner or reviewer, and expiration.
- **Correction event**: Source reference, session or event identity, correction, and affected behavior.
- **Learning proposal**: Repeated issue, evidence, candidate change, impact, validation, disposition, and deduplication identity.

## Edge cases

- A new project has no test suite, browser surface, security scanner, or performance benchmark yet: the profile requires an honest declaration and records missing required work as a failure.
- A verification command hangs or emits a large log: the runner bounds execution and report size while preserving a diagnostic artifact.
- A rule is added to a repository with existing violations: baseline or migration decisions are explicit, scoped, and visible; new violations are not silently hidden.
- A correction appears in two records from the same session: it counts as one event for recurrence.
- Session records are missing, incomplete, inaccessible, or inconsistent: the retrospective states the evidence limit and does not invent history.
- A generated report contains sensitive output: the documented artifact policy controls local storage, redaction, and source-control exclusion.

## Success criteria

- **SC-001**: A fresh FishDev project can discover the verification command and explicitly account for all five standard categories without undocumented setup.
- **SC-002**: In fixtures, every required failing or missing check produces a nonzero result, and every deliberate skip is visibly marked with a reason in both local and CI runs.
- **SC-003**: The two initial executable rules each catch a planted violation, show the same diagnostic on repeated runs, and pass once the violation is removed.
- **SC-004**: A two-session repeated correction yields one reviewable proposal with two evidence references; a single correction yields no enforcement proposal; rerunning creates no duplicate.
- **SC-005**: The workflow works without an AI provider or a hosted service, and no proposal modifies governing files until reviewed through a normal spec/task.

## Assumptions and decisions to validate during planning

- The user asked for one feature branch and one coordinated spec; implementation can be delivered in the three independently testable slices above.
- Projects may use different stacks. The configuration defines a common contract while each project supplies its own commands, browser scripts, security tools, and performance budgets.
- Retroactive access to provider session transcripts is not guaranteed. Local project records are the baseline; optional transcript import is explicit and provider-neutral.
- Native Windows use is part of FishDev's documented setup path. The implementation plan must choose a runner and test strategy that preserve equivalent behavior there.

## Out of scope

- Automatically repairing code or approving learning proposals.
- Claiming deterministic enforcement of every Clean Code principle.
- Sending project history to an external AI service by default.
- Creating a browser test or performance budget for a project that has no relevant surface or baseline.
