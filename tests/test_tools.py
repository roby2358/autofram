"""Tests for the tools module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofram.tools import (
    bash,
    execute_tool,
    format_bash_output,
    get_tools_for_openai,
    mcp,
    read_file,
    write_file,
)


class TestFormatBashOutput:
    """Tests for format_bash_output."""

    def test_stdout_only(self):
        """Should return stdout when only stdout present."""
        result = MagicMock(stdout="output", stderr="", returncode=0)
        output = format_bash_output(result)
        assert output == "output"

    def test_stderr_only(self):
        """Should return stderr when only stderr present."""
        result = MagicMock(stdout="", stderr="error", returncode=0)
        output = format_bash_output(result)
        assert output == "error"

    def test_both_stdout_and_stderr(self):
        """Should combine stdout and stderr."""
        result = MagicMock(stdout="output", stderr="error", returncode=0)
        output = format_bash_output(result)
        assert "output" in output
        assert "error" in output

    def test_nonzero_exit_code(self):
        """Should include exit code when non-zero."""
        result = MagicMock(stdout="", stderr="", returncode=1)
        output = format_bash_output(result)
        assert "[Exit code: 1]" in output

    def test_no_output(self):
        """Should return placeholder when no output."""
        result = MagicMock(stdout="", stderr="", returncode=0)
        output = format_bash_output(result)
        assert output == "[No output]"

    def test_all_parts(self):
        """Should combine all parts correctly."""
        result = MagicMock(stdout="out", stderr="err", returncode=2)
        output = format_bash_output(result)
        assert "out" in output
        assert "err" in output
        assert "[Exit code: 2]" in output


class TestReadFile:
    """Tests for read_file tool."""

    def test_reads_existing_file(self, tmp_path):
        """Should read contents of existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = read_file(str(test_file))

        assert result == "hello world"

    def test_raises_on_missing_file(self, tmp_path):
        """Should raise FileNotFoundError for missing file."""
        missing_file = tmp_path / "missing.txt"

        with patch("autofram.tools.FileSystem.resolve_path", return_value=missing_file):
            with pytest.raises(FileNotFoundError):
                read_file(str(missing_file))


class TestWriteFile:
    """Tests for write_file tool."""

    def test_writes_content(self, tmp_path):
        """Should write content to file."""
        test_file = tmp_path / "test.txt"

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = write_file(str(test_file), "hello world")

        assert test_file.read_text() == "hello world"
        assert "11 bytes" in result

    def test_creates_parent_directories(self, tmp_path):
        """Should create parent directories if needed."""
        test_file = tmp_path / "subdir" / "test.txt"

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            write_file(str(test_file), "content")

        assert test_file.exists()
        assert test_file.read_text() == "content"

    def test_returns_confirmation(self, tmp_path):
        """Should return confirmation message."""
        test_file = tmp_path / "test.txt"

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = write_file(str(test_file), "test")

        assert "Successfully wrote" in result
        assert "4 bytes" in result


class TestBash:
    """Tests for bash tool."""

    @patch("subprocess.run")
    def test_executes_command(self, mock_run):
        """Should execute shell command."""
        mock_run.return_value = MagicMock(stdout="output", stderr="", returncode=0)
        result = bash("echo hello")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == "echo hello"
        assert call_args[1]["shell"] is True

    @patch("subprocess.run")
    def test_captures_output(self, mock_run):
        """Should capture and return output."""
        mock_run.return_value = MagicMock(stdout="hello", stderr="", returncode=0)
        result = bash("echo hello")
        assert result == "hello"

    @patch("subprocess.run")
    def test_uses_timeout(self, mock_run):
        """Should use configured timeout."""
        mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        bash("sleep 1")

        call_args = mock_run.call_args
        assert call_args[1]["timeout"] == 300  # BASH_TIMEOUT


class TestGetToolsForOpenai:
    """Tests for get_tools_for_openai."""

    def test_returns_list(self):
        """Should return a list."""
        result = get_tools_for_openai()
        assert isinstance(result, list)

    def test_wraps_schemas_in_function_type(self):
        """Should wrap each schema with type: function."""
        result = get_tools_for_openai()
        for tool in result:
            assert tool["type"] == "function"
            assert "function" in tool

    def test_contains_all_tools(self):
        """Should contain all defined tools."""
        result = get_tools_for_openai()
        tool_names = [t["function"]["name"] for t in result]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "bash" in tool_names
        assert "bootstrap" in tool_names
        assert "rollback" in tool_names

    def test_tools_have_required_fields(self):
        """Each tool should have name, description, and parameters."""
        result = get_tools_for_openai()
        for tool in result:
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func


class TestExecuteTool:
    """Tests for execute_tool."""

    def test_executes_read_file(self, tmp_path):
        """Should execute read_file tool."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = execute_tool("read_file", {"path": str(test_file)})

        assert result == "content"

    def test_executes_write_file(self, tmp_path):
        """Should execute write_file tool."""
        test_file = tmp_path / "test.txt"

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = execute_tool("write_file", {"path": str(test_file), "content": "hello"})

        assert "Successfully wrote" in result

    def test_raises_on_unknown_tool(self):
        """Should raise ValueError for unknown tool."""
        with pytest.raises(ValueError, match="Unknown tool"):
            execute_tool("nonexistent_tool", {})

    def test_returns_string(self, tmp_path):
        """Should always return a string."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("autofram.tools.FileSystem.resolve_path", return_value=test_file):
            result = execute_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, str)


class TestMcpToolManager:
    """Tests for FastMCP tool registration."""

    def test_tools_registered_in_manager(self):
        """All tools should be registered in FastMCP's tool manager."""
        registered_tools = list(mcp._tool_manager._tools.keys())
        assert "read_file" in registered_tools
        assert "write_file" in registered_tools
        assert "bash" in registered_tools
        assert "bootstrap" in registered_tools
        assert "rollback" in registered_tools

    def test_tool_has_function(self):
        """Each registered tool should have a callable function."""
        for tool in mcp._tool_manager._tools.values():
            assert callable(tool.fn)

    def test_tool_has_parameters(self):
        """Each registered tool should have parameters schema."""
        for tool in mcp._tool_manager._tools.values():
            assert tool.parameters is not None
            assert "type" in tool.parameters
