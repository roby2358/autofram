"""Git utilities for autofram infrastructure."""

import subprocess
from pathlib import Path


class Git:
    """Git operations wrapper."""

    REMOTE_REPO = Path("/mnt/remote")
    AGENT_DIR = Path("/home/agent")

    @staticmethod
    def get_branch_dir(branch: str) -> Path:
        """Get the working directory for a branch."""
        return Git.AGENT_DIR / branch / "autofram"

    @staticmethod
    def run(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command.

        Args:
            args: Git command arguments (without 'git' prefix)
            cwd: Working directory for the command
            check: Whether to raise on non-zero exit

        Returns:
            CompletedProcess result
        """
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=check,
        )

    @staticmethod
    def get_current_branch(cwd: Path | None = None) -> str:
        """Get the current git branch name.

        Args:
            cwd: Working directory (defaults to cwd)

        Returns:
            Branch name string
        """
        result = Git.run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, check=False)
        return result.stdout.strip()

    @staticmethod
    def sync(cwd: Path, branch: str = "main") -> bool:
        """Fetch and reset to origin branch.

        Args:
            cwd: Working directory
            branch: Branch to sync to

        Returns:
            True if successful, False otherwise
        """
        try:
            Git.run(["fetch", "origin"], cwd=cwd)
            Git.run(["reset", "--hard", f"origin/{branch}"], cwd=cwd)
            return True
        except subprocess.CalledProcessError:
            return False
