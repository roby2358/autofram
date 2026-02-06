"""Tests for the FileSystem class."""

import re
from pathlib import Path

import pytest

from autofram.filesystem import LOCAL_FORMAT, UTC_FORMAT, FileSystem


class TestResolvePath:
    """Tests for FileSystem.resolve_path."""

    def test_absolute_path_returned_unchanged(self):
        """Absolute paths should be returned as-is."""
        path = "/absolute/path/to/file.txt"
        result = FileSystem.resolve_path(path, Path("/some/base"))
        assert result == Path(path)

    def test_relative_path_resolved_against_base(self):
        """Relative paths should be resolved against provided base."""
        path = "file.txt"
        base = Path("/custom/base")
        result = FileSystem.resolve_path(path, base)
        assert result == base / path

    def test_absolute_path_ignores_base(self):
        """Absolute paths should ignore the base parameter."""
        path = "/absolute/file.txt"
        base = Path("/custom/base")
        result = FileSystem.resolve_path(path, base)
        assert result == Path(path)

    def test_returns_path_object(self):
        """Result should always be a Path object."""
        result = FileSystem.resolve_path("test.txt", Path.cwd())
        assert isinstance(result, Path)


class TestFormatTimestamp:
    """Tests for FileSystem.format_timestamp."""

    def test_utc_format_is_iso(self):
        """UTC_FORMAT should produce ISO 8601 with Z suffix."""
        result = FileSystem.format_timestamp(UTC_FORMAT)
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert re.match(pattern, result)

    def test_custom_format(self):
        """Custom format should be respected."""
        result = FileSystem.format_timestamp("%Y-%m-%d")
        pattern = r"\d{4}-\d{2}-\d{2}"
        assert re.match(pattern, result)
        assert "T" not in result

    def test_returns_string(self):
        """Result should be a string."""
        result = FileSystem.format_timestamp(UTC_FORMAT)
        assert isinstance(result, str)


class TestFormatLocalTimestamp:
    """Tests for FileSystem.format_local_timestamp."""

    def test_local_format(self):
        """LOCAL_FORMAT should produce YYYY-MM-DD HH:MM:SS."""
        result = FileSystem.format_local_timestamp(LOCAL_FORMAT)
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.match(pattern, result)

    def test_custom_format(self):
        """Custom format should be respected."""
        result = FileSystem.format_local_timestamp("%H:%M")
        pattern = r"\d{2}:\d{2}"
        assert re.match(pattern, result)

    def test_returns_string(self):
        """Result should be a string."""
        result = FileSystem.format_local_timestamp(LOCAL_FORMAT)
        assert isinstance(result, str)
