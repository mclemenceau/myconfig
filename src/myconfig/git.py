"""Git operations for myconfig."""

import shutil
import subprocess
from datetime import date
from pathlib import Path

import click

from .config import get_config_dir


def _run_git(
    *args: str, cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run a git command in the config directory.

    Returns CompletedProcess result.
    Raises click.ClickException if git is not installed.
    """
    if shutil.which("git") is None:
        raise click.ClickException("git is not installed.")

    if cwd is None:
        cwd = get_config_dir()

    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def is_git_repo() -> bool:
    """Check if the config directory is a git repository."""
    return (get_config_dir() / ".git").exists()


def git_clone(url: str, dest: Path) -> None:
    """Clone a remote repository to dest."""
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"git clone failed: {result.stderr.strip()}"
        )


def git_init_and_add_remote(url: str) -> None:
    """Initialize git repo and add remote origin."""
    result = _run_git("init")
    if result.returncode != 0:
        raise click.ClickException(
            f"git init failed: {result.stderr.strip()}"
        )

    result = _run_git("remote", "add", "origin", url)
    if result.returncode != 0:
        raise click.ClickException(
            f"git remote add failed: {result.stderr.strip()}"
        )

    result = _run_git("fetch", "origin")
    if result.returncode != 0:
        raise click.ClickException(
            f"git fetch failed: {result.stderr.strip()}"
        )

    # Try to checkout the remote default branch
    branch = _detect_default_branch()
    result = _run_git("checkout", "-t", f"origin/{branch}")
    if result.returncode != 0:
        # Remote might be empty, just create the branch locally
        _run_git("checkout", "-b", branch)


def _detect_default_branch() -> str:
    """Detect the default branch name from origin."""
    result = _run_git("remote", "show", "origin")
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "HEAD branch:" in line:
                return line.split(":")[-1].strip()
    return "main"


def git_push() -> None:
    """Stage all changes, commit, and push."""
    result = _run_git("add", ".")
    if result.returncode != 0:
        raise click.ClickException(
            f"git add failed: {result.stderr.strip()}"
        )

    # Check if there is anything to commit
    result = _run_git("diff", "--cached", "--quiet")
    if result.returncode == 0:
        click.echo("Nothing to commit, working tree clean.")
        return

    today = date.today().isoformat()
    result = _run_git("commit", "-m", f"myconfig: sync {today}")
    if result.returncode != 0:
        raise click.ClickException(
            f"git commit failed: {result.stderr.strip()}"
        )

    result = _run_git("push")
    if result.returncode != 0:
        # First push may need --set-upstream
        result = _run_git("push", "--set-upstream", "origin", "HEAD")
        if result.returncode != 0:
            raise click.ClickException(
                f"git push failed: {result.stderr.strip()}"
            )

    click.secho("Pushed to remote.", fg="green")


def git_pull() -> None:
    """Pull latest from remote."""
    result = _run_git("pull")
    if result.returncode != 0:
        raise click.ClickException(
            f"git pull failed: {result.stderr.strip()}"
        )
    click.secho("Pulled latest changes.", fg="green")


def ensure_gitignore() -> None:
    """Create or update .gitignore in the config directory."""
    config_dir = get_config_dir()
    gitignore_path = config_dir / ".gitignore"

    patterns = ["*.bak.*"]

    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        to_add = [p for p in patterns if p not in existing]
        if to_add:
            with open(gitignore_path, "a") as f:
                f.write("\n" + "\n".join(to_add) + "\n")
    else:
        gitignore_path.write_text("\n".join(patterns) + "\n")
