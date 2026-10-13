# Fix installer syntax

## Problem

`bash -n install.sh` fails because the final `echo` has an unmatched double quote. Bash cannot parse the installer.

## Scope

Close the final string without changing the installer's steps or output text.

## Acceptance criteria

- `bash -n install.sh` succeeds.
- The final startup instruction is printed as intended.
- The fix and validation are recorded in `.config/ai/progress.ai`.
