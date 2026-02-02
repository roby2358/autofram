"""Filesystem utilities for autofram infrastructure."""

from datetime import datetime
from pathlib import Path


class FileSystem:
    """Filesystem and path operations."""

    @staticmethod
    def resolve_path(path: str, base: Path | None = None) -> Path:
        """Resolve a path to absolute, using base or cwd as reference.

        Args:
            path: The path string to resolve
            base: Base directory for relative paths (defaults to cwd)

        Returns:
            Absolute Path object
        """
        file_path = Path(path)
        if file_path.is_absolute():
            return file_path
        base = base or Path.cwd()
        return base / file_path

    @staticmethod
    def format_timestamp(fmt: str = "%Y-%m-%dT%H:%M:%SZ") -> str:
        """Format current UTC time as a string."""
        return datetime.utcnow().strftime(fmt)

    @staticmethod
    def format_local_timestamp(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format current local time as a string."""
        return datetime.now().strftime(fmt)
