# Set up FishDev on Windows in VS Code

These steps use the **PowerShell terminal in VS Code**. WSL and Git Bash are not required. Use a project folder that has not already been initialized with FishDev or SpecKit; the commands below add workflow files to that folder.

## 1. Prepare the project

Install [VS Code](https://code.visualstudio.com/download) and [Git for Windows](https://git-scm.com/download/win). Open your project folder with **File > Open Folder**, then open **Terminal > New Terminal**. If the terminal is not PowerShell, use **Terminal: Select Default Profile** from the Command Palette and choose PowerShell, then open a new terminal. VS Code documents [terminal setup](https://code.visualstudio.com/docs/terminal/getting-started) and [profile selection](https://code.visualstudio.com/docs/terminal/profiles).

Check that the terminal is in the project root and Git is available:

```powershell
Get-Location
git --version
git status --short
```

If this is a new folder and `git status` says it is not a repository, run `git init`. Commit or back up existing work before adding SpecKit to a project with files. Stop if this folder already contains `start.ai`, `.config/ai`, or `.specify`; this guide is for a first installation.

## 2. Install uv and SpecKit

Install [uv using its Windows PowerShell installer](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close the VS Code terminal and open a new one so its `PATH` includes `uv`. Then install Python 3.11 and the [official SpecKit package](https://github.github.io/spec-kit/installation.html):

```powershell
uv --version
uv python install 3.11
uv tool install --python 3.11 specify-cli
specify version
```

SpecKit requires Python 3.11 or newer. If `uv` or `specify` is not recognized after installation, reopen the terminal and check the relevant installer's `PATH` instructions.

## 3. Initialize SpecKit for PowerShell

Run this from the project root:

```powershell
specify init . --here --force --non-interactive --ignore-agent-tools --script ps --integration generic --integration-options="--commands-dir .config/ai/commands"
```

`--force` allows initialization in a folder that already has project files. `--script ps` installs PowerShell workflow scripts. The [generic integration](https://github.github.io/spec-kit/reference/integrations.html) places its commands under FishDev's vendor-neutral `.config/ai/` directory. `--ignore-agent-tools` skips checks for a particular AI agent executable; it does not install an agent.

## 4. Add FishDev's workflow files

Run the following in the same project root. These downloads save files; they do not execute the Linux installer.

```powershell
$ErrorActionPreference = 'Stop'
$fishDevRaw = 'https://raw.githubusercontent.com/fishdan/fishdev/main'
New-Item -ItemType Directory -Force -Path .config/ai/defaults | Out-Null
Invoke-WebRequest "$fishDevRaw/start.ai" -OutFile start.ai
Invoke-WebRequest "$fishDevRaw/fishdev-init.md" -OutFile fishdev-init.md
Invoke-WebRequest "$fishDevRaw/.config/ai/defaults/constitution.md" -OutFile .config/ai/defaults/constitution.md

Set-Content -Encoding ascii -Path AGENTS.md -Value 'Read and follow start.ai before doing any work.'
Copy-Item AGENTS.md CLAUDE.md
Copy-Item AGENTS.md GEMINI.md
Set-Content -Encoding ascii -Path .config/ai/repo.ai -Value '# Repository Settings'
Set-Content -Encoding ascii -Path .config/ai/progress.ai -Value '# Progress Log'
Set-Content -Encoding ascii -Path .config/ai/handoff.ai -Value '# Handoff'
Copy-Item .config/ai/defaults/constitution.md .specify/memory/constitution.md
```

The three `.ai` state files begin empty except for their headings. Keep future project settings, progress, and handoff notes in `.config/ai/`. The agent pointer files all direct assistants to `start.ai`.

## 5. Verify and begin

```powershell
specify version
Test-Path start.ai, .config/ai/progress.ai, .specify/memory/constitution.md, .specify/scripts/powershell
git status --short
```

All four `Test-Path` results should be `True`. In your AI assistant's chat in VS Code, say: **“Follow the instructions in start.ai.”** Review the resulting changes, then commit the initialized workflow files with your project.

These instructions were checked against current official VS Code, uv, and SpecKit documentation and against the installed SpecKit CLI. The PowerShell commands have not been executed on a Windows machine in this repository's validation environment.
