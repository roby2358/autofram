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
