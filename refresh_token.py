#!/usr/bin/env python3
"""
Refresh the Claude Code OAuth token in .env from ~/.claude/.credentials.json

Usage:
    python refresh_token.py
"""
import json
import sys
from pathlib import Path


def main():
    credentials_path = Path.home() / ".claude" / ".credentials.json"
    env_path = Path(__file__).parent / ".env"

    if not credentials_path.exists():
        print(f"Error: {credentials_path} not found")
        print("Run 'claude login' first to generate credentials")
        sys.exit(1)

    if not env_path.exists():
        print(f"Error: {env_path} not found")
        sys.exit(1)

    try:
        with open(credentials_path) as f:
            credentials = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse {credentials_path}: {e}")
        sys.exit(1)

    oauth_data = credentials.get("claudeAiOauth")
    if not oauth_data:
        print("Error: No 'claudeAiOauth' found in credentials file")
        print(f"Available keys: {list(credentials.keys())}")
        sys.exit(1)

    token = oauth_data.get("accessToken")
    if not token:
        print("Error: No 'accessToken' found in claudeAiOauth object")
        print(f"Available keys: {list(oauth_data.keys())}")
        sys.exit(1)

    env_content = env_path.read_text()
    lines = env_content.splitlines()
    updated = False

    for i, line in enumerate(lines):
        if line.startswith("CLAUDE_CODE_OAUTH_TOKEN="):
            lines[i] = f"CLAUDE_CODE_OAUTH_TOKEN={token}"
            updated = True
            print(f"✓ Updated CLAUDE_CODE_OAUTH_TOKEN in {env_path}")
            break

    if not updated:
        print("Warning: CLAUDE_CODE_OAUTH_TOKEN not found in .env, adding it")
        lines.append(f"CLAUDE_CODE_OAUTH_TOKEN={token}")

    env_path.write_text("\n".join(lines) + "\n")
    print("\nToken refreshed successfully!")
    print("Restart the container to use the new token:")
    print("  ./launcher.sh stop && ./launcher.sh run")


if __name__ == "__main__":
    main()
