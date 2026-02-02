"""Tests for the Runner class."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofram.runner import Runner


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
        with patch.dict(os.environ, {}, clear=True):
            runner = Runner()
            assert runner.model is None


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
        max_seconds = runner.WORK_INTERVAL_MINUTES * 60
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
    """Tests for Runner.truncate_for_display."""

    def test_short_text_unchanged(self):
        """Short text should be returned unchanged."""
        runner = Runner()
        text = "short"
        result = runner.truncate_for_display(text)
        assert result == text

    def test_long_text_truncated(self):
        """Long text should be truncated with ellipsis."""
        runner = Runner()
        text = "x" * 500
        result = runner.truncate_for_display(text)

        assert len(result) < len(text)
        assert result.endswith("...")

    def test_truncation_length(self):
        """Should truncate to DISPLAY_TRUNCATE_LENGTH."""
        runner = Runner()
        text = "x" * 500
        result = runner.truncate_for_display(text)

        expected_length = runner.DISPLAY_TRUNCATE_LENGTH + 3  # +3 for "..."
        assert len(result) == expected_length


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
        with patch.dict(os.environ, {}, clear=True):
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


class TestLogBootstrap:
    """Tests for Runner.log_bootstrap."""

    @patch("autofram.runner.Git.get_current_branch", return_value="main")
    @patch("autofram.runner.FileSystem.format_timestamp", return_value="2024-01-15T10:00:00Z")
    def test_writes_to_bootstrap_log(self, mock_timestamp, mock_branch, tmp_path):
        """Should write status to bootstrap.log."""
        runner = Runner(working_dir=tmp_path)
        runner.log_bootstrap("BOOTSTRAPPING")

        log_content = runner.bootstrap_log.read_text()
        assert "BOOTSTRAPPING" in log_content
        assert "2024-01-15T10:00:00Z" in log_content
        assert "main" in log_content

    @patch("autofram.runner.Git.get_current_branch", return_value="main")
    @patch("autofram.runner.FileSystem.format_timestamp", return_value="2024-01-15T10:00:00Z")
    def test_creates_logs_directory(self, mock_timestamp, mock_branch, tmp_path):
        """Should create logs directory if needed."""
        runner = Runner(working_dir=tmp_path)
        assert not runner.logs_dir.exists()

        runner.log_bootstrap("TEST")

        assert runner.logs_dir.exists()
