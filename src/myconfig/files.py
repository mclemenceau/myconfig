"""File operations for myconfig."""

import shutil
from datetime import datetime
from pathlib import Path

import click

from .config import get_stored_file_path, relative_to_path


def backup_file(path: Path) -> Path | None:
    """Create a backup of a file with timestamp.

    Returns the backup path, or None if file doesn't exist.
    """
    if not path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f"{path.suffix}.bak.{timestamp}")

    shutil.copy2(path, backup_path)
    return backup_path


def apply_configs(configs: list[str], dry_run: bool = False) -> None:
    """Apply tracked config files to the system.

    Args:
        configs: List of relative paths to apply
        dry_run: If True, only show what would be done
    """
    for relative in configs:
        stored = get_stored_file_path(relative)
        target = relative_to_path(relative)

        if not stored.exists():
            click.secho(f"  Skipping {relative}: not in storage", fg="yellow")
            continue

        if dry_run:
            if target.exists():
                click.echo(f"  Would backup and replace: {relative}")
            else:
                click.echo(f"  Would create: {relative}")
            continue

        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        # Check if files are identical
        if target.exists() and stored.read_bytes() == target.read_bytes():
            click.echo(f"  Unchanged: {relative}")
            continue

        # Backup existing file (only if different)
        mode = None
        if target.exists():
            mode = target.stat().st_mode
            backup = backup_file(target)
            if backup:
                click.echo(f"  Backed up: {target} -> {backup.name}")

        # Copy from storage, keeping the permissions of an existing file
        # since git does not preserve them (e.g. 0600 on ~/.netrc)
        shutil.copy2(stored, target)
        if mode is not None:
            target.chmod(mode)
        click.secho(f"  Applied: {relative}", fg="green")

