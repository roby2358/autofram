#!/bin/bash
set -e

# Load .env if present in mounted location
if [ -f /mnt/remote/.env ]; then
    export $(grep -v '^#' /mnt/remote/.env | xargs)
fi

# Configure git user
git config --global user.name "${GIT_USER_NAME:-autofram}"
git config --global user.email "${GIT_USER_EMAIL:-autofram@localhost}"

# Configure nftables for network isolation
# Block RFC1918 private ranges and link-local
nft add table inet filter 2>/dev/null || true
nft add chain inet filter output '{ type filter hook output priority 0; policy accept; }' 2>/dev/null || true
nft add rule inet filter output ip daddr 10.0.0.0/8 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 172.16.0.0/12 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 192.168.0.0/16 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 169.254.0.0/16 drop 2>/dev/null || true

# Clone repo from /mnt/remote to /agent/main/autofram
if [ ! -d /agent/main/autofram ]; then
    git clone /mnt/remote /agent/main/autofram
fi

# Create logs directory
mkdir -p /agent/main/autofram/logs

# Change to working directory
cd /agent/main/autofram

# Determine current branch for status server
export AUTOFRAM_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Start status server as background process
python /agent/main/autofram/src/autofram/server.py &

# Start watcher as background process
python /agent/main/autofram/src/autofram/watcher.py &

# Exec runner in foreground
exec python /agent/main/autofram/src/autofram/runner.py
