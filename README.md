# FishDev Workflow

**tl;dr** you can install in any directory using:
```bash
curl -fsSL https://raw.githubusercontent.com/fishdan/fishdev/main/install.sh | bash
```

## What is FishDev?

FishDev is a standardized, constitution-driven workflow for AI-assisted software development. It relies on [SpecKit](https://github.com/github/spec-kit) and a strict set of engineering principles to ensure that AI coding assistants behave predictably, maintain project history, and produce clean, testable code. 

When initialized, FishDev scaffolds an authoritative `.config/ai/` directory that stores your project's state, handoff notes, progress logs, and your engineering constitution. This enforces "Spec-First Development," meaning no code is written without a clear specification, keeping your project organized and fully transparent.

## Why AI Agnosticism Matters

The AI landscape is moving incredibly fast. Today's best coding assistant might be obsolete in six months, and development teams are often fractured across multiple tools (like Copilot, Claude, Gemini, Cursor, or Aider). 

FishDev is built to be **strictly AI-vendor-neutral**. 

By storing all workflows, instructions, and context inside a standardized `.config/ai/` directory rather than proprietary vendor folders (like `.cursor/` or `.gemini/`), you guarantee that your project remains portable. Any engineer using any AI agent can drop into your repository, run the `start.ai` sequence, and immediately align with the project's constitution and active specifications. This eliminates vendor lock-in and ensures your repository's history and rules belong to *you*, not your tools.
