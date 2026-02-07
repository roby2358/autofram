# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Autofram is a sandboxed, self-modifying AI agent that communicates with the outside world exclusively through git. It runs in a Podman container with network isolation, using a bind-mounted bare git repo as its sole communication channel with the human operator ("PM").

## Build & Run

```bash
./launcher.sh build     # Build the container
./launcher.sh run       # Start the agent
./launcher.sh stop      # Stop the agent
./launcher.sh logs      # View container logs
./launcher.sh shell     # Shell into the container
./launcher.sh rebuild   # Rebuild and run
```

Requires a `.env` file (copy from `.env.example`). Key vars: `OPENROUTER_API_KEY`, `AUTOFRAM_REMOTE` (path to bare git repo).

## Testing

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_runner.py

# Run a specific test
pytest tests/test_runner.py::test_function_name
```

Tests are in `tests/`, source path is configured in `pyproject.toml` (`pythonpath = ["src"]`).

## Architecture

**Two-stage container startup:**
1. `entrypoint.sh` (static, baked into image) — sets up git config, nftables network isolation, clones repo, then execs into:
2. `bootstrap.sh` (agent-modifiable, in repo) — installs deps via `uv pip install --system -e .`, starts server/watcher as background processes, execs runner in foreground.

**Three concurrent processes inside the container:**
- `runner.py` — The LLM agent loop. Checks COMMS.md for directives on a configurable interval, calls OpenRouter API, exposes tools via MCP.
- `watcher.py` — Crash recovery monitor. Restarts runner from `/agent/main/autofram` on crashes. Detects CPU runaway and log explosion.
- `server.py` — FastAPI status endpoint on port 8080.

**Key source files (`src/autofram/`):**
- `tools.py` — MCP tool definitions (read_file, write_file, bash, bootstrap, rollback)
- `git.py` — Git utilities for pull/push/commit
- `filesystem.py` — Filesystem utilities

**Hop-scotch upgrade pattern:** The agent modifies code on a *different* branch from the one it's running on, pushes, then calls `bootstrap(target_branch)` which execs the new runner. The new branch self-validates, merges to main, then bootstraps back to main. This ensures the running process never modifies its own code in-place.

**Communication:** All human-agent communication happens through `COMMS.md` via git commits. The PM edits COMMS.md in a working copy cloned from the shared bare repo.

## Dependencies

Python 3.12, managed with `uv`. Key deps: `openai` (for OpenRouter), `mcp`, `fastapi`/`uvicorn`, `psutil`, `ddgs`. See `pyproject.toml`.

## Container Details

- Base image: `python:3.12-slim`
- PostgreSQL is available inside the container
- Network: all RFC1918/link-local blocked via nftables; outbound internet allowed
- Working directory inside container: `/agent/<branch>/autofram/`
