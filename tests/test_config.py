"""Tests for config module."""

from pathlib import Path

from myconfig.config import (
    default_config,
    path_to_relative,
    relative_to_path,
)


def test_default_config_structure():
    """Test that default config has required keys."""
    config = default_config()

    assert "version" in config
    assert config["version"] == 1
    assert "package_managers" in config
    assert "preference" in config["package_managers"]
    assert "profiles" in config
    assert "base" in config["profiles"]


def test_path_to_relative():
    """Test converting absolute paths to relative."""
    home = Path.home()

    # Path under home
    result = path_to_relative(home / ".bashrc")
    assert result == ".bashrc"

    result = path_to_relative(home / ".config" / "helix" / "config.toml")
    assert result == ".config/helix/config.toml"


def test_relative_to_path():
    """Test converting relative paths to absolute."""
    home = Path.home()

    result = relative_to_path(".bashrc")
    assert result == home / ".bashrc"

    result = relative_to_path("~/.bashrc")
    assert result == home / ".bashrc"
