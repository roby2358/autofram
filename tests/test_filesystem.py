"""Tests for the FileSystem class."""

import re
from pathlib import Path

import pytest

from autofram.filesystem import FileSystem


class TestResolvePath:
    """Tests for FileSystem.resolve_path."""

    def test_absolute_path_returned_unchanged(self):
        """Absolute paths should be returned as-is."""
        path = "/absolute/path/to/file.txt"
        result = FileSystem.resolve_path(path)
        assert result == Path(path)

    def test_relative_path_resolved_against_cwd(self):
        """Relative paths should be resolved against cwd by default."""
        path = "relative/path.txt"
        result = FileSystem.resolve_path(path)
        assert result == Path.cwd() / path

    def test_relative_path_resolved_against_base(self):
        """Relative paths should be resolved against provided base."""
        path = "file.txt"
        base = Path("/custom/base")
        result = FileSystem.resolve_path(path, base=base)
        assert result == base / path

    def test_absolute_path_ignores_base(self):
        """Absolute paths should ignore the base parameter."""
        path = "/absolute/file.txt"
        base = Path("/custom/base")
        result = FileSystem.resolve_path(path, base=base)
        assert result == Path(path)

    def test_returns_path_object(self):
        """Result should always be a Path object."""
        result = FileSystem.resolve_path("test.txt")
        assert isinstance(result, Path)


class TestFormatTimestamp:
    """Tests for FileSystem.format_timestamp."""

    def test_default_format_is_iso(self):
        """Default format should be ISO 8601 with Z suffix."""
        result = FileSystem.format_timestamp()
        # Should match pattern like 2024-01-15T10:30:45Z
        pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
        assert re.match(pattern, result)

    def test_custom_format(self):
        """Custom format should be respected."""
        result = FileSystem.format_timestamp("%Y-%m-%d")
        # Should match pattern like 2024-01-15
        pattern = r"\d{4}-\d{2}-\d{2}"
        assert re.match(pattern, result)
        assert "T" not in result

    def test_returns_string(self):
        """Result should be a string."""
        result = FileSystem.format_timestamp()
        assert isinstance(result, str)


class TestFormatLocalTimestamp:
    """Tests for FileSystem.format_local_timestamp."""

    def test_default_format(self):
        """Default format should be YYYY-MM-DD HH:MM:SS."""
        result = FileSystem.format_local_timestamp()
        # Should match pattern like 2024-01-15 10:30:45
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.match(pattern, result)

    def test_custom_format(self):
        """Custom format should be respected."""
        result = FileSystem.format_local_timestamp("%H:%M")
        # Should match pattern like 10:30
        pattern = r"\d{2}:\d{2}"
        assert re.match(pattern, result)

    def test_returns_string(self):
        """Result should be a string."""
        result = FileSystem.format_local_timestamp()
        assert isinstance(result, str)
