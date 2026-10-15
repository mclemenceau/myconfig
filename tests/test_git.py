"""Tests for git module."""

import subprocess
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


@patch("subprocess.run")
@patch("shutil.which", return_value="/usr/bin/git")
@patch("myconfig.git.get_config_dir")
def test_git_push_with_message(mock_dir, mock_which, mock_run, tmp_path):
    """Test push includes custom message in commit."""
    mock_dir.return_value = tmp_path
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git add .
        MagicMock(returncode=1),  # git diff --cached --quiet (has changes)
        MagicMock(returncode=0),  # git commit
        MagicMock(returncode=0),  # git push
    ]
    git_push(message="Updated vim config")
    commit_call = mock_run.call_args_list[2]
    commit_msg = commit_call[0][0][3]  # ["git", "commit", "-m", <msg>]
    assert "Updated vim config" in commit_msg
    assert "myconfig: sync" in commit_msg


@patch("shutil.which", return_value=None)
def test_run_git_no_git_installed(mock_which):
    """Test error when git is not installed."""
    with pytest.raises(ClickException, match="git is not installed"):
        _run_git("status")


@pytest.fixture
def remote(tmp_path):
    """A bare git remote containing a myconfig configuration."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "config.yml").write_text(
        "version: 1\nprofiles:\n  base:\n    configs: [.remote]\n"
    )
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "."],
        ["commit", "-qm", "init"],
    ):
        subprocess.run(["git", *args], cwd=src, check=True)
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(src), str(bare)], check=True
    )
    return bare


def test_init_git_unreachable_keeps_config(run, initialized, tmp_path):
    before = (initialized / "config.yml").read_text()

    result = run("init", "--git", str(tmp_path / "missing.git"))
    assert result.exit_code == 1
    assert "Cannot access remote" in result.output
    assert (initialized / "config.yml").read_text() == before
    assert list(initialized.parent.iterdir()) == [initialized]


def test_init_git_clones_and_backs_up(run, initialized, remote):
    result = run("init", "--git", str(remote))
    assert result.exit_code == 0, result.output

    assert ".remote" in (initialized / "config.yml").read_text()
    assert is_git_repo()
    backups = list(initialized.parent.glob("myconfig.bak.*"))
    assert len(backups) == 1
    assert (backups[0] / "config.yml").exists()


def test_init_git_empty_remote_pushes(run, home, tmp_path):
    bare = tmp_path / "empty.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)

    result = run("init", "--git", str(bare))
    assert result.exit_code == 0, result.output

    log = subprocess.run(
        ["git", "log", "--oneline", "main"],
        cwd=bare, capture_output=True, text=True, check=True,
    )
    assert "myconfig: sync" in log.stdout


def test_git_push_and_pull_between_machines(run, home, tmp_path, remote):
    assert run("init", "--git", str(remote)).exit_code == 0
    (home / ".vimrc").write_text("set nu\n")
    assert run("add", "config", str(home / ".vimrc")).exit_code == 0
    result = run("git", "push", "-m", "add vimrc")
    assert result.exit_code == 0, result.output

    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)],
                   check=True)
    assert (other / "files" / ".vimrc").read_text() == "set nu\n"

    (other / "files" / ".vimrc").write_text("set nonu\n")
    for args in (["commit", "-qam", "change"], ["push", "-q"]):
        subprocess.run(["git", *args], cwd=other, check=True)

    result = run("git", "pull")
    assert result.exit_code == 0, result.output
    stored = home / ".config" / "myconfig" / "files" / ".vimrc"
    assert stored.read_text() == "set nonu\n"


def test_git_commands_require_repo(run, initialized):
    result = run("git", "push")
    assert result.exit_code == 1
    assert "Not a git repo" in result.output
