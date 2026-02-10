"""Tests for the status server."""

import logging
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autofram import server


class TestFindProcessByScript:
    """Tests for find_process_by_script."""

    def test_finds_matching_process(self):
        """Should return process when script name matches."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 123, "cmdline": ["python", "runner.py"]}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            result = server.find_process_by_script("runner.py")
            assert result == mock_proc

    def test_returns_none_when_not_found(self):
        """Should return None when no matching process."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 123, "cmdline": ["python", "other.py"]}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            result = server.find_process_by_script("runner.py")
            assert result is None

    def test_excludes_specified_script(self):
        """Should skip processes matching exclude pattern."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 123, "cmdline": ["python", "watcher.py", "runner.py"]}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            result = server.find_process_by_script("runner.py", exclude="watcher.py")
            assert result is None

    def test_handles_empty_cmdline(self):
        """Should skip processes with empty command line."""
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 123, "cmdline": []}

        with patch("psutil.process_iter", return_value=[mock_proc]):
            result = server.find_process_by_script("runner.py")
            assert result is None


class TestGetProcessInfo:
    """Tests for get_process_info."""

    def test_not_running(self):
        """Should report not running for None process."""
        result = server.get_process_info(None, "runner")
        assert result == "runner: not running"

    def test_running_process(self):
        """Should format running process info."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.status.return_value = "running"
        mock_proc.create_time.return_value = datetime.now().timestamp() - 3661  # 1h 1m 1s ago

        result = server.get_process_info(mock_proc, "runner")

        assert "runner:" in result
        assert "pid=12345" in result
        assert "status=running" in result
        assert "uptime=1h 1m" in result


class TestStatusEndpoint:
    """Tests for the /status endpoint."""

    def test_returns_plain_text(self):
        """Should return plain text response with all fields."""
        with patch.object(server, "BRANCH", "test-branch"):
            with patch.object(server, "find_process_by_script", return_value=None):
                result = server.status()

        assert "timestamp:" in result
        assert "branch: test-branch" in result
        assert "watcher: not running" in result
        assert "runner: not running" in result

    def test_includes_process_info(self):
        """Should include process info when processes are running."""
        mock_watcher = MagicMock()
        mock_watcher.pid = 111
        mock_watcher.status.return_value = "sleeping"
        mock_watcher.create_time.return_value = datetime.now().timestamp() - 60

        mock_runner = MagicMock()
        mock_runner.pid = 222
        mock_runner.status.return_value = "running"
        mock_runner.create_time.return_value = datetime.now().timestamp() - 120

        def mock_find(script, exclude=None):
            if "watcher" in script:
                return mock_watcher
            return mock_runner

        with patch.object(server, "BRANCH", "main"):
            with patch.object(server, "find_process_by_script", side_effect=mock_find):
                result = server.status()

        assert "watcher: pid=111" in result
        assert "runner: pid=222" in result


class TestHelloEndpoint:
    """Tests for the /hello endpoint."""

    def test_returns_hello_world(self):
        """Should return Hello, World! with correct status and content-type."""
        client = TestClient(server.app)
        response = client.get("/hello")

        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


class TestSetupAccessLog:
    """Tests for setup_access_log."""

    def test_creates_log_directory(self, tmp_path):
        """Should create parent directory for the log file."""
        log_path = tmp_path / "logs" / "access.log"
        assert not log_path.parent.exists()

        server.setup_access_log(log_path)

        assert log_path.parent.exists()

    def test_adds_file_handler_to_uvicorn_access_logger(self, tmp_path):
        """Should add a FileHandler to the uvicorn.access logger."""
        log_path = tmp_path / "logs" / "access.log"
        access_logger = logging.getLogger("uvicorn.access")
        initial_handlers = len(access_logger.handlers)

        server.setup_access_log(log_path)

        assert len(access_logger.handlers) == initial_handlers + 1
        added_handler = access_logger.handlers[-1]
        assert isinstance(added_handler, logging.FileHandler)

        # Cleanup
        access_logger.removeHandler(added_handler)
        added_handler.close()

    def test_sets_info_level(self, tmp_path):
        """Should set uvicorn.access logger to INFO level."""
        log_path = tmp_path / "logs" / "access.log"

        server.setup_access_log(log_path)

        access_logger = logging.getLogger("uvicorn.access")
        assert access_logger.level == logging.INFO

        # Cleanup
        for h in access_logger.handlers:
            if isinstance(h, logging.FileHandler):
                access_logger.removeHandler(h)
                h.close()
