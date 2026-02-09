"""Tests for the Watcher class."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofram.watcher import Watcher


class TestWatcherInit:
    """Tests for Watcher initialization."""

    def test_default_main_dir(self):
        """Should use Git.get_branch_dir('main') as default."""
        with patch("autofram.watcher.Git.get_branch_dir") as mock_get_dir:
            mock_get_dir.return_value = Path("/home/agent/main/autofram")
            watcher = Watcher()
            mock_get_dir.assert_called_once_with("main")
            assert watcher.main_dir == Path("/home/agent/main/autofram")

    def test_custom_main_dir(self, tmp_path):
        """Should accept custom main directory."""
        watcher = Watcher(main_dir=tmp_path)
        assert watcher.main_dir == tmp_path

    def test_paths_relative_to_main_dir(self, tmp_path):
        """Paths should be relative to main directory."""
        watcher = Watcher(main_dir=tmp_path)
        assert watcher.logs_dir == tmp_path / "logs"
        assert watcher.watcher_log == tmp_path / "logs" / "watcher.log"
        assert watcher.errors_log == tmp_path / "logs" / "errors.log"
        assert watcher.comms_md == tmp_path / "COMMS.md"

    def test_initial_state(self, tmp_path):
        """Should initialize with empty state."""
        watcher = Watcher(main_dir=tmp_path)
        assert watcher.crash_times == []
        assert watcher.high_cpu_start is None


class TestResetCpuTracking:
    """Tests for Watcher.reset_cpu_tracking."""

    def test_resets_high_cpu_start(self, tmp_path):
        """Should reset high_cpu_start to None."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.high_cpu_start = datetime.now()

        watcher.reset_cpu_tracking()

        assert watcher.high_cpu_start is None


class TestRecordCrash:
    """Tests for Watcher.record_crash."""

    def test_adds_crash_time(self, tmp_path):
        """Should add current time to crash_times."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)

        initial_count = len(watcher.crash_times)
        watcher.record_crash()

        assert len(watcher.crash_times) == initial_count + 1

    def test_returns_false_under_limit(self, tmp_path):
        """Should return False when under crash limit."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)

        result = watcher.record_crash()

        assert result is False

    def test_returns_true_at_limit(self, tmp_path):
        """Should return True when crash limit reached."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)

        # Add crashes up to limit - 1
        for _ in range(watcher.CRASH_LIMIT - 1):
            watcher.crash_times.append(datetime.now())

        # This should hit the limit
        result = watcher.record_crash()

        assert result is True

    def test_removes_old_crashes(self, tmp_path):
        """Should remove crashes outside the window."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)

        # Add old crash outside window
        old_time = datetime.now() - timedelta(seconds=watcher.CRASH_WINDOW_SECONDS + 100)
        watcher.crash_times.append(old_time)

        watcher.record_crash()

        # Old crash should be removed
        assert old_time not in watcher.crash_times


class TestIsRunnerCmdline:
    """Tests for Watcher.is_runner_cmdline."""

    def test_detects_runner(self, tmp_path):
        """Should detect runner.py in command line."""
        watcher = Watcher(main_dir=tmp_path)
        cmdline = ["python", "/path/to/runner.py"]

        assert watcher.is_runner_cmdline(cmdline) is True

    def test_rejects_watcher(self, tmp_path):
        """Should reject watcher.py even if runner.py present."""
        watcher = Watcher(main_dir=tmp_path)
        cmdline = ["python", "watcher.py", "runner.py"]

        assert watcher.is_runner_cmdline(cmdline) is False

    def test_rejects_other_processes(self, tmp_path):
        """Should reject processes without runner.py."""
        watcher = Watcher(main_dir=tmp_path)
        cmdline = ["python", "other_script.py"]

        assert watcher.is_runner_cmdline(cmdline) is False


class TestFindLastBootstrapIndex:
    """Tests for Watcher.find_last_bootstrap_index."""

    def test_finds_last_bootstrap(self, tmp_path):
        """Should find index of last BOOTSTRAPPING entry."""
        watcher = Watcher(main_dir=tmp_path)
        lines = [
            "BOOTSTRAPPING 2024-01-01",
            "SUCCESS 2024-01-01",
            "BOOTSTRAPPING 2024-01-02",
            "SUCCESS 2024-01-02",
        ]

        result = watcher.find_last_bootstrap_index(lines)

        assert result == 2

    def test_returns_negative_one_if_not_found(self, tmp_path):
        """Should return -1 if no BOOTSTRAPPING found."""
        watcher = Watcher(main_dir=tmp_path)
        lines = ["SUCCESS 2024-01-01", "other content"]

        result = watcher.find_last_bootstrap_index(lines)

        assert result == -1


