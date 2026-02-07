# SPEC: Claude Agent SDK Integration

## Overview

The main runner (Sonnet via OpenRouter) acts as a **project manager**. When it wakes up and reads COMMS.md, it breaks work into discrete **contracts**, writes each to `contracts/*.md`, then spawns a Claude Agent SDK instance for each contract. The SDK agents do the actual coding/research work. The runner collects results, updates COMMS.md, and commits.

## Flow

```
1. Runner wakes up, reads COMMS.md and the last 20 git log entries
2. Runner notes status in COMMS.md ("Working on: ...") and pushes to git
3. Runner creates contracts/001-foo.md, contracts/002-bar.md, ...
4. Runner calls execute_contracts() tool (synchronous — blocks until all contracts complete)
5. Tool returns a summary of all contract outcomes as the tool result
6. Runner reviews the summary in its next LLM turn, updates COMMS.md
7. Runner moves completed contracts to contracts_completed/ (failed contracts stay in contracts/), commits and pushes
```

## Contracts

A contract is a markdown file in `contracts/` with this structure:

```markdown
# Contract: <title>

## Status
pending | in_progress | completed | failed

## Task
<Clear, self-contained description of what the agent should do.>

## Constraints
- Files the agent may touch
- Tools allowed
- Time/turn budget

## Result
<Filled in by the SDK agent when done.>
```

The runner writes the contract with Status: pending. The executor updates it to in_progress, then completed/failed with a Result section. Contracts are self-contained — the runner's job is to decompose tasks well. SDK agents *can* read other files in the repo if they want, but we don't inject extra context.

## Contract Executor

New tool in `tools.py`: `execute_contracts()`.

```python
execute_contracts() -> str
```

- Scans `contracts/` for files with `Status: pending`
- For each pending contract:
  - Parses the contract (task, constraints, allowed files/tools)
  - Updates status to `in_progress`
  - Calls the Claude Agent SDK `query()` function
  - Writes the result back into the contract file
  - Updates status to `completed` or `failed`
- Returns a summary of all contract outcomes

SDK agents only modify files — the runner handles all git operations. Separation of concerns.

### SDK Agent Configuration

Each SDK agent gets:
- `prompt`: The full contract text
- `system_prompt`: "You are a contractor working within autofram. Only modify files, do not use git."
- `allowed_tools`: All SDK built-in tools by default (`["Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"]`), can be restricted via contract Constraints
- `cwd`: The working directory (`/agent/<branch>/autofram/`)
- `permission_mode`: `"bypassPermissions"` (the container is already sandboxed)
- `model`: `"sonnet"`
- `max_turns`: From contract Constraints (default: 30)

### Sequencing

Contracts execute **sequentially** (ordered by filename). Simpler, avoids filesystem conflicts.

## Authentication

The SDK authenticates via the Max plan OAuth token, not a separate API key.

### Getting the token into the container

1. Add `CLAUDE_CODE_OAUTH_TOKEN` to `.env` (and `.env.example`)
2. `.env` is already read by `entrypoint.sh` from `/mnt/remote/.env`
3. The SDK reads `CLAUDE_CODE_OAUTH_TOKEN` from the environment automatically

Token rotation requires a container restart. This is the cloud-forward pattern — in production, the token would come from a secrets manager.

### Cost control

- `max_turns` per contract (default 30)
- The runner decides how many contracts to create per cycle — it should be conservative

## Dependencies

Add to `pyproject.toml`:

```toml
"claude-agent-sdk",
```

The SDK bundles its own Claude Code CLI — no separate `npm install` needed.

Node.js is required at runtime (the SDK spawns the CLI as a Node subprocess). Add `nodejs` to the Dockerfile's `apt-get install` line.

## Implementation Plan

1. Add `CLAUDE_CODE_OAUTH_TOKEN` to `.env.example`
2. Add `nodejs` to Dockerfile apt-get
3. Add `claude-agent-sdk` to `pyproject.toml`
4. Create `src/autofram/contracts.py`:
   - `parse_contract(path) -> dict` — parse a contract markdown file
   - `update_contract(path, status, result)` — update status/result in a contract file
   - `execute_contract(path) -> str` — run one contract via SDK
   - `execute_contracts() -> str` — run all pending contracts
5. Make tool executor async-aware in `tools.py` — `execute_tool()` should await coroutines
6. Register `execute_contracts` as an async tool in `tools.py`
7. Update `SYSTEM.md` to teach the runner about contracts
8. Create `contracts/.gitkeep` and `contracts_completed/.gitkeep`