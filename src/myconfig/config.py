"""Configuration management for my-config."""

from pathlib import Path
from typing import Any

import yaml

CONFIG_VERSION = 1
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "myconfig"
CONFIG_FILE = "config.yml"
FILES_DIR = "files"


def get_config_dir() -> Path:
    """Get the my-config configuration directory."""
    return DEFAULT_CONFIG_DIR


def get_config_path() -> Path:
    """Get the path to the main config.yml file."""
    return get_config_dir() / CONFIG_FILE


def get_files_dir() -> Path:
    """Get the path to the tracked files directory."""
    return get_config_dir() / FILES_DIR


def default_config() -> dict[str, Any]:
    """Return the default configuration structure."""
    return {
        "version": CONFIG_VERSION,
        "profiles": {
            "base": {
                "apps": {},
                "configs": [],
            },
        },
    }


def load_config() -> dict[str, Any]:
    """Load configuration from config.yml.

    Returns the config dict, or raises FileNotFoundError if not initialized.
    """
    config_path = get_config_path()
    if not config_path.exists():
        msg = f"Not found at {config_path}. Run 'my-config init' first."
        raise FileNotFoundError(msg)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if config is None:
        return default_config()

    return config


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to config.yml."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(
            config, f,
            default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def ensure_initialized() -> dict[str, Any]:
    """Ensure my-config is initialized, return config.

    Raises FileNotFoundError with helpful message if not initialized.
    """
    return load_config()


def path_to_relative(path: Path) -> str:
    """Convert an absolute path to a home-relative path string.

    Example: /home/user/.bashrc -> .bashrc
    """
    try:
        return str(path.relative_to(Path.home()))
    except ValueError:
        # Path is not under home directory, return as-is
        return str(path)


def relative_to_path(relative: str) -> Path:
    """Convert a home-relative path string to an absolute Path.

    Example: .bashrc -> /home/user/.bashrc
    """
    if relative.startswith("~"):
        return Path(relative).expanduser()
    # Assume relative to home
    return Path.home() / relative


def get_stored_file_path(relative: str) -> Path:
    """Get the path where a tracked file is stored.

    Example: .bashrc -> ~/.config/myconfig/files/.bashrc
    """
    return get_files_dir() / relative