class TestHasSuccessAfter:
    """Tests for Watcher.has_success_after."""

    def test_finds_success(self, tmp_path):
        """Should find SUCCESS after given index."""
        watcher = Watcher(main_dir=tmp_path)
        lines = ["BOOTSTRAPPING", "other", "SUCCESS"]

        result = watcher.has_success_after(lines, 0)

        assert result is True

    def test_no_success_found(self, tmp_path):
        """Should return False if no SUCCESS after index."""
        watcher = Watcher(main_dir=tmp_path)
        lines = ["BOOTSTRAPPING", "other", "FAILED"]

        result = watcher.has_success_after(lines, 0)

        assert result is False


class TestCheckBootstrapSuccess:
    """Tests for Watcher.check_bootstrap_success."""

    def test_returns_false_if_no_log(self, tmp_path):
        """Should return False if bootstrap.log doesn't exist."""
        watcher = Watcher(main_dir=tmp_path)

        result = watcher.check_bootstrap_success()

        assert result is False

    def test_returns_true_for_successful_bootstrap(self, tmp_path):
        """Should return True if last bootstrap was successful."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        watcher.bootstrap_log.write_text("BOOTSTRAPPING 2024-01-01\nSUCCESS 2024-01-01\n")

        result = watcher.check_bootstrap_success()

        assert result is True

    def test_returns_false_for_failed_bootstrap(self, tmp_path):
        """Should return False if last bootstrap failed."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        watcher.bootstrap_log.write_text("BOOTSTRAPPING 2024-01-01\nFAILED 2024-01-01\n")

        result = watcher.check_bootstrap_success()

        assert result is False


class TestCheckLogSize:
    """Tests for Watcher.check_log_size."""

    def test_returns_none_if_no_log(self, tmp_path):
        """Should return None if errors.log doesn't exist."""
        watcher = Watcher(main_dir=tmp_path)

        result = watcher.check_log_size()

        assert result is None

    def test_returns_none_for_small_log(self, tmp_path):
        """Should return None if log is under limit."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        watcher.errors_log.write_text("small content")

        result = watcher.check_log_size()

        assert result is None

    def test_returns_error_for_large_log(self, tmp_path):
        """Should return error message if log exceeds limit."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        # Write content larger than LOG_SIZE_LIMIT (1MB)
        watcher.errors_log.write_text("x" * (watcher.LOG_SIZE_LIMIT + 100))

        result = watcher.check_log_size()

        assert result is not None
        assert "Log explosion" in result


class TestLog:
    """Tests for Watcher.log."""

    @patch("autofram.watcher.FileSystem.format_local_timestamp", return_value="2024-01-15 10:00:00")
    def test_writes_to_log_file(self, mock_timestamp, tmp_path):
        """Should write message to watcher.log."""
        watcher = Watcher(main_dir=tmp_path)

        watcher.log("test message")

        log_content = watcher.watcher_log.read_text()
        assert "test message" in log_content
        assert "2024-01-15 10:00:00" in log_content

    @patch("autofram.watcher.FileSystem.format_local_timestamp", return_value="2024-01-15 10:00:00")
    def test_creates_logs_directory(self, mock_timestamp, tmp_path):
        """Should create logs directory if needed."""
        watcher = Watcher(main_dir=tmp_path)
        assert not watcher.logs_dir.exists()

        watcher.log("test")

        assert watcher.logs_dir.exists()


