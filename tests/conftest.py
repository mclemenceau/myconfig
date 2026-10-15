"""Shared fixtures for myconfig tests."""

import pytest
from click.testing import CliRunner

from myconfig.cli import main


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated $HOME so tests never touch the real configuration."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    return home


@pytest.fixture
def run(home):
    """Invoke the CLI and return the click Result."""
    runner = CliRunner()

    def _run(*args, **kwargs):
        return runner.invoke(main, list(args), **kwargs)

    return _run


@pytest.fixture
def initialized(run, home):
    """An initialized myconfig in the isolated $HOME."""
    result = run("init")
    assert result.exit_code == 0, result.output
    return home / ".config" / "myconfig"
