#!/bin/bash
# Bootstrap script - lives in repo so agent can modify it
# Launched by entrypoint.sh after clone, or by bootstrap tool for branch switches
set -e

# Configuration - derive location from script path (works for any branch)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"

cd "$REPO_DIR"

# Dependencies
uv pip install --system -e .

# Wrap bundled Claude CLI to run as agent user (SDK refuses to run as root)
BUNDLED_CLAUDE="/usr/local/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude"
if [ -f "$BUNDLED_CLAUDE" ] && [ ! -f "$BUNDLED_CLAUDE.real" ]; then
    mv "$BUNDLED_CLAUDE" "$BUNDLED_CLAUDE.real"
    printf '#!/bin/bash\nexec runuser -u agent -- "${0}.real" "$@"\n' > "$BUNDLED_CLAUDE"
    chmod +x "$BUNDLED_CLAUDE"
fi

# Setup
mkdir -p "$REPO_DIR/logs"
export AUTOFRAM_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Launch services
python "$REPO_DIR/src/autofram/server.py" &
python "$REPO_DIR/src/autofram/watcher.py" &
python "$REPO_DIR/src/autofram/runner.py" &

# Forward SIGTERM to all children for clean shutdown
trap 'kill 0' SIGTERM
wait