class TestCheckCpuHealth:
    """Tests for Watcher.check_cpu_health."""

    def test_returns_none_for_normal_cpu(self, tmp_path):
        """Should return None for CPU under threshold."""
        watcher = Watcher(main_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 50.0

        result = watcher.check_cpu_health(mock_proc)

        assert result is None

    def test_starts_tracking_high_cpu(self, tmp_path):
        """Should start tracking when CPU exceeds threshold."""
        watcher = Watcher(main_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 99.0

        watcher.check_cpu_health(mock_proc)

        assert watcher.high_cpu_start is not None

    def test_returns_error_after_duration(self, tmp_path):
        """Should return error after sustained high CPU."""
        watcher = Watcher(main_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 99.0

        # Simulate high CPU started long ago
        watcher.high_cpu_start = datetime.now() - timedelta(seconds=watcher.CPU_DURATION + 10)

        result = watcher.check_cpu_health(mock_proc)

        assert result is not None
        assert "CPU runaway" in result

    def test_resets_on_normal_cpu(self, tmp_path):
        """Should reset tracking when CPU returns to normal."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.high_cpu_start = datetime.now()
        mock_proc = MagicMock()
        mock_proc.cpu_percent.return_value = 50.0

        watcher.check_cpu_health(mock_proc)

        assert watcher.high_cpu_start is None


class TestTerminateProcess:
    """Tests for Watcher.terminate_process."""

    def test_terminates_process(self, tmp_path):
        """Should call terminate on process."""
        watcher = Watcher(main_dir=tmp_path)
        mock_proc = MagicMock()

        watcher.terminate_process(mock_proc)

        mock_proc.terminate.assert_called_once()

    def test_kills_on_timeout(self, tmp_path):
        """Should kill process if terminate times out."""
        import psutil

        watcher = Watcher(main_dir=tmp_path)
        mock_proc = MagicMock()
        mock_proc.wait.side_effect = psutil.TimeoutExpired(10)

        watcher.terminate_process(mock_proc)

        mock_proc.kill.assert_called_once()


class TestCommitAndPushFile:
    """Tests for Watcher.commit_and_push_file."""

    @patch("autofram.watcher.Git.run")
    def test_runs_git_commands(self, mock_git_run, tmp_path):
        """Should run add, commit, and push commands."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        filepath = tmp_path / "test.txt"
        filepath.write_text("content")

        result = watcher.commit_and_push_file(filepath, "test commit")

        assert result is True
        assert mock_git_run.call_count == 3

    @patch("autofram.watcher.Git.run")
    def test_returns_false_on_error(self, mock_git_run, tmp_path):
        """Should return False on git error."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        mock_git_run.side_effect = Exception("git error")

        result = watcher.commit_and_push_file(Path("test.txt"), "commit")

        assert result is False


class TestIsBootstrapInProgress:
    """Tests for Watcher.is_bootstrap_in_progress."""

    def test_returns_false_when_no_touch_file(self, tmp_path):
        """Should return False when touch file doesn't exist."""
        watcher = Watcher(main_dir=tmp_path)
        assert watcher.is_bootstrap_in_progress() is False

    def test_returns_true_for_recent_touch_file(self, tmp_path):
        """Should return True when touch file is fresh."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        (watcher.logs_dir / "bootstrapping").touch()

        assert watcher.is_bootstrap_in_progress() is True

    def test_returns_false_for_stale_touch_file(self, tmp_path):
        """Should return False when touch file is older than grace period."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        touch_file = watcher.logs_dir / "bootstrapping"
        touch_file.touch()

        # Backdate the file past the grace period
        stale_time = time.time() - watcher.BOOTSTRAP_GRACE_SECONDS - 10
        import os
        os.utime(touch_file, (stale_time, stale_time))

        assert watcher.is_bootstrap_in_progress() is False


class TestHandleMissingRunnerWithBootstrap:
    """Tests for handle_missing_runner bootstrap grace period."""

    @patch("autofram.watcher.FileSystem.format_local_timestamp", return_value="2024-01-15 10:00:00")
    def test_skips_when_bootstrap_in_progress(self, mock_timestamp, tmp_path):
        """Should not launch runner when bootstrap is in progress."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        (watcher.logs_dir / "bootstrapping").touch()

        watcher.handle_missing_runner()

        # Should not have recorded a crash
        assert len(watcher.crash_times) == 0

    @patch("autofram.watcher.FileSystem.format_local_timestamp", return_value="2024-01-15 10:00:00")
    def test_proceeds_when_no_bootstrap(self, mock_timestamp, tmp_path):
        """Should proceed with crash handling when no bootstrap in progress."""
        watcher = Watcher(main_dir=tmp_path)
        watcher.logs_dir.mkdir(parents=True)
        watcher.bootstrap_log.write_text("BOOTSTRAPPING\nSUCCESS\n")

        with patch.object(watcher, "handle_crash_and_restart") as mock_restart:
            watcher.handle_missing_runner()
            mock_restart.assert_called_once()


class TestLaunchRunnerNoSync:
    """Tests for launch_runner without Git.sync."""

    @patch("autofram.watcher.Git.sync")
    @patch("subprocess.Popen")
    @patch("autofram.watcher.FileSystem.format_local_timestamp", return_value="2024-01-15 10:00:00")
    def test_does_not_call_git_sync(self, mock_timestamp, mock_popen, mock_sync, tmp_path):
        """Should not call Git.sync when launching runner."""
        watcher = Watcher(main_dir=tmp_path)
        runner_path = tmp_path / "src" / "autofram" / "runner.py"
        runner_path.parent.mkdir(parents=True)
        runner_path.write_text("# runner")

        watcher.launch_runner()

        mock_sync.assert_not_called()
        mock_popen.assert_called_once()
