# Autofram

A sandboxed, self-modifying AI agent that communicates with the outside world exclusively through git.

## How It Works

The agent runs in an isolated container and communicates via a shared bare git repository:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ~/autofram-remote/        (bare repo - the shared "hub")  │
│         ▲           ▲                                       │
│         │           │                                       │
│    push/pull    push/pull                                   │
│         │           │                                       │
│         ▼           ▼                                       │
│   Container      ~/autofram-working/   (your working copy)  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

- **Bare repo** (`~/autofram-remote/`): A hub with no working tree. You never edit files here directly.
- **Container**: The agent clones from the bare repo, does work, and pushes changes back.
- **Your working copy** (`~/autofram-working/`): Where you edit `COMMS.md` to give directives and pull to see the agent's responses.

## Prerequisites

- Podman

## Setup

1. Create your environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and configure:

```
OPENROUTER_API_KEY=your_key_here
AUTOFRAM_REMOTE=~/autofram-remote
```

3. Create the bare git repository (use the path from `AUTOFRAM_REMOTE`):

```bash
git init --bare -b main ~/autofram-remote
```

4. Push this repository to the remote:

```bash
git remote add agent ~/autofram-remote
git push agent main
```

5. Build the container:

```bash
./launcher.sh build
```

## Running the Agent

Start the agent:

```bash
./launcher.sh run
```

## Administration Commands

### View logs

```bash
./launcher.sh logs
```

### Shell into the container

```bash
./launcher.sh shell
```

### Stop the agent

```bash
./launcher.sh stop
```

### View agent working directory (from inside container)

```bash
ls -la /agent/main/autofram/
```

### View bootstrap log (from inside container)

```bash
cat /agent/main/autofram/logs/bootstrap.log
```

### View error log (from inside container)

```bash
cat /agent/main/autofram/logs/errors.log
```

### View watcher log (from inside container)

```bash
cat /agent/main/autofram/logs/watcher.log
```

## Communicating with the Agent

1. Clone the working copy (one-time setup):

```bash
git clone ~/autofram-remote ~/autofram-working
cd ~/autofram-working
```

2. Edit `COMMS.md` with your directives:

```bash
vim COMMS.md
```

3. Push your changes:

```bash
git add COMMS.md && git commit -m "Add directive" && git push
```

4. The agent checks for updates every 10 minutes (aligned to :00, :10, :20, etc.)

5. Pull to see agent responses:

```bash
git pull
cat COMMS.md
```

## Status Server

The container exposes a status endpoint at `http://localhost:8080/status`:

```bash
curl localhost:8080/status
```

Returns:
```
timestamp: 2024-01-15 10:30:45
branch: main
watcher: pid=123 status=sleeping uptime=1h 5m 30s
runner: pid=456 status=running uptime=0h 58m 12s
```

## Environment Variables

All variables are required. See `.env.example` for reference.

| Variable | Description |
|----------|-------------|
| OPENROUTER_API_KEY | API key for OpenRouter |
| OPENROUTER_MODEL | Model identifier (e.g., `anthropic/claude-sonnet-4-5`) |
| GIT_USER_NAME | Git commit author name |
| GIT_USER_EMAIL | Git commit author email |
| AUTOFRAM_REMOTE | Path to bare git repo |
