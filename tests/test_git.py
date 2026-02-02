"""Tests for the Git class."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autofram.git import Git


class TestConstants:
    """Tests for Git class constants."""

    def test_remote_repo_path(self):
        """REMOTE_REPO should be /mnt/remote."""
        assert Git.REMOTE_REPO == Path("/mnt/remote")

    def test_agent_dir_path(self):
        """AGENT_DIR should be /agent."""
        assert Git.AGENT_DIR == Path("/agent")


class TestGetBranchDir:
    """Tests for Git.get_branch_dir."""

    def test_main_branch_dir(self):
        """Main branch should return /agent/main/autofram."""
        result = Git.get_branch_dir("main")
        assert result == Path("/agent/main/autofram")

    def test_feature_branch_dir(self):
        """Feature branch should return correct path."""
        result = Git.get_branch_dir("feature-x")
        assert result == Path("/agent/feature-x/autofram")

    def test_returns_path_object(self):
        """Result should be a Path object."""
        result = Git.get_branch_dir("test")
        assert isinstance(result, Path)


class TestRun:
    """Tests for Git.run."""

    @patch("subprocess.run")
    def test_prepends_git_to_command(self, mock_run):
        """Git command should be prepended to args."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.run(["status"])
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "status"]

    @patch("subprocess.run")
    def test_passes_cwd(self, mock_run):
        """cwd parameter should be passed through."""
        mock_run.return_value = MagicMock(returncode=0)
        cwd = Path("/test/dir")
        Git.run(["status"], cwd=cwd)
        call_args = mock_run.call_args
        assert call_args[1]["cwd"] == cwd

    @patch("subprocess.run")
    def test_check_true_by_default(self, mock_run):
        """check parameter should be True by default."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.run(["status"])
        call_args = mock_run.call_args
        assert call_args[1]["check"] is True

    @patch("subprocess.run")
    def test_check_false_when_specified(self, mock_run):
        """check parameter should be passed through when False."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.run(["status"], check=False)
        call_args = mock_run.call_args
        assert call_args[1]["check"] is False

    @patch("subprocess.run")
    def test_capture_output_enabled(self, mock_run):
        """capture_output should be enabled."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.run(["status"])
        call_args = mock_run.call_args
        assert call_args[1]["capture_output"] is True

    @patch("subprocess.run")
    def test_text_mode_enabled(self, mock_run):
        """text mode should be enabled."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.run(["status"])
        call_args = mock_run.call_args
        assert call_args[1]["text"] is True


class TestGetCurrentBranch:
    """Tests for Git.get_current_branch."""

    @patch.object(Git, "run")
    def test_returns_branch_name(self, mock_run):
        """Should return the current branch name."""
        mock_run.return_value = MagicMock(stdout="main\n")
        result = Git.get_current_branch()
        assert result == "main"

    @patch.object(Git, "run")
    def test_strips_whitespace(self, mock_run):
        """Should strip whitespace from output."""
        mock_run.return_value = MagicMock(stdout="  feature-branch  \n")
        result = Git.get_current_branch()
        assert result == "feature-branch"

    @patch.object(Git, "run")
    def test_passes_cwd(self, mock_run):
        """Should pass cwd to Git.run."""
        mock_run.return_value = MagicMock(stdout="main\n")
        cwd = Path("/test/dir")
        Git.get_current_branch(cwd=cwd)
        mock_run.assert_called_once_with(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, check=False
        )

    @patch.object(Git, "run")
    def test_uses_check_false(self, mock_run):
        """Should use check=False to handle non-git directories."""
        mock_run.return_value = MagicMock(stdout="main\n")
        Git.get_current_branch()
        call_args = mock_run.call_args
        assert call_args[1]["check"] is False


class TestSync:
    """Tests for Git.sync."""

    @patch.object(Git, "run")
    def test_returns_true_on_success(self, mock_run):
        """Should return True when sync succeeds."""
        mock_run.return_value = MagicMock(returncode=0)
        result = Git.sync(Path("/test"))
        assert result is True

    @patch.object(Git, "run")
    def test_returns_false_on_failure(self, mock_run):
        """Should return False when sync fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = Git.sync(Path("/test"))
        assert result is False

    @patch.object(Git, "run")
    def test_fetches_then_resets(self, mock_run):
        """Should fetch origin then reset to branch."""
        mock_run.return_value = MagicMock(returncode=0)
        cwd = Path("/test")
        Git.sync(cwd, branch="main")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(["fetch", "origin"], cwd=cwd)
        mock_run.assert_any_call(["reset", "--hard", "origin/main"], cwd=cwd)

    @patch.object(Git, "run")
    def test_uses_provided_branch(self, mock_run):
        """Should use the provided branch name."""
        mock_run.return_value = MagicMock(returncode=0)
        Git.sync(Path("/test"), branch="develop")

        reset_call = mock_run.call_args_list[1]
        assert reset_call[0][0] == ["reset", "--hard", "origin/develop"]
