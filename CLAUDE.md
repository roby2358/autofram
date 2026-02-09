# CLAUDE.md

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
pytest                                        # all tests
pytest tests/test_runner.py                   # one file
pytest tests/test_runner.py::test_func_name   # one test
```

Tests are in `tests/`, source path configured in `pyproject.toml` (`pythonpath = ["src"]`).

## Architecture

**Two-stage startup:**
1. `entrypoint.sh` (static, baked into image) — git config, nftables isolation, clones repo, execs into:
2. `bootstrap.sh` (agent-modifiable) — installs deps via `uv pip install --system -e .`, starts server/watcher as background processes, execs runner in foreground.

**Three processes:**
- `runner.py` — LLM agent loop. Checks COMMS.md on a configurable interval, calls OpenRouter API, exposes tools via MCP.
- `watcher.py` — Crash recovery. Rolls back runner to main on crashes. Detects CPU runaway and log explosion.
- `server.py` — FastAPI status endpoint on port 8080.

**Key source files (`src/autofram/`):**
- `tools.py` — MCP tool definitions (read_file, write_file, bash, bootstrap, rollback). Names are self-explanatory; see below for behavioral details.
- `git.py` — Git pull/push/commit utilities
- `filesystem.py` — Filesystem utilities

**Hop-scotch upgrade:** The agent modifies code on a *different* branch, pushes, then calls `bootstrap(target_branch)` which pulls and execs the new runner. The new branch self-validates, merges to main, then bootstraps back to main. The running process never modifies its own code in-place.

**Rollback:** `rollback()` kills all runner processes and restarts main *without pulling* — a safe recovery to last known-good state. The watcher uses rollback (not bootstrap) on crash.

**Communication:** All human-agent communication happens through `COMMS.md` via git commits. The PM edits COMMS.md in a working copy cloned from the shared bare repo. The agent is free to structure COMMS.md however it sees fit.

## Code Style

Simple, readable Python. No type hints, no docstrings — the code must be easy for an LLM to read and modify. Use `logging` (not print). Keep functions short. Favor small named functions over inline or lambdas. Favor classes over modules of functions.

**Error handling:** Tolerate transient failures (network timeouts, API errors) with logging and retry. Fail fast on structural errors (git corruption, bad bootstrap, invalid state) — stability matters more than uptime.

## Dependencies

Python 3.12, managed with `uv`. Key deps: `openai` (for OpenRouter), `mcp`, `fastapi`/`uvicorn`, `psutil`, `ddgs`. See `pyproject.toml`.

## Logging

All logs in `logs/` under the working directory. Format: `%(asctime)s %(levelname)s %(message)s`.

- `runner.log` — agent loop (rotating, 5MB x 3 backups)
- `model.log` — raw API requests/responses (JSON)
- `errors.log` — stderr + explicit errors
- `bootstrap.log` — bootstrap events
- `watcher.log` — watcher activity
- `access.log` — HTTP access logs

## Container

- Base image: `python:3.12-slim`
- PostgreSQL available inside the container
- Network: RFC1918/link-local blocked via nftables; outbound internet allowed
- Bare repo bind-mounted at `/mnt/remote` (git remote for pull/push)
- Working directory: `/home/agent/<branch>/autofram/`
