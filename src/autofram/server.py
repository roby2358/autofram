#!/usr/bin/env python3
"""FastAPI status server for the autofram agent."""

import logging
import os
from datetime import datetime
from pathlib import Path

import psutil
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

# Branch is passed via environment variable at startup
BRANCH = os.environ.get("AUTOFRAM_BRANCH", "unknown")


def find_process_by_script(script_name: str, exclude: str | None = None) -> psutil.Process | None:
    """Find a process by script name in command line.

    Args:
        script_name: Script filename to search for (e.g., "runner.py")
        exclude: Script name to exclude from matches

    Returns:
        Process if found, None otherwise
    """
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline", [])
            if not cmdline:
                continue
            cmdline_str = " ".join(cmdline)
            if script_name in cmdline_str:
                if exclude and exclude in cmdline_str:
                    continue
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def get_process_info(proc: psutil.Process | None, name: str) -> str:
    """Get formatted process info string.

    Args:
        proc: Process object or None
        name: Display name for the process

    Returns:
        Formatted status line
    """
    if proc is None:
        return f"{name}: not running"

    try:
        create_time = datetime.fromtimestamp(proc.create_time())
        uptime = datetime.now() - create_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        status = proc.status()
        return f"{name}: pid={proc.pid} status={status} uptime={uptime_str}"
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return f"{name}: not accessible"


@app.get("/status", response_class=PlainTextResponse)
def status() -> str:
    """Return agent status in plain text."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    watcher_proc = find_process_by_script("watcher.py")
    runner_proc = find_process_by_script("runner.py", exclude="watcher.py")

    lines = [
        f"timestamp: {timestamp}",
        f"branch: {BRANCH}",
        get_process_info(watcher_proc, "watcher"),
        get_process_info(runner_proc, "runner"),
    ]

    return "\n".join(lines)


@app.get("/hello", response_class=PlainTextResponse)
def hello() -> str:
    """Return a simple hello world message."""
    return "Hello, World!"


def setup_access_log(log_path: Path) -> None:
    """Configure uvicorn access logging to a file."""
    log_path.parent.mkdir(exist_ok=True)
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.INFO)


def main() -> None:
    """Start the server."""
    import uvicorn

    logs_dir = Path.cwd() / "logs"
    setup_access_log(logs_dir / "access.log")

    port = int(os.environ.get("AUTOFRAM_STATUS_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
