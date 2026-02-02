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
│  /home/user/autofram-remote/  (bare git repo)                      │
│         ▲                                                       │
│         │ bind mount                                            │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Podman Container                                       │    │
│  │                                                         │    │
│  │  /mnt/remote  ◄──────────────────────────────────────┐  │    │
│  │                                                      │  │    │
│  │  /agent                                                │  │    │
│  │    /main                                             │  │    │
│  │      /autofram  (working directory) ◄── git pull/push ──┘  │    │
│  │    /feature-x                                           │    │
│  │      /autofram  (experimental branch)                      │    │
│  │                                                         │    │
│  │  Processes (separate, concurrent):                      │    │
│  │    - watcher.py (monitors agent, handles crashes)       │    │
│  │    - runner.py  (LLM loop, executes agent logic)        │    │
│  │                                                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  /home/user/autofram-working/  (user's working copy)               │
│    - User edits COMMS.md, pushes                                │
│    - User reviews branches, merges                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
/agent/<branch>/autofram/
├── SYSTEM.md              # Base system prompt
├── COMMS.md               # Directives and reports
├── .gitignore             # Excludes logs/
├── /spec
│   └── SPEC_*.md          # Specifications (read into context as needed)
├── /infra
│   ├── runner.py          # Agent LLM loop
│   └── watcher.py         # Process monitor (crash recovery only)
├── /src
│   └── ...                # Agent code and any project code
└── /logs                  # .gitignored
    ├── bootstrap.log      # Bootstrap attempts and outcomes
    ├── errors.log         # Captured errors and stderr
    └── watcher.log        # Watcher operational log
```

## Functional Requirements

### Container Isolation

- The container MUST block all network access to RFC1918 private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- The container MUST block access to link-local addresses (169.254.0.0/16)
- The container MUST allow outbound internet access for LLM API calls and package installation
- The container MUST mount the host's bare git repo at /mnt/remote
- The container MUST drop all capabilities except those required for operation
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
- **bash(command)** - Execute a shell command
- **bootstrap(branch)** - Clone/update target branch directory and exec its runner
- **rollback(ref)** - Reset current branch to specified git ref and exec runner

The agent SHOULD use bash for git operations, running tests, and other system tasks.

Bootstrap and rollback tools directly exec the new runner process, replacing the current process. There is brief overlap during the transition. The watcher is not involved in bootstrap/rollback - it only handles crash recovery.

### Prompt Construction

- The system prompt MUST consist of SYSTEM.md followed by COMMS.md
- The user message MUST be "Continue."
- The agent MUST read SPEC_*.md files into context as needed during execution
- The agent MAY modify SYSTEM.md to change its own base behavior

### SYSTEM.md Content

SYSTEM.md MUST establish:
- The agent's identity and purpose (self-modifying autonomous agent)
- Available tools and their usage (read_file, write_file, bash, bootstrap, rollback)
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

- The agent MUST modify code on a branch different from the one it is running on
- To upgrade, the running agent MUST:
    - Commit changes to the target branch
    - Push to remote
    - Call bootstrap(target_branch) which execs the new runner
- The newly launched branch MUST:
    - Self-validate
    - Merge into main (if stable)
    - Call bootstrap("main") which execs the main runner
- Bootstrap uses exec to replace the current process with the new runner
- Brief overlap occurs during exec transition; this is acceptable

### Work Loop

- The agent MUST check COMMS.md for new directives at minimum every 10 minutes
- Work intervals MUST be aligned to clock time (:00, :10, :20, :30, :40, :50)
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
- The watcher MUST monitor for CPU runaway (100% CPU for 60+ seconds)
- The watcher MUST monitor for log file explosion (errors.log exceeds 1 MB)
- The watcher MUST terminate the agent if runaway or explosion is detected
- The watcher MUST track crash frequency and implement restart limits
- If the agent crashes 5 times within 60 minutes, the watcher MUST stop restarting and alert via COMMS.md
- The watcher MAY append critical messages to COMMS.md when intervention is needed

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
- The runner MUST capture its stdout and stderr to logs/errors.log
- The agent MUST be able to read errors.log to investigate failures
- Bootstrap attempts MUST be logged to logs/bootstrap.log
- The watcher MUST maintain its own operational log (logs/watcher.log)
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
- The system SHOULD support rollback to any previous git ref
- The watcher MUST continue running even if agent repeatedly crashes

### Observability

- All agent errors MUST be captured to a readable log file
- All bootstrap attempts MUST be logged with timestamps and outcomes
- The PM MUST be able to review agent activity through git history

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
- LLM API via OpenRouter (default model: Claude Sonnet 4.5)
- MCP (Model Context Protocol) for tool exposure
- Third-party OSS libraries preferred over custom implementations

## Configuration

### Environment Variables

The following environment variables MUST be supported:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENROUTER_API_KEY | Yes | - | API key for OpenRouter LLM access |
| OPENROUTER_MODEL | No | anthropic/claude-sonnet-4.5 | Model identifier for OpenRouter |
| GIT_USER_NAME | No | autofram | Git commit author name |
| GIT_USER_EMAIL | No | autofram@company.com | Git commit author email |

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

- The container entry point MUST clone the repo from /mnt/remote to /agent/main/autofram on first start
- Git user.name and user.email MUST be configured from environment variables before any git operations
- The entry point MUST start watcher.py as a background process
- The entry point MUST then exec runner.py in the foreground
- The watcher finds the runner by scanning for the process by name (no PID files needed)
- The watcher monitors for crashes and resource abuse; it does not manage bootstrap/rollback

## Implementation Notes

### Bind Mount vs Network Git

Phase 1 uses a bind-mounted bare git repository for simplicity. No authentication is required for local bare repo operations. The attack surface is limited to git objects rather than arbitrary files. A future iteration MAY switch to network-based git (git daemon on a single port) for stronger isolation.

### Single Process Constraint

Only one agent process runs at a time to simplify watcher logic. The watcher cannot distinguish between multiple agent processes, so the hop-scotch pattern ensures clean handoffs.

### Watcher Architecture

The watcher code lives in the git repository alongside agent code but runs as a separate process. This is a YOLO design choice: the watcher can theoretically be upgraded by the agent, but in practice it should remain stable and rarely change. If a watcher upgrade breaks the watcher, manual intervention is required. The watcher has its own implicit bootstrap - it starts from /agent/main/autofram/infra/watcher.py and is not subject to the hop-scotch pattern.

The watcher is designed to be minimal. It only monitors for crashes and resource abuse. Bootstrap and rollback are handled entirely by the runner via exec - the watcher is not involved in normal branch transitions. This keeps the watcher simple and reduces coordination complexity.

### MCP Tool Exposure

Tools are exposed to the LLM via Model Context Protocol (MCP). This provides a standardized interface for tool discovery and execution. The runner acts as an MCP server, exposing read_file, write_file, bash, bootstrap, and rollback tools to the model.

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
- **LLM API failure** - Agent logs error, sleeps, retries on next interval
- **Runaway process** - Watcher terminates agent, restarts from main
- **Log explosion** - Watcher terminates agent, restarts from main
- **Repeated crashes** - After 5 crashes in 60 minutes, watcher stops and alerts PM via COMMS.md