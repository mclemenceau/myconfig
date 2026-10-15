"""Configuration management for myconfig."""

from pathlib import Path, PurePosixPath
from typing import Any

import click
import yaml

CONFIG_VERSION = 1
CONFIG_FILE = "config.yml"
FILES_DIR = "files"


def get_config_dir() -> Path:
    """Get the myconfig configuration directory."""
    return Path.home() / ".config" / "myconfig"


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

    Raises click.ClickException if not initialized or malformed.
    """
    config_path = get_config_path()
    if not config_path.exists():
        msg = f"Not found at {config_path}. Run 'myconfig init' first."
        raise click.ClickException(msg)

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise click.ClickException(f"Invalid {config_path}: {e}") from e

    if config is None:
        return default_config()

    if not isinstance(config, dict) or not isinstance(
        config.get("profiles"), dict
    ):
        msg = f"Invalid {config_path}: missing 'profiles' mapping"
        raise click.ClickException(msg)

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
    """Ensure myconfig is initialized, return config.

    Raises click.ClickException with helpful message if not initialized.
    """
    return load_config()


def validate_relative(relative: str) -> str:
    """Check that a tracked path stays inside $HOME and the store.

    Tracked paths come from config.yml, which may be hand-edited or
    pulled from a remote, so never trust them blindly.
    """
    parts = PurePosixPath(relative).parts
    if not parts or parts[0] == "/" or ".." in parts:
        raise click.ClickException(
            f"Invalid tracked path (must be relative to $HOME): {relative}"
        )
    return relative


def path_to_relative(path: Path) -> str:
    """Convert an absolute path to a home-relative path string.

    Example: /home/user/.bashrc -> .bashrc
    Raises click.ClickException if the path is not under $HOME.
    """
    try:
        relative = path.relative_to(Path.home())
    except ValueError:
        raise click.ClickException(
            f"Only files under $HOME can be tracked: {path}"
        ) from None
    return validate_relative(str(relative))


def relative_to_path(relative: str) -> Path:
    """Convert a home-relative path string to an absolute Path.

    Example: .bashrc -> /home/user/.bashrc
    """
    if relative.startswith("~/"):
        relative = relative[2:]
    return Path.home() / validate_relative(relative)


def get_stored_file_path(relative: str) -> Path:
    """Get the path where a tracked file is stored.

    Example: .bashrc -> ~/.config/myconfig/files/.bashrc
    """
    if relative.startswith("~/"):
        relative = relative[2:]
    return get_files_dir() / validate_relative(relative)


def get_app_name(item: str | dict[str, str]) -> str:
    """Extract app name from an apps list item (string or {name: params})."""
    if isinstance(item, dict):
        return next(iter(item))
    return item


def get_app_params(item: str | dict[str, str]) -> str | None:
    """Extract app params from an apps list item (string or dict)."""
    if isinstance(item, dict):
        return next(iter(item.values()))
    return None
