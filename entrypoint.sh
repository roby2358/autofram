#!/bin/bash
# Minimal bootloader - clones repo and hands off to bootstrap.sh
# This file stays static in the container for security
set -e

# Configuration
REMOTE_REPO="/mnt/remote"
AGENT_BASE="/agent"
BRANCH="main"
WORKDIR="$AGENT_BASE/$BRANCH/autofram"

# Environment
if [ -f "$REMOTE_REPO/.env" ]; then
    export $(grep -v '^#' "$REMOTE_REPO/.env" | xargs)
fi

git config --global user.name "${GIT_USER_NAME:-autofram}"
git config --global user.email "${GIT_USER_EMAIL:-autofram@localhost}"

# Network isolation (static for security - agent cannot modify)
nft add table inet filter 2>/dev/null || true
nft add chain inet filter output '{ type filter hook output priority 0; policy accept; }' 2>/dev/null || true
# Allow DNS (needed for WSL where DNS server is on private IP)
nft add rule inet filter output udp dport 53 accept 2>/dev/null || true
nft add rule inet filter output tcp dport 53 accept 2>/dev/null || true
# Block private ranges
nft add rule inet filter output ip daddr 10.0.0.0/8 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 172.16.0.0/12 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 192.168.0.0/16 drop 2>/dev/null || true
nft add rule inet filter output ip daddr 169.254.0.0/16 drop 2>/dev/null || true

# Clone and hand off
if [ ! -d "$WORKDIR" ]; then
    git clone "$REMOTE_REPO" "$WORKDIR"
fi

exec "$WORKDIR/bootstrap.sh"
