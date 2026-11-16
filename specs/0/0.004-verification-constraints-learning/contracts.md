# Version 1 contracts

All durable configuration is project-owned JSON under `.config/ai/`. Python 3.11+ is the runtime on Bash and native Windows paths; the implementation uses only the standard library. `docs/verification-and-learning.md` is the operator guide.

## Verification profile and result

`.config/ai/verification.json` is `{ "version": 1, "steps": [...] }`. Each step has `id`, `category`, `applicability`, and `failure_policy`. Applicable steps have an argv-style `command`; inapplicable steps have `reason`; conditional steps also have `when_env`. Performance steps have `max_value` and `unit`. A missing standard category or malformed step is an error. `{python}` is substituted with the running interpreter. Every command runs from the project root without a shell, and has a default 300-second timeout.

`.config/ai/reports/verification.json` is generated and ignored by Git. It has `version`, `mode` (`local` or `ci`), `status`, and ordered `steps`. Each result has `id`, `category`, `status` (`pass`, `fail`, `skip`), `failure_policy`, `elapsed_seconds`, `identity`, and optional `diagnostic`, `artifact`, `measurement`, and `unit`. A blocking failure returns exit code 1; invalid configuration returns 2; otherwise the runner returns 0. The mode label does not change step behavior.

## Rules and exceptions

`.config/ai/rules.json` is `{ "version": 1, "rules": [...], "exceptions": [...], "advisory_principles": [...] }`. A rule has `id`, `principle`, `kind`, `severity`, `message`, and `remediation`. `forbid_paths` uses `paths` globs; `forbid_text` uses `files` globs plus a line regular expression in `pattern`. Paths are repository-relative. A rule exception has `rule`, exact `path`, `reason`, `reviewer`, and `expires` as an ISO date. Invalid or expired exceptions produce exit code 2. Blocking violations return 1. The rule list itself declares only the constitutional coverage it actually implements.

## Corrections and proposals

Project history can contain `- Human correction [session-id] (target): correction text`, where `target` is `rule`, `script`, `skill`, or `verification`. Optional `.config/ai/local/sessions.jsonl` records have `kind: correction`, `session`, `target`, and `correction`. The import is local and ignored by Git. Grouping uses the same target and normalized correction wording; at least two distinct sessions are needed for a proposal.

`.config/ai/learning/proposals.json` is `{ "version": 1, "proposals": [...], "observations": [...] }`. Each proposal has a stable ID derived from target and issue, `status`, `target`, `issue`, `evidence`, `rationale`, `candidate_change`, `likely_impact`, and `validation_plan`. Existing dispositions are preserved on reruns. Single-session groups are retained as observations with target, issue, and evidence. The retrospective never edits rules, scripts, skills, or verification profiles. This file is ignored by Git by default; review and redact it before explicitly adding it to project history.
