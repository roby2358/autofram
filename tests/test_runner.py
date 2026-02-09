"""Tests for the Runner class."""

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofram.runner import Runner, logger as runner_logger
from autofram.logger_out import log_bootstrap, setup_logging


@pytest.fixture(autouse=True)
def runner_env():
    """Ensure WORK_INTERVAL_MINUTES is set for all runner tests."""
    with patch.dict(os.environ, {"WORK_INTERVAL_MINUTES": "10"}):
        yield


class TestRunnerInit:
    """Tests for Runner initialization."""

    def test_default_working_dir_is_cwd(self):
        """Should use cwd as default working directory."""
        runner = Runner()
        assert runner.working_dir == Path.cwd()

    def test_custom_working_dir(self, tmp_path):
        """Should accept custom working directory."""
        runner = Runner(working_dir=tmp_path)
        assert runner.working_dir == tmp_path

    def test_paths_relative_to_working_dir(self, tmp_path):
        """Paths should be relative to working directory."""
        runner = Runner(working_dir=tmp_path)
        assert runner.system_md == tmp_path / "static" / "prompts" / "SYSTEM.md"
        assert runner.comms_md == tmp_path / "COMMS.md"
        assert runner.logs_dir == tmp_path / "logs"

    def test_reads_api_key_from_env(self):
        """Should read API key from environment."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            runner = Runner()
            assert runner.api_key == "test-key"

    def test_reads_model_from_env(self):
        """Should read model from environment."""
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "custom-model"}):
            runner = Runner()
            assert runner.model == "custom-model"

    def test_model_none_when_not_set(self):
        """Should have None model if not in environment."""
        with patch.dict(os.environ, {"WORK_INTERVAL_MINUTES": "10"}, clear=True):
            runner = Runner()
            assert runner.model is None


class TestHashComms:
    """Tests for Runner.hash_comms."""

    def test_returns_none_when_missing(self, tmp_path):
        """Should return None when COMMS.md doesn't exist."""
        runner = Runner(working_dir=tmp_path)
        assert runner.hash_comms() is None

    def test_returns_hash_when_exists(self, tmp_path):
        """Should return SHA-256 hash of COMMS.md contents."""
        (tmp_path / "COMMS.md").write_text("task list")
        runner = Runner(working_dir=tmp_path)

        result = runner.hash_comms()
        expected = hashlib.sha256(b"task list").hexdigest()
        assert result == expected

    def test_different_content_different_hash(self, tmp_path):
        """Should return different hash for different content."""
        (tmp_path / "COMMS.md").write_text("version 1")
        runner = Runner(working_dir=tmp_path)
        hash_v1 = runner.hash_comms()

        (tmp_path / "COMMS.md").write_text("version 2")
        hash_v2 = runner.hash_comms()

        assert hash_v1 != hash_v2

    def test_same_content_same_hash(self, tmp_path):
        """Should return identical hash for identical content."""
        (tmp_path / "COMMS.md").write_text("stable")
        runner = Runner(working_dir=tmp_path)

        assert runner.hash_comms() == runner.hash_comms()


class TestPullLatest:
    """Tests for Runner.pull_latest."""

    @patch("autofram.runner.Git.run")
    def test_calls_git_pull(self, mock_git_run, tmp_path):
        """Should call git pull --ff-only."""
        runner = Runner(working_dir=tmp_path)
        runner.pull_latest()

        mock_git_run.assert_called_once_with(
            ["pull", "--ff-only"], cwd=tmp_path, check=False
        )


class TestRunSingleIteration:
    """Tests for Runner.run_single_iteration skip behavior."""

    @patch("autofram.runner.Git.run")
    def test_skips_when_comms_unchanged(self, mock_git_run, tmp_path):
        """Should skip LLM call when COMMS.md hash matches."""
        (tmp_path / "COMMS.md").write_text("no changes")
        runner = Runner(working_dir=tmp_path)
        runner._last_comms_hash = hashlib.sha256(b"no changes").hexdigest()
        runner.client = MagicMock()

        runner.run_single_iteration()

        runner.client.chat.completions.create.assert_not_called()

    @patch("autofram.runner.Git.run")
    def test_runs_when_comms_changed(self, mock_git_run, tmp_path):
        """Should call LLM when COMMS.md hash differs."""
        prompts_dir = tmp_path / "static" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "SYSTEM.md").write_text("system")
        (tmp_path / "COMMS.md").write_text("new task")
        (tmp_path / "logs").mkdir()

        runner = Runner(working_dir=tmp_path)
        runner._last_comms_hash = "stale-hash"
        runner.client = MagicMock()
        runner.tools = []

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Done"
        mock_message.model_dump.return_value = {"role": "assistant", "content": "Done"}
        runner.client.chat.completions.create.return_value.choices = [
            MagicMock(message=mock_message)
        ]

        runner.run_single_iteration()

        runner.client.chat.completions.create.assert_called_once()

    @patch("autofram.runner.Git.run")
    def test_runs_on_first_iteration(self, mock_git_run, tmp_path):
        """Should always run when _last_comms_hash is None."""
        prompts_dir = tmp_path / "static" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "SYSTEM.md").write_text("system")
        (tmp_path / "COMMS.md").write_text("task")
        (tmp_path / "logs").mkdir()

        runner = Runner(working_dir=tmp_path)
        runner.client = MagicMock()
        runner.tools = []

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Done"
        mock_message.model_dump.return_value = {"role": "assistant", "content": "Done"}
        runner.client.chat.completions.create.return_value.choices = [
            MagicMock(message=mock_message)
        ]

        assert runner._last_comms_hash is None
        runner.run_single_iteration()

        runner.client.chat.completions.create.assert_called_once()

    @patch("autofram.runner.Git.run")
    def test_updates_hash_after_iteration(self, mock_git_run, tmp_path):
        """Should update _last_comms_hash after a successful iteration."""
        prompts_dir = tmp_path / "static" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "SYSTEM.md").write_text("system")
        (tmp_path / "COMMS.md").write_text("task")
        (tmp_path / "logs").mkdir()

        runner = Runner(working_dir=tmp_path)
        runner.client = MagicMock()
        runner.tools = []

        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "Done"
        mock_message.model_dump.return_value = {"role": "assistant", "content": "Done"}
        runner.client.chat.completions.create.return_value.choices = [
            MagicMock(message=mock_message)
        ]

        runner.run_single_iteration()

        expected = hashlib.sha256(b"task").hexdigest()
        assert runner._last_comms_hash == expected


