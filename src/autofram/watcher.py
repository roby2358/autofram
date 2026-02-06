#!/usr/bin/env python3
"""Crash recovery monitor for the autofram agent."""

import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

from autofram.filesystem import LOCAL_FORMAT, FileSystem
from autofram.git import Git


class Watcher:
    """Crash recovery monitor for the autofram agent."""

    # Configuration
    CHECK_INTERVAL = 5  # seconds between checks
    CPU_THRESHOLD = 95  # percent
    CPU_DURATION = 60  # seconds of sustained high CPU
    LOG_SIZE_LIMIT = 1 * 1024 * 1024  # 1 MB
    CRASH_LIMIT = 5
    CRASH_WINDOW_SECONDS = 60 * 60  # 60 minutes
    POST_LAUNCH_DELAY = 10  # seconds to wait after launching runner
    POST_CRASH_LIMIT_DELAY = 300  # seconds to wait after hitting crash limit

    def __init__(self, main_dir: Path | None = None):
        """Initialize the watcher.

        Args:
            main_dir: Main branch directory (defaults to Git.get_branch_dir("main"))
        """
        self.main_dir = main_dir or Git.get_branch_dir("main")
        self.logs_dir = self.main_dir / "logs"
        self.watcher_log = self.logs_dir / "watcher.log"
        self.errors_log = self.logs_dir / "errors.log"
        self.bootstrap_log = self.logs_dir / "bootstrap.log"
        self.comms_md = self.main_dir / "COMMS.md"

        # State
        self.crash_times: list[datetime] = []
        self.high_cpu_start: datetime | None = None

    def reset_cpu_tracking(self) -> None:
        """Reset high CPU tracking state."""
        self.high_cpu_start = None

    def record_crash(self) -> bool:
        """Record a crash and return True if limit reached.

        Returns:
            True if crash limit has been reached
        """
        now = datetime.now()
        self.crash_times.append(now)

        # Remove old crashes outside the window
        cutoff = now - timedelta(seconds=self.CRASH_WINDOW_SECONDS)
        self.crash_times = [t for t in self.crash_times if t > cutoff]

        self.log(f"Crash recorded. {len(self.crash_times)} crashes in last {self.CRASH_WINDOW_SECONDS // 60} minutes.")
        return len(self.crash_times) >= self.CRASH_LIMIT

    def log(self, message: str) -> None:
        """Log a message to watcher.log and stdout."""
        self.logs_dir.mkdir(exist_ok=True)
        timestamp = FileSystem.format_local_timestamp(LOCAL_FORMAT)
        log_line = f"[{timestamp}] {message}\n"
        print(log_line, end="")
        with open(self.watcher_log, "a") as f:
            f.write(log_line)

    def find_runner_process(self) -> psutil.Process | None:
        """Find the runner process by scanning for runner.py in command line."""
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = proc.info.get("cmdline", [])
                if cmdline and self.is_runner_cmdline(cmdline):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def is_runner_cmdline(self, cmdline: list[str]) -> bool:
        """Check if a command line belongs to the runner process."""
        cmdline_str = " ".join(cmdline)
        return "runner.py" in cmdline_str and "watcher.py" not in cmdline_str

    def check_bootstrap_success(self) -> bool:
        """Check if the most recent bootstrap was successful."""
        if not self.bootstrap_log.exists():
            return False

        lines = self.bootstrap_log.read_text().strip().split("\n")
        if not lines:
            return False

        last_bootstrap_idx = self.find_last_bootstrap_index(lines)
        if last_bootstrap_idx == -1:
            return False

        return self.has_success_after(lines, last_bootstrap_idx)

    def find_last_bootstrap_index(self, lines: list[str]) -> int:
        """Find the index of the most recent BOOTSTRAPPING entry."""
        last_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("BOOTSTRAPPING"):
                last_idx = i
        return last_idx

    def has_success_after(self, lines: list[str], start_idx: int) -> bool:
        """Check if there's a SUCCESS entry after the given index."""
        for line in lines[start_idx + 1:]:
            if line.startswith("SUCCESS"):
                return True
        return False

    def commit_and_push_file(self, filepath: Path, message: str) -> bool:
        """Stage, commit, and push a single file.

        Returns:
            True if successful
        """
        try:
            Git.run(["add", str(filepath.name)], cwd=self.main_dir, check=False)
            Git.run(["commit", "-m", message], cwd=self.main_dir, check=False)
            Git.run(["push", "origin", "main"], cwd=self.main_dir, check=False)
            return True
        except Exception as e:
            self.log(f"Git operation failed: {e}")
            return False

    def alert_pm(self, message: str) -> None:
        """Alert the PM by appending to COMMS.md and pushing."""
        self.log(f"ALERT: {message}")
        try:
            timestamp = FileSystem.format_local_timestamp(LOCAL_FORMAT)
            alert_text = f"\n\n---\n**WATCHER ALERT** ({timestamp}):\n{message}\n"

            content = self.comms_md.read_text() if self.comms_md.exists() else ""
            self.comms_md.write_text(content + alert_text)

            self.commit_and_push_file(self.comms_md, f"WATCHER ALERT: {message[:50]}")
        except Exception as e:
            self.log(f"Failed to alert PM: {e}")

    def terminate_process(self, proc: psutil.Process) -> None:
        """Gracefully terminate a process, falling back to kill."""
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass

    def launch_runner(self) -> None:
        """Launch the runner from main branch."""
        self.reset_cpu_tracking()
        self.log("Launching runner from main...")

        runner_path = self.main_dir / "src" / "autofram" / "runner.py"
        if not runner_path.exists():
            self.log(f"ERROR: Runner not found at {runner_path}")
            return

        if not Git.sync(self.main_dir, "main"):
            self.log("Warning: git sync failed")

        self.logs_dir.mkdir(exist_ok=True)

        subprocess.Popen(
            [sys.executable, str(runner_path)],
            cwd=self.main_dir,
            start_new_session=True,
        )

        self.log("Runner launched.")

    def check_cpu_health(self, proc: psutil.Process) -> str | None:
        """Check CPU usage and return error if runaway detected."""
        cpu_percent = proc.cpu_percent(interval=1)

        if cpu_percent >= self.CPU_THRESHOLD:
            if self.high_cpu_start is None:
                self.high_cpu_start = datetime.now()
            elif (datetime.now() - self.high_cpu_start).total_seconds() >= self.CPU_DURATION:
                return f"CPU runaway detected ({cpu_percent}% for {self.CPU_DURATION}s)"
        else:
            self.reset_cpu_tracking()

        return None

    def check_log_size(self) -> str | None:
        """Check error log size and return error if explosion detected."""
        if self.errors_log.exists():
            log_size = self.errors_log.stat().st_size
            if log_size > self.LOG_SIZE_LIMIT:
                return f"Log explosion detected ({log_size} bytes)"
        return None

    def check_runner_health(self, proc: psutil.Process) -> str | None:
        """Check runner health, return error message if unhealthy."""
        try:
            cpu_error = self.check_cpu_health(proc)
            if cpu_error:
                return cpu_error

            log_error = self.check_log_size()
            if log_error:
                return log_error

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return "Process no longer accessible"

        return None

    def handle_crash_and_restart(self) -> bool:
        """Handle a crash event and attempt restart.

        Returns:
            True if should continue monitoring, False if crash limit reached
        """
        if self.record_crash():
            self.alert_pm(
                f"Agent has crashed {self.CRASH_LIMIT} times in {self.CRASH_WINDOW_SECONDS // 60} minutes. "
                "Manual intervention required."
            )
            self.log("Crash limit reached. Stopping restart attempts.")
            time.sleep(self.POST_CRASH_LIMIT_DELAY)
            return False

        self.launch_runner()
        time.sleep(self.POST_LAUNCH_DELAY)
        return True

    def handle_missing_runner(self) -> None:
        """Handle case when runner process is not found."""
        self.log("Runner not found!")

        if not self.check_bootstrap_success():
            self.log("Bootstrap failed, falling back to main")

        self.handle_crash_and_restart()

    def handle_unhealthy_runner(self, proc: psutil.Process, error: str) -> None:
        """Handle case when runner is unhealthy."""
        self.log(f"Unhealthy runner: {error}")
        self.terminate_process(proc)
        self.handle_crash_and_restart()

    def monitor_iteration(self) -> None:
        """Run a single iteration of the monitoring loop."""
        proc = self.find_runner_process()

        if proc is None:
            self.handle_missing_runner()
            return

        error = self.check_runner_health(proc)
        if error:
            self.handle_unhealthy_runner(proc, error)

    def run(self) -> None:
        """Main watcher loop."""
        self.log("Watcher starting...")
        time.sleep(5)  # Give the runner a moment to start

        while True:
            try:
                self.monitor_iteration()
            except Exception as e:
                self.log(f"Watcher error: {type(e).__name__}: {e}")

            time.sleep(self.CHECK_INTERVAL)


def main() -> None:
    """Main entry point."""
    watcher = Watcher()
    watcher.run()


if __name__ == "__main__":
    main()
