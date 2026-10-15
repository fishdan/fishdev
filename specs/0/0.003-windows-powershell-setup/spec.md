# Windows setup in VS Code with PowerShell

## Problem

The README shows only a Bash installation command. Windows users need native PowerShell steps they can run from VS Code without WSL or Git Bash.

## Scope

Document prerequisites, FishDev file setup, SpecKit installation and initialization, verification, and the first AI session. Link the guide from the README. Keep `.config/ai/` authoritative and avoid vendor-specific integration files.

## Acceptance criteria

- A user can follow the guide from VS Code's PowerShell terminal in an existing project that has not already been initialized with FishDev or SpecKit.
- Commands use PowerShell syntax and initialize SpecKit with PowerShell scripts.
- Existing FishDev/SpecKit state is protected from accidental overwrite.
- The guide names its Windows-only validation limits and links official prerequisites.
- Documentation and validation are recorded in `.config/ai/progress.ai`.