class TestLoadFileContent:
    """Tests for Runner.load_file_content."""

    def test_loads_existing_file(self, tmp_path):
        """Should load content from existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        runner = Runner(working_dir=tmp_path)
        result = runner.load_file_content(test_file, "default")
        assert result == "content"

    def test_returns_default_for_missing_file(self, tmp_path):
        """Should return default for missing file."""
        missing_file = tmp_path / "missing.txt"

        runner = Runner(working_dir=tmp_path)
        result = runner.load_file_content(missing_file, "default value")
        assert result == "default value"


class TestLoadSystemPrompt:
    """Tests for Runner.load_system_prompt."""

    def test_combines_system_and_comms(self, tmp_path):
        """Should combine SYSTEM.md and COMMS.md."""
        # Create directory structure
        prompts_dir = tmp_path / "static" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "SYSTEM.md").write_text("System content")
        (tmp_path / "COMMS.md").write_text("Comms content")

        runner = Runner(working_dir=tmp_path)
        result = runner.load_system_prompt()

        assert "System content" in result
        assert "Comms content" in result
        assert "COMMS.md" in result

    def test_uses_defaults_when_files_missing(self, tmp_path):
        """Should use defaults when files don't exist."""
        runner = Runner(working_dir=tmp_path)
        result = runner.load_system_prompt()

        assert "No SYSTEM.md found" in result
        assert "No COMMS.md found" in result


class TestCalculateSleepSeconds:
    """Tests for Runner.calculate_sleep_seconds."""

    def test_returns_positive_number(self):
        """Should return a positive number."""
        runner = Runner()
        result = runner.calculate_sleep_seconds()
        assert result >= 0

    def test_max_is_interval_minutes(self):
        """Should return at most interval minutes in seconds."""
        runner = Runner()
        result = runner.calculate_sleep_seconds()
        max_seconds = runner.work_interval_minutes * 60
        assert result <= max_seconds

    @patch("autofram.runner.datetime")
    def test_calculates_to_next_interval(self, mock_datetime):
        """Should calculate time to next 10-minute boundary."""
        # Mock time as 10:03:00
        mock_now = datetime(2024, 1, 15, 10, 3, 0)
        mock_datetime.now.return_value = mock_now

        runner = Runner()
        result = runner.calculate_sleep_seconds()

        # Should be about 7 minutes (420 seconds) to 10:10
        assert 400 <= result <= 440


class TestTruncateForDisplay:
    """Tests for truncate_for_display."""

    def test_short_text_unchanged(self):
        from autofram.logger_out import truncate_for_display
        assert truncate_for_display("short") == "short"

    def test_long_text_truncated(self):
        from autofram.logger_out import truncate_for_display
        result = truncate_for_display("x" * 500)
        assert len(result) < 500
        assert result.endswith("...")

    def test_truncation_length(self):
        from autofram.logger_out import truncate_for_display, MAX_DISPLAY_LENGTH
        result = truncate_for_display("x" * 500)
        assert len(result) == MAX_DISPLAY_LENGTH + 3


class TestBuildMessages:
    """Tests for Runner.build_messages."""

    def test_returns_list(self):
        """Should return a list."""
        runner = Runner()
        result = runner.build_messages("system prompt")
        assert isinstance(result, list)

    def test_contains_system_message(self):
        """Should contain system message."""
        runner = Runner()
        result = runner.build_messages("system prompt")

        system_msg = next(m for m in result if m["role"] == "system")
        assert system_msg["content"] == "system prompt"

    def test_contains_user_message(self):
        """Should contain user message with 'Continue.'"""
        runner = Runner()
        result = runner.build_messages("system prompt")

        user_msg = next(m for m in result if m["role"] == "user")
        assert user_msg["content"] == "Continue."

    def test_message_order(self):
        """System message should come before user message."""
        runner = Runner()
        result = runner.build_messages("system prompt")

        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"


