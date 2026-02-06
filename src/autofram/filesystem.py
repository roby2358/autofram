"""Filesystem utilities for autofram infrastructure."""

from datetime import datetime, UTC
from pathlib import Path


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
LOCAL_FORMAT = "%Y-%m-%d %H:%M:%S"


class FileSystem:
    """Filesystem and path operations."""

    @staticmethod
    def resolve_path(path: str, base: Path) -> Path:
        """Resolve a path to absolute, using base as reference.

        Args:
            path: The path string to resolve
            base: Base directory for relative paths

        Returns:
            Absolute Path object
        """
        file_path = Path(path)
        if file_path.is_absolute():
            return file_path
        return base / file_path

    @staticmethod
    def format_timestamp(fmt: str) -> str:
        """Format current UTC time as a string."""
        return datetime.now(UTC).strftime(fmt)

    @staticmethod
    def format_local_timestamp(fmt: str) -> str:
        """Format current local time as a string."""
        return datetime.now().strftime(fmt)
