# Self-Modifying Agent System - Technical Specification

A sandboxed, self-modifying AI agent that communicates with the outside world exclusively through git.

## Project Name

**autofram** - the self-framing autonomous agent.

## Purpose

This system provides a secure environment for an AI agent to write, test, and deploy code—including modifications to itself. The agent operates in an isolated container with no direct access to the host machine. All communication between the agent and the human operator (the "PM") occurs through git commits. The agent is the project: it builds and improves itself over time.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Host Machine                                                   │
│                                                                 │
│  /home/user/autofram-remote/  (bare git repo)                   │
│         ▲                                                       │
│         │ bind mount                                            │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Podman Container                                       │    │
│  │                                                         │    │
│  │  /mnt/remote  ◄──────────────────────────────────────┐  │    │
│  │                                                      │  │    │
│  │  /agent                                              │  │    │
│  │    /main                                             │  │    │
│  │      /autofram  (working directory) ◄── git pull/push ┘  │    │
│  │    /feature-x                                        │    │
│  │      /autofram  (experimental branch)                │    │
│  │                                                         │    │
│  │  Processes (separate, concurrent):                      │    │
│  │    - server.py  (status API on port 8080)               │    │
│  │    - watcher.py (monitors agent, handles crashes)       │    │
│  │    - runner.py  (LLM loop, executes agent logic)        │    │
│  │                                                         │    │
│  └────────────────────────────────┬────────────────────────┘    │
│                                   │                             │
│                              port 8080                          │
│                                   │                             │
│                              curl localhost:8080/status         │
│                                                                 │
│  /home/user/autofram-working/  (user's working copy)            │
│    - User edits COMMS.md, pushes                                │
│    - User reviews branches, merges                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
/agent/<branch>/autofram/
├── bootstrap.sh           # Startup script (agent-modifiable)
├── COMMS.md               # Directives and reports
├── pyproject.toml         # Python dependencies
├── .gitignore             # Excludes logs/
├── /static
│   └── /prompts
│       └── SYSTEM.md      # Base system prompt
├── /spec
│   └── SPEC_*.md          # Specifications (read into context as needed)
├── /src/autofram          # Orchestration code (agent-modifiable)
│   ├── runner.py          # Agent LLM loop
│   ├── watcher.py         # Process monitor (crash recovery only)
│   ├── server.py          # Status API server
│   ├── tools.py           # MCP tool definitions
│   ├── git.py             # Git utilities
│   └── filesystem.py      # Filesystem utilities
└── /logs                  # .gitignored
    ├── bootstrap.log      # Bootstrap attempts and outcomes
    ├── errors.log         # Captured errors and stderr
    ├── runner.log         # Runner operational log (rotating)
    ├── model.log          # LLM API requests and responses (JSONL)
    ├── access.log         # Status server access log
    └── watcher.log        # Watcher operational log
```

## Functional Requirements

### Container Isolation

- The container MUST allow DNS traffic (UDP/TCP port 53) before applying private range blocks (required for environments where the DNS resolver is on a private IP, e.g., WSL)
- The container MUST block all network access to RFC1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- The container MUST block access to link-local addresses (169.254.0.0/16)
- The container MUST allow outbound internet access for LLM API calls and package installation
- The container MUST mount the host's bare git repo at /mnt/remote
- The container MUST drop all capabilities and add back only NET_ADMIN (required for nftables)
- The container MUST run with no-new-privileges security option

### Git Communication

- The agent MUST use git as the sole mechanism for communicating with the outside world
- The agent MUST pull from /mnt/remote to receive updates
- The agent MUST push to /mnt/remote to publish changes
- The agent MUST commit changes before calling bootstrap
- The host MUST maintain a bare git repository for the agent remote
- The user MUST interact with the agent by cloning, editing, and pushing to the same bare repo

### Agent Tools

The agent MUST have access to the following tools:

- **read_file(path)** - Read contents of a file
- **write_file(path, content)** - Write contents to a file
- **bash(command)** - Execute a shell command (5-minute timeout)
- **bootstrap(branch)** - Clone/update target branch directory and exec its runner
- **rollback()** - Bootstrap to main branch to recover from a bad state
- **web_search(query, max_results)** - Search the web using DuckDuckGo

The agent SHOULD use bash for git operations, running tests, and other system tasks.

Bootstrap and rollback tools directly exec the new runner process, replacing the current process. Before exec, the tool MUST write a touch file (`logs/bootstrapping`) in main's logs directory so the watcher knows a transition is in progress. The watcher is not involved in bootstrap/rollback - it only handles crash recovery.

### Prompt Construction

- The system prompt MUST consist of SYSTEM.md followed by COMMS.md
- The user message MUST be "Continue."
- The agent MUST read SPEC_*.md files into context as needed during execution
- The agent MAY modify SYSTEM.md to change its own base behavior

### SYSTEM.md Content

SYSTEM.md MUST establish:
- The agent's identity and purpose (self-modifying autonomous agent)
- Available tools and their usage (read_file, write_file, bash, bootstrap, rollback, web_search)
- The hop-scotch upgrade pattern and when to use it
- Communication protocol via COMMS.md
- Work loop behavior and timing
- Error handling and recovery procedures
- Guidelines for self-modification safety

### COMMS.md Format

- COMMS.md is freeform text with no required structure
- The PM SHOULD add directives by editing COMMS.md and pushing
- The agent MUST update COMMS.md to communicate status and results
- The agent MAY add suggestions or questions to COMMS.md
- Pruning of COMMS.md SHOULD be a shared responsibility between PM and agent
- Initial COMMS.md content: "No directives at this time. Enter wait loop for updates."

### Spec Files

- Specification files MUST be stored in /spec with the naming pattern SPEC_*.md
- The PM MAY add or edit spec files to provide persistent requirements
- The agent MAY propose spec changes by editing files and committing to a branch
- Spec files SHOULD follow RFC 2119 language conventions

### Bootstrap Process

- The agent MUST write a BOOTSTRAPPING entry to bootstrap.log on startup
- The agent MUST write a SUCCESS entry to bootstrap.log after successful initialization
- The bootstrap log entry MUST include a timestamp and branch name
- If the watcher detects a missing SUCCESS entry after restart, it MUST fall back to main

### Hop-Scotch Upgrade Pattern

The agent MUST NOT modify files in its own running directory. All code changes MUST be made in a separate clone directory and validated there before merging.

**Step 1: Running from main path** (`/agent/main/autofram/`)
- The agent creates a git branch and pushes it to remote
- The agent clones the branch to a separate directory (`/agent/feature-x/autofram/`)
- The agent makes and tests changes in the clone directory
- The agent commits and pushes from the clone directory

**Step 2: Bootstrap into branch path** (`/agent/feature-x/autofram/`)
- The agent calls `bootstrap("feature-x")` which execs the branch's runner
- The current process is replaced; the agent is now running from the branch path

**Step 3: Validate in branch path**
- The agent self-validates (runs tests, checks behavior)
- If unstable, the agent calls `rollback()` to return to main, or the watcher recovers automatically on crash

**Step 4: Bootstrap back to main path** (`/agent/main/autofram/`)
- The agent merges the branch into main and pushes
- The agent calls `bootstrap("main")` which execs the main runner
- The agent is now running from main with the upgraded code

Bootstrap uses exec to replace the current process with the target branch's runner. The main path (`/agent/main/autofram/`) MUST remain untouched during the upgrade so the watcher can fall back to it on failure.

### Work Loop

- The agent MUST check COMMS.md for new directives at the configured interval (WORK_INTERVAL_MINUTES)
- The agent MUST skip the LLM call if COMMS.md has not changed since the last cycle (tracked via content hash)
- Work intervals MUST be aligned to clock time (e.g., with 1-minute interval: :00, :01, :02, ...)
- After completing work, the agent MUST sleep until the next aligned interval
- If work extends past an interval boundary, the agent MUST continue working and wait for the next interval
- A unit of work MAY span multiple files and include coding, testing, and validation
- The agent SHOULD use judgment to determine appropriate work boundaries

### Watcher Process

The watcher handles crash recovery only. Bootstrap and rollback are handled by the runner via exec.

- The watcher MUST run as a separate process from the agent runner
- The watcher MUST find the runner by scanning for the process by name
- The watcher MUST monitor the runner process for unexpected termination
- If the runner crashes, the watcher MUST launch runner from /agent/main/autofram
- The watcher MUST recognize an in-progress bootstrap via a touch file (`logs/bootstrapping`) and suppress restart during the grace period (60 seconds)
- The watcher MUST monitor for CPU runaway (95%+ CPU for 60+ seconds)
- The watcher MUST monitor for log file explosion (errors.log exceeds 1 MB)
- The watcher MUST terminate the agent if runaway or explosion is detected
- The watcher MUST track crash frequency and implement restart limits
- If the agent crashes 5 times within 60 minutes, the watcher MUST stop restarting and alert via COMMS.md
- The watcher MAY append critical messages to COMMS.md when intervention is needed

### Status Server

- The status server MUST expose an HTTP endpoint at `/status` on port 8080
- The status server MUST return plain text responses
- The `/status` endpoint MUST return:
  - Current timestamp
  - Branch name the runner was launched from
  - Process information for watcher and runner (PID, status, uptime)
- The status server MUST run as a separate background process
- The status port MUST be exposed to the host via port mapping
- The branch name MUST be passed to the server via the `AUTOFRAM_BRANCH` environment variable

**Status Response Format:**
```
timestamp: 2024-01-15 10:30:45
branch: main
watcher: pid=123 status=sleeping uptime=1h 5m 30s
runner: pid=456 status=running uptime=0h 58m 12s
```

If a process is not running:
```
watcher: not running
```

### File Formats

**Bootstrap Log Format (bootstrap.log):**
```
<STATUS> <ISO8601_TIMESTAMP> <BRANCH>
```
Example:
```
BOOTSTRAPPING 2024-01-15T10:30:00Z main
SUCCESS 2024-01-15T10:30:05Z main
BOOTSTRAPPING 2024-01-15T11:00:00Z feature-x
FALLBACK 2024-01-15T11:00:10Z main
```

Valid status values: BOOTSTRAPPING, SUCCESS, FALLBACK

### Logging

- The logs/ directory MUST be located within the working directory (/agent/<branch>/autofram/logs/)
- The runner MUST capture its stderr to logs/errors.log
- The runner MUST maintain a rotating operational log (logs/runner.log, 5 MB max, 3 backups)
- The runner MUST log all LLM API requests and responses to logs/model.log in JSONL format
- The agent MUST be able to read errors.log to investigate failures
- Bootstrap attempts MUST be logged to logs/bootstrap.log
- The watcher MUST maintain its own operational log (logs/watcher.log)
- The status server MUST log HTTP access to logs/access.log
- Log files MUST NOT be committed to git (logs/ in .gitignore)
- Each bootstrap SHOULD start with a fresh errors.log (truncate on startup)
- Old logs are cleaned up when branch directories are deleted after merge

### Branch Directory Management

- Each branch MUST be cloned to /agent/<branch>/autofram/
- The runner MUST create branch directories via git clone when bootstrapping
- The agent MUST clean up branch directories after successful merge to main
- Git history provides audit trail; branch directories are ephemeral
- On crash recovery, the watcher always restarts from /agent/main/autofram

## Non-Functional Requirements

### Security

- The container MUST NOT have access to host filesystem except the git mount
- The container SHOULD run rootless
- No git credentials required (local bare repo via bind mount)
- The agent MUST NOT be able to access watcher process memory or signals except through defined mechanisms

### Reliability

- The system MUST recover from agent crashes by falling back to main
- The system MUST maintain git history for all changes
- The system MUST support rollback to main as a recovery mechanism
- The watcher MUST continue running even if agent repeatedly crashes

### Observability

- All agent errors MUST be captured to a readable log file
- All bootstrap attempts MUST be logged with timestamps and outcomes
- The PM MUST be able to review agent activity through git history
- The status server MUST provide real-time process status via HTTP

## Dependencies

**Container Runtime:**
- Podman for rootless container execution
- Base image: python:slim with uv package manager

**Network:**
- nftables for network isolation rules

**Version Control:**
- Git for all communication and state management
- No authentication required (local bare repo via bind mount)

**Agent Runtime:**
- Python for watcher and runner infrastructure
- LLM API via OpenRouter using the OpenAI Python client (default model: Claude Sonnet 4.5)
- FastMCP for tool schema generation (OpenAI function calling format)
- FastAPI and uvicorn for status server
- DuckDuckGo Search (ddgs) for web search tool
- psutil for process monitoring
- Third-party OSS libraries preferred over custom implementations

**Available Services:**
- PostgreSQL is installed in the container and available for agent use if needed

## Configuration

### Environment Variables

The following environment variables MUST be supported:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENROUTER_API_KEY | Yes | - | API key for OpenRouter LLM access |
| OPENROUTER_MODEL | No | anthropic/claude-sonnet-4.5 | Model identifier for OpenRouter |
| GIT_USER_NAME | No | autofram | Git commit author name |
| GIT_USER_EMAIL | No | autofram@localhost | Git commit author email |
| WORK_INTERVAL_MINUTES | No | 1 | Minutes between work loop iterations |
| AUTOFRAM_STATUS_PORT | No | 8080 | Port for the status server |
| AUTOFRAM_BRANCH | No | (set by bootstrap.sh) | Branch name for status server |

### .env File

- The system MUST support loading configuration from a `.env` file
- The `.env` file MUST be located in the project root on the host
- The `.env` file MUST NOT be committed to git (include in .gitignore)
- Environment variables MUST override `.env` values

### Launcher Script

- A launcher script MUST be provided to build and run the container
- The script MUST load `.env` if present
- The script MUST pass required environment variables to the container
- The script MUST handle container lifecycle (build, run, stop)

### Container Initialization

The container uses a two-stage startup: a static bootloader (entrypoint.sh) hands off to an agent-modifiable bootstrap script (bootstrap.sh).

**Stage 1: entrypoint.sh (static, baked into container)**
- Load .env from /mnt/remote if present
- Configure git user.name and user.email from environment variables
- Configure nftables for network isolation (security-critical, not agent-modifiable)
- Clone the repo from /mnt/remote to /agent/main/autofram on first start
- Exec bootstrap.sh from the cloned repo

**Stage 2: bootstrap.sh (agent-modifiable, lives in repo)**
- Install Python dependencies via `uv pip install --system -e .`
- Create logs directory
- Determine current branch and set AUTOFRAM_BRANCH
- Start server.py as a background process
- Start watcher.py as a background process
- Exec runner.py in the foreground

This architecture allows the agent to modify how it starts up (bootstrap.sh, dependencies, orchestration code) while keeping security-critical network isolation static in the container.

## Implementation Notes

### Bind Mount vs Network Git

Phase 1 uses a bind-mounted bare git repository for simplicity. No authentication is required for local bare repo operations. The attack surface is limited to git objects rather than arbitrary files. A future iteration MAY switch to network-based git (git daemon on a single port) for stronger isolation.

### Single Process Constraint

Only one agent process runs at a time to simplify watcher logic. The watcher cannot distinguish between multiple agent processes, so the hop-scotch pattern ensures clean handoffs.

### Self-Modifying Architecture

The container has a minimal static layer (entrypoint.sh) and everything else lives in the git repository. This means the agent can modify:

- **bootstrap.sh** - How the system starts up
- **pyproject.toml** - Python dependencies
- **src/autofram/*.py** - All orchestration code (runner, watcher, server, tools)
- **static/prompts/SYSTEM.md** - Its own system prompt

Only entrypoint.sh and network isolation rules are baked into the container image. When bootstrap() or rollback() is called, the new branch's bootstrap.sh runs, installing any new dependencies and starting the updated orchestration code.

### Watcher Architecture

The watcher code lives in the git repository alongside agent code but runs as a separate process. This is a YOLO design choice: the watcher can theoretically be upgraded by the agent, but in practice it should remain stable and rarely change. If a watcher upgrade breaks the watcher, manual intervention is required. The watcher starts from /agent/main/autofram/src/autofram/watcher.py and is not subject to the hop-scotch pattern.

The watcher is designed to be minimal. It only monitors for crashes and resource abuse. Bootstrap and rollback are handled entirely by the runner via exec - the watcher is not involved in normal branch transitions. This keeps the watcher simple and reduces coordination complexity.

### MCP Tool Exposure

Tools are defined using MCP's FastMCP decorator for schema generation, but invoked directly as Python functions via the OpenAI function calling format. The runner extracts tool schemas from FastMCP and converts them to OpenAI tool definitions. Tool execution is synchronous within the LLM conversation loop.

### Context Window Management

SYSTEM.md and COMMS.md are included in every prompt. SPEC_*.md files are read into context on demand. The agent is responsible for managing context window limits. COMMS.md pruning is a shared responsibility.

### Bootstrap Log Interpretation

The watcher determines success by checking for a SUCCESS entry following the most recent BOOTSTRAPPING entry. Absence of SUCCESS indicates a crash during initialization, triggering fallback to main.

## Error Handling

The system MUST handle these error conditions:

- **Agent crash during startup** - Watcher restarts from /agent/main/autofram
- **Agent crash during work** - Watcher restarts from main, agent investigates via error logs
- **Bad bootstrap target** - Runner fails to exec, crashes, watcher falls back to main
- **Git push failure** - Agent retries or reports in COMMS.md
- **LLM API failure** - Agent logs error, sleeps 60 seconds, retries
- **Runaway process** - Watcher terminates agent, restarts from main
- **Log explosion** - Watcher terminates agent, restarts from main
- **Repeated crashes** - After 5 crashes in 60 minutes, watcher stops and alerts PM via COMMS.md