class TestCreateClient:
    """Tests for Runner.create_client."""

    @patch("autofram.runner.OpenAI")
    def test_creates_client_with_api_key(self, mock_openai):
        """Should create client with API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            runner = Runner()
            runner.create_client()

            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["api_key"] == "test-key"

    @patch("autofram.runner.OpenAI")
    def test_uses_openrouter_base_url(self, mock_openai):
        """Should use OpenRouter base URL."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            runner = Runner()
            runner.create_client()

            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["base_url"] == Runner.OPENROUTER_BASE_URL

    def test_exits_without_api_key(self):
        """Should exit if API key not set."""
        with patch.dict(os.environ, {"WORK_INTERVAL_MINUTES": "10"}, clear=True):
            runner = Runner()
            runner.api_key = None

            with pytest.raises(SystemExit):
                runner.create_client()


class TestExecuteToolCall:
    """Tests for Runner.execute_tool_call."""

    def test_returns_tool_message(self, tmp_path):
        """Should return a tool message dict."""
        runner = Runner(working_dir=tmp_path)

        # Create mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = json.dumps({"path": "test.txt"})

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = runner.execute_tool_call(mock_tool_call)

        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_123"
        assert result["content"] == "content"

    def test_handles_tool_error(self, tmp_path):
        """Should handle tool execution errors."""
        runner = Runner(working_dir=tmp_path)

        # Create mock tool call for missing file
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "read_file"
        mock_tool_call.function.arguments = json.dumps({"path": "missing.txt"})

        missing_file = tmp_path / "missing.txt"
        with patch("autofram.tools.FileSystem.resolve_path", return_value=missing_file):
            result = runner.execute_tool_call(mock_tool_call)

        assert "Error:" in result["content"]
        assert "FileNotFoundError" in result["content"]


class TestSetupLogging:
    """Tests for Runner.setup_logging."""

    def _cleanup_logger(self):
        """Remove all handlers from the runner logger."""
        for h in runner_logger.handlers[:]:
            runner_logger.removeHandler(h)
            h.close()

    def test_creates_logs_directory(self, tmp_path):
        """Should create logs directory."""
        runner = Runner(working_dir=tmp_path)
        assert not runner.logs_dir.exists()

        setup_logging(runner.logs_dir)

        assert runner.logs_dir.exists()
        self._cleanup_logger()

    def test_adds_console_and_file_handlers(self, tmp_path):
        """Should add both a StreamHandler and a RotatingFileHandler."""
        self._cleanup_logger()
        runner = Runner(working_dir=tmp_path)

        setup_logging(runner.logs_dir)

        handler_types = [type(h) for h in runner_logger.handlers]
        assert logging.StreamHandler in handler_types
        from logging.handlers import RotatingFileHandler
        assert RotatingFileHandler in handler_types
        self._cleanup_logger()

    def test_logger_writes_to_file(self, tmp_path):
        """Should write log messages to runner.log."""
        self._cleanup_logger()
        runner = Runner(working_dir=tmp_path)

        setup_logging(runner.logs_dir)
        runner_logger.info("test log message")

        for h in runner_logger.handlers:
            h.flush()

        log_content = (runner.logs_dir / "runner.log").read_text()
        assert "test log message" in log_content
        self._cleanup_logger()

    def test_sets_info_level(self, tmp_path):
        """Should set logger to INFO level."""
        runner = Runner(working_dir=tmp_path)

        setup_logging(runner.logs_dir)

        assert runner_logger.level == logging.INFO
        self._cleanup_logger()


class TestLogBootstrap:
    """Tests for Runner.log_bootstrap."""

    @patch("autofram.logger_out.Git.get_current_branch", return_value="main")
    @patch("autofram.logger_out.FileSystem.format_timestamp", return_value="2024-01-15T10:00:00Z")
    def test_writes_to_bootstrap_log(self, mock_timestamp, mock_branch, tmp_path):
        """Should write status to bootstrap.log."""
        runner = Runner(working_dir=tmp_path)
        log_bootstrap(runner.logs_dir, runner.bootstrap_log, runner.working_dir, "BOOTSTRAPPING")

        log_content = runner.bootstrap_log.read_text()
        assert "BOOTSTRAPPING" in log_content
        assert "2024-01-15T10:00:00Z" in log_content
        assert "main" in log_content

    @patch("autofram.logger_out.Git.get_current_branch", return_value="main")
    @patch("autofram.logger_out.FileSystem.format_timestamp", return_value="2024-01-15T10:00:00Z")
    def test_creates_logs_directory(self, mock_timestamp, mock_branch, tmp_path):
        """Should create logs directory if needed."""
        runner = Runner(working_dir=tmp_path)
        assert not runner.logs_dir.exists()

        log_bootstrap(runner.logs_dir, runner.bootstrap_log, runner.working_dir, "TEST")

        assert runner.logs_dir.exists()
