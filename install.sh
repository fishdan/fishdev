#!/usr/bin/env bash
set -e

REPO_RAW_URL="https://raw.githubusercontent.com/fishdan/fishdev/main"

echo "🐟 Initializing FishDev AI workflow..."

# 1. Create directories
echo "Creating repository layout..."
mkdir -p .config/ai/defaults

# 2. Download workflow files
echo "Downloading core workflow files..."
curl -fsSL "$REPO_RAW_URL/start.ai" -o start.ai
curl -fsSL "$REPO_RAW_URL/fishdev-init.md" -o fishdev-init.md
curl -fsSL "$REPO_RAW_URL/.config/ai/defaults/constitution.md" -o .config/ai/defaults/constitution.md

# 3. Create pointer files and state files
echo "Setting up agent pointers and state files..."
cat << 'EOF' > AGENTS.md
Read and follow start.ai before doing any work.
EOF
cp AGENTS.md CLAUDE.md
cp AGENTS.md GEMINI.md

cat << 'EOF' > .config/ai/repo.ai
# Repository Settings
EOF

cat << 'EOF' > .config/ai/progress.ai
# Progress Log
EOF

cat << 'EOF' > .config/ai/handoff.ai
# Handoff
EOF

# 4. Install SpecKit via uv
echo "Installing specify-cli..."
if ! command -v uv &> /dev/null; then
    echo "uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# 5. Initialize SpecKit
echo "Initializing SpecKit..."
# Using --ignore-agent-tools to prevent interactive blocks and checks during automated setup
specify init . --here --force --ignore-agent-tools

# Copy constitution for SpecKit memory
mkdir -p .specify/memory
cp .config/ai/defaults/constitution.md .specify/memory/constitution.md

echo ""
echo "✅ FishDev Bootstrap complete!"
echo ""
echo "Next Steps:"
echo "tell your ai assistant to follow the instructions in ./start.ai and start all future sessions with that command.
