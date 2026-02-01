"""Tests for git module."""

from unittest.mock import MagicMock, patch

import pytest
from click import ClickException

from myconfig.git import (
    _run_git,
    ensure_gitignore,
    git_push,
    is_git_repo,
)


@patch("myconfig.git.get_config_dir")
def test_is_git_repo_true(mock_config_dir, tmp_path):
    """Test is_git_repo returns True when .git exists."""
    (tmp_path / ".git").mkdir()
    mock_config_dir.return_value = tmp_path
    assert is_git_repo() is True


@patch("myconfig.git.get_config_dir")
def test_is_git_repo_false(mock_config_dir, tmp_path):
    """Test is_git_repo returns False when .git missing."""
    mock_config_dir.return_value = tmp_path
    assert is_git_repo() is False


@patch("myconfig.git.get_config_dir")
def test_ensure_gitignore_creates_file(mock_config_dir, tmp_path):
    """Test .gitignore creation with correct patterns."""
    mock_config_dir.return_value = tmp_path
    ensure_gitignore()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "*.bak.*" in gitignore


@patch("myconfig.git.get_config_dir")
def test_ensure_gitignore_appends_missing(mock_config_dir, tmp_path):
    """Test .gitignore appends patterns that are missing."""
    mock_config_dir.return_value = tmp_path
    (tmp_path / ".gitignore").write_text("# my ignores\n")
    ensure_gitignore()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "# my ignores" in gitignore
    assert "*.bak.*" in gitignore


@patch("myconfig.git.get_config_dir")
def test_ensure_gitignore_noop_when_present(mock_config_dir, tmp_path):
    """Test .gitignore is not modified when patterns already present."""
    mock_config_dir.return_value = tmp_path
    (tmp_path / ".gitignore").write_text("*.bak.*\n")
    ensure_gitignore()
    gitignore = (tmp_path / ".gitignore").read_text()
    assert gitignore == "*.bak.*\n"


@patch("subprocess.run")
@patch("shutil.which", return_value="/usr/bin/git")
@patch("myconfig.git.get_config_dir")
def test_git_push_nothing_to_commit(mock_dir, mock_which, mock_run, tmp_path):
    """Test push when nothing to commit."""
    mock_dir.return_value = tmp_path
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git add .
        MagicMock(returncode=0),  # git diff --cached --quiet (nothing)
    ]
    git_push()


@patch("shutil.which", return_value=None)
def test_run_git_no_git_installed(mock_which):
    """Test error when git is not installed."""
    with pytest.raises(ClickException, match="git is not installed"):
        _run_git("status")
