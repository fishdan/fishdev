# Verification, rules, and retrospective learning

FishDev stores the workflow in `.config/ai/` and runs it with Python 3.11 or newer. It uses only the Python standard library. From the project root:

```sh
python .config/ai/tools/fishdev.py verify
python .config/ai/tools/fishdev.py check
python .config/ai/tools/fishdev.py retro
```

On systems where the executable is named `python3`, use `python3`. In CI, run `python .config/ai/tools/fishdev.py verify --ci`; `--ci` changes only the report label, not check behavior or exit status. FishDev's own CI workflow is in `.github/workflows/verify.yml`.

For a GitHub Actions project, a minimal job after checkout and Python setup is:

```yaml
- run: python .config/ai/tools/fishdev.py verify --ci
```

Install any stack-specific build, browser, or security tools before this step. Other CI systems can invoke the same command.

## Configure verification

`.config/ai/verification.json` has `version: 1` and an ordered `steps` array. Declare at least one step for each category: `build`, `tests`, `browser`, `security`, and `performance`. Additional categories are allowed. Each step has a unique lowercase `id`, `category`, `applicability`, and `failure_policy`.

| Field | Meaning |
| --- | --- |
| `applicability` | `required`, `conditional`, or `inapplicable`. |
| `command` | Argument array for an applicable step. `{python}` uses the current Python interpreter. Commands run from the project root without a shell. |
| `failure_policy` | `blocking` makes failure fail verification; `advisory` reports failure without changing the final exit code. |
| `reason` | Required for `inapplicable` and `conditional` steps; shown on skip. |
| `when_env` | Required for `conditional`; run only when this environment variable is nonempty. |
| `timeout_seconds` | Optional positive number up to 3600; default 300. |
| `max_value`, `unit` | Required for an applicable `performance` step. Its command prints a numeric measurement on the last output line; values over the budget fail. |

For example, a web project can run a headless browser script using `command: ["{python}", "tests/browser_flow.py"]`. The script must perform the actual interaction and exit nonzero on failure. Install the browser and its runtime in both local and CI environments. Configure a performance command that measures a representative flow and prints one numeric result; set a project-specific threshold. A non-web project can mark `browser` inapplicable with a reason. A new installation starts with failing placeholders where the project stack cannot be inferred. Replace each placeholder or mark genuinely irrelevant categories inapplicable. Never mark a missing required check as inapplicable to make verification green.

The starter security step runs FishDev's architectural rule checker. Add a stack-specific dependency vulnerability scan and other relevant security checks as separate `security` steps. FishDev's monthly vulnerability audit remains part of `start.ai`; the rule checker alone is not a dependency audit.

The runner executes every step in order, reports pass/fail/skip with timing, and exits nonzero for a blocking failure or invalid profile. Missing executables and timeouts fail visibly. Logs are capped at 64 KiB per step and saved under `.config/ai/reports/`, along with `verification.json`. The report contains step IDs, category, status, elapsed time, identity, diagnostic or artifact path, and policy. Reports are ignored by Git; inspect and delete them according to your project's retention policy. Environment-specific URLs and credentials belong in environment variables or a secret manager, never in the profile. Log redaction handles common token and email patterns but cannot guarantee removal of every secret; avoid printing secrets from commands.

## Write executable constraints

`.config/ai/rules.json` has `version: 1`, `rules`, `exceptions`, and `advisory_principles`. Every rule needs a stable `id`, `principle`, `kind`, `severity` (`error` or `warning`), `message`, and `remediation`.

- `forbid_paths` checks repository-relative paths against `paths` glob patterns.
- `forbid_text` checks lines in files selected by `files` globs against a regular expression in `pattern`. It can express a concrete dependency boundary, such as forbidding production modules from importing test modules.

`check` lists every violation with rule ID and location. Errors return nonzero; warnings remain visible. It also lists covered rules and advisory principles. This is a coverage declaration, not a claim that broad qualities such as Clean Code can be checked mechanically. Repeat runs over the same files and rules produce the same diagnostics.

An exception is an object with `rule`, exact repository-relative `path`, `reason`, `reviewer`, and ISO `expires` date. Wildcard paths, missing review context, and expired exceptions are invalid. Use an exception only after a maintainer approves the specific legacy violation; record the migration task in progress history. Rules apply to current repository contents, so introducing one into an existing project may reveal a baseline that must be fixed or reviewed.

## Run a retrospective

`retro` reads `.config/ai/progress.ai`, `.config/ai/handoff.ai`, and optionally `.config/ai/local/sessions.jsonl`. It recognizes explicit project-history entries of this form:

```text
- Human correction [session-2026-11-12-a] (script): Run the project verifier before declaring completion
```

An optional vendor-neutral JSONL import has one object per line:

```json
{"kind":"correction","session":"session-1","target":"verification","correction":"Run the project verifier before declaring completion"}
```

`target` is `rule`, `script`, `skill`, or `verification`. Other JSONL event kinds are ignored. Use `retro --events path/to/file.jsonl` to read a different import. Raw imports and generated reports belong under `.config/ai/local/` and stay untracked. Do not import secrets or unnecessary personal data.

The local retrospective groups corrections by target and normalized wording. Two distinct session IDs are required for a proposal; a single correction is stored as an observation. Semantically equivalent corrections with different wording may need a human to consolidate them in the project record. The verification profiles also run `retro` as an advisory `learning` step, so each verification pass rechecks available records. Proposals are stored in `.config/ai/learning/proposals.json` with evidence references, a candidate change, impact, validation plan, and disposition. Rerunning updates evidence without duplicating proposals or overwriting `accepted`, `rejected`, or `superseded` status. The file is ignored by Git by default; review and redact it before explicitly adding it to project history. Delete local reports and imports when their review is complete. The tool never changes rules, scripts, skills, or verification configuration; adoption requires a normal spec, task, implementation, and verification. No project data is sent to an AI service.
