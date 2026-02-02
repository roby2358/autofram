# Autofram

A sandboxed, self-modifying AI agent that communicates with the outside world exclusively through git.

## Prerequisites

- Podman
- A bare git repository for agent communication

## Setup

1. Create your environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and add your OpenRouter API key:

```
OPENROUTER_API_KEY=your_key_here
```

3. Create the bare git repository:

```bash
git init --bare ~/autofram-remote
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

1. Clone the working copy:

```bash
git clone ~/autofram-remote ~/autofram-working
cd ~/autofram-working
```

2. Edit `COMMS.md` with your directives:

```bash
vi COMMS.md
```

3. Push your changes:

```bash
git add COMMS.md
git commit -m "Add directive"
git push
```

4. Pull to see agent responses:

```bash
git pull
cat COMMS.md
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| OPENROUTER_API_KEY | Yes | - | API key for OpenRouter |
| OPENROUTER_MODEL | No | anthropic/claude-sonnet-4-5 | Model identifier |
| GIT_USER_NAME | No | autofram | Git commit author name |
| GIT_USER_EMAIL | No | autofram@localhost | Git commit author email |
| AUTOFRAM_REMOTE | No | ~/autofram-remote | Path to bare git repo |
