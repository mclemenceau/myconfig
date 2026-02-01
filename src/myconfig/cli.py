"""Command-line interface for myconfig."""

import shutil
from pathlib import Path

import click

from . import __version__
from .config import (
    default_config,
    ensure_initialized,
    get_config_dir,
    get_config_path,
    get_files_dir,
    get_stored_file_path,
    path_to_relative,
    relative_to_path,
    save_config,
)
from .secrets import check_secrets


@click.group()
@click.version_option(version=__version__, prog_name="myconfig")
def main():
    """Portable configuration management tool.

    Quickly restore your environment on any machine by tracking your
    favorite apps and config files.
    """
    pass


@main.command()
def init():
    """Initialize myconfig in ~/.config/myconfig/."""
    config_dir = get_config_dir()
    config_path = get_config_path()
    files_dir = get_files_dir()

    if config_path.exists():
        click.echo(f"Already initialized at {config_dir}")
        return

    # Create directories
    config_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    # Create default config
    save_config(default_config())

    click.echo(f"Initialized myconfig at {config_dir}")
    click.echo(f"  Config file: {config_path}")
    click.echo(f"  Files directory: {files_dir}")


# --- Add command group ---


@main.group()
def add():
    """Add apps or config files to track."""
    pass


@add.command("config")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--profile", "-p", default="base", help="Profile to add to"
)
def add_config(path: str, profile: str):
    """Add a config file to track.

    PATH is the path to the config file (e.g., ~/.bashrc)
    """
    config = ensure_initialized()

    # Resolve and normalize path
    source = Path(path).expanduser().resolve()
    if source.is_dir():
        raise click.ClickException(f"Cannot track directories: {source}")

    relative = path_to_relative(source)

    # Check for secrets
    warnings = check_secrets(source, relative)
    for warning in warnings:
        click.secho(f"Warning: {warning}", fg="yellow", err=True)

    # Ensure profile exists
    if profile not in config["profiles"]:
        config["profiles"][profile] = {"apps": {}, "configs": []}

    # Check if already tracked
    if relative in config["profiles"][profile].get("configs", []):
        click.echo(f"Already tracking: {relative}")
        return

    # Copy file to storage
    stored_path = get_stored_file_path(relative)
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, stored_path)

    # Update config
    if "configs" not in config["profiles"][profile]:
        config["profiles"][profile]["configs"] = []
    config["profiles"][profile]["configs"].append(relative)
    save_config(config)

    click.echo(f"Added config: {relative} (profile: {profile})")


def get_app_name(item):
    """Extract app name from a list item (string or dict)."""
    if isinstance(item, str):
        return item
    elif isinstance(item, dict):
        return list(item.keys())[0]
    return None


def get_app_params(item):
    """Extract app params from a list item (string or dict)."""
    if isinstance(item, dict):
        return list(item.values())[0]
    return None


@add.command("app")
@click.argument("name")
@click.option("--profile", "-P", default="base", help="Profile to add to")
@click.option(
    "--manager", "-m",
    type=click.Choice(["apt", "snap", "cargo", "npm"]),
    default="apt",
    help="Package manager to use (default: apt)",
)
@click.option(
    "--params", "-p",
    default=None,
    help="Extra parameters for the package manager (e.g., '--classic' for snap)",
)
def add_app(name: str, profile: str, manager: str, params: str | None):
    """Add an application to track.

    NAME is the package name (e.g., helix, ripgrep, git)
    """
    config = ensure_initialized()

    # Ensure profile exists
    if profile not in config["profiles"]:
        config["profiles"][profile] = {"apps": {}, "configs": []}

    apps = config["profiles"][profile].get("apps", {})

    # Check if already tracked under any manager
    for mgr, pkg_list in apps.items():
        if isinstance(pkg_list, list):
            for item in pkg_list:
                if get_app_name(item) == name:
                    click.echo(f"Already tracking app: {name} (via {mgr})")
                    return

    # Add to the specified manager's list
    if "apps" not in config["profiles"][profile]:
        config["profiles"][profile]["apps"] = {}

    if manager not in config["profiles"][profile]["apps"]:
        config["profiles"][profile]["apps"][manager] = []

    # Store as dict if params provided, otherwise as string
    if params:
        config["profiles"][profile]["apps"][manager].append({name: params})
    else:
        config["profiles"][profile]["apps"][manager].append(name)
    save_config(config)

    msg = f"Added app: {name} (profile: {profile}, manager: {manager})"
    if params:
        msg += f" [params: {params}]"
    click.echo(msg)


# --- Remove command group ---


@main.group()
def remove():
    """Remove apps or config files from tracking."""
    pass


@remove.command("config")
@click.argument("path")
@click.option(
    "--profile", "-p", default="base", help="Profile to remove from"
)
@click.option("--keep-file", is_flag=True, help="Keep the stored file")
def remove_config(path: str, profile: str, keep_file: bool):
    """Remove a config file from tracking.

    PATH is the relative path (e.g., .bashrc) or full path
    """
    config = ensure_initialized()

    # Normalize path
    if path.startswith("/") or path.startswith("~"):
        source = Path(path).expanduser().resolve()
        relative = path_to_relative(source)
    else:
        relative = path

    # Check if profile exists
    if profile not in config["profiles"]:
        raise click.ClickException(f"Profile not found: {profile}")

    # Check if tracked
    if relative not in config["profiles"][profile].get("configs", []):
        msg = f"Config not tracked in profile '{profile}': {relative}"
        raise click.ClickException(msg)

    # Remove from config
    config["profiles"][profile]["configs"].remove(relative)
    save_config(config)

    # Remove stored file unless --keep-file
    if not keep_file:
        stored_path = get_stored_file_path(relative)
        if stored_path.exists():
            stored_path.unlink()
            # Clean up empty parent directories
            try:
                stored_path.parent.rmdir()
            except OSError:
                pass  # Directory not empty, that's fine

    click.echo(f"Removed config: {relative} (profile: {profile})")


@remove.command("app")
@click.argument("name")
@click.option(
    "--profile", "-P", default="base", help="Profile to remove from"
)
def remove_app(name: str, profile: str):
    """Remove an application from tracking.

    NAME is the package name (e.g., helix, ripgrep, git)
    """
    config = ensure_initialized()

    # Check if profile exists
    if profile not in config["profiles"]:
        raise click.ClickException(f"Profile not found: {profile}")

    apps = config["profiles"][profile].get("apps", {})

    # Find which manager has this app
    found_manager = None
    found_item = None
    for mgr, pkg_list in apps.items():
        if isinstance(pkg_list, list):
            for item in pkg_list:
                if get_app_name(item) == name:
                    found_manager = mgr
                    found_item = item
                    break
        if found_manager:
            break

    if not found_manager:
        msg = f"App not tracked in profile '{profile}': {name}"
        raise click.ClickException(msg)

    # Remove from config
    apps[found_manager].remove(found_item)

    # Clean up empty lists
    if not apps[found_manager]:
        del apps[found_manager]

    save_config(config)

    click.echo(f"Removed app: {name} (profile: {profile})")


# --- List command ---


@main.command("list")
@click.option("--profile", "-p", help="Show only this profile")
def list_items(profile: str | None):
    """List tracked apps and config files."""
    config = ensure_initialized()

    profiles_to_show = [profile] if profile else list(config["profiles"].keys())

    for prof_name in profiles_to_show:
        if prof_name not in config["profiles"]:
            click.secho(f"Profile not found: {prof_name}", fg="red", err=True)
            continue

        prof = config["profiles"][prof_name]
        extends = prof.get("extends", "")

        click.secho(f"\n[{prof_name}]", fg="cyan", bold=True)
        if extends:
            click.echo(f"  extends: {extends}")

        # Apps (grouped by manager)
        apps = prof.get("apps", {})
        if apps:
            click.echo("  Apps:")
            for mgr, pkg_list in apps.items():
                if isinstance(pkg_list, list) and pkg_list:
                    # Format each app, showing params if present
                    formatted = []
                    for item in pkg_list:
                        app_name = get_app_name(item)
                        app_params = get_app_params(item)
                        if app_params:
                            formatted.append(f"{app_name} [{app_params}]")
                        else:
                            formatted.append(app_name)
                    click.echo(f"    {mgr}: {', '.join(formatted)}")
        else:
            click.echo("  Apps: (none)")

        # Configs
        configs = prof.get("configs", [])
        if configs:
            click.echo("  Configs:")
            for cfg in configs:
                stored = get_stored_file_path(cfg)
                exists = "+" if stored.exists() else "-"
                click.echo(f"    [{exists}] {cfg}")
        else:
            click.echo("  Configs: (none)")


# --- Status command ---


@main.command()
def status():
    """Show status of tracked files (changed, missing, etc.)."""
    config = ensure_initialized()
    get_files_dir()

    click.echo("Checking tracked files...\n")

    has_changes = False

    for prof_name, prof in config["profiles"].items():
        changes = []

        for cfg in prof.get("configs", []):
            stored = get_stored_file_path(cfg)
            actual = relative_to_path(cfg)

            if not stored.exists():
                changes.append((cfg, "not stored", "yellow"))
            elif not actual.exists():
                changes.append((cfg, "missing on system", "red"))
            else:
                # Compare contents
                stored_content = stored.read_bytes()
                actual_content = actual.read_bytes()
                if stored_content != actual_content:
                    changes.append((cfg, "modified", "yellow"))

        if changes:
            has_changes = True
            click.secho(f"[{prof_name}]", fg="cyan", bold=True)
            for cfg, status, color in changes:
                click.secho(f"  {cfg}: {status}", fg=color)

    if not has_changes:
        click.secho("All tracked files are in sync.", fg="green")


# --- Sync command ---


@main.command()
@click.option("--profile", "-p", help="Sync only this profile")
@click.option("--dry-run", is_flag=True, help="Show what would be synced")
def sync(profile: str | None, dry_run: bool):
    """Sync modified system files back to storage.

    Updates stored copies with current versions from the system.
    """
    config = ensure_initialized()

    if dry_run:
        click.secho("(dry-run mode - no changes will be made)", fg="yellow")

    profiles_to_sync = [profile] if profile else list(config["profiles"].keys())
    synced_count = 0

    for prof_name in profiles_to_sync:
        if prof_name not in config["profiles"]:
            click.secho(f"Profile not found: {prof_name}", fg="red", err=True)
            continue

        prof = config["profiles"][prof_name]

        for cfg in prof.get("configs", []):
            stored = get_stored_file_path(cfg)
            actual = relative_to_path(cfg)

            if not actual.exists():
                continue  # Can't sync a file that doesn't exist on system

            if not stored.exists():
                # File not yet stored, copy it
                if dry_run:
                    click.echo(f"  Would store: {cfg}")
                else:
                    stored.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(actual, stored)
                    click.echo(f"  Stored: {cfg}")
                synced_count += 1
            else:
                # Compare and sync if different
                stored_content = stored.read_bytes()
                actual_content = actual.read_bytes()
                if stored_content != actual_content:
                    if dry_run:
                        click.echo(f"  Would sync: {cfg}")
                    else:
                        shutil.copy2(actual, stored)
                        click.echo(f"  Synced: {cfg}")
                    synced_count += 1

    if synced_count == 0:
        click.secho("All tracked files are already in sync.", fg="green")
    elif not dry_run:
        click.secho(f"\nSynced {synced_count} file(s).", fg="green")


# --- Placeholder commands for features to be implemented ---


@main.command()
@click.option("--profile", "-p", default="base", help="Profile to apply")
@click.option("--dry-run", is_flag=True, help="Show what would change")
def apply(profile: str, dry_run: bool):
    """Apply configuration to the local system."""
    from .files import apply_configs
    from .packages import install_apps
    from .profiles import resolve_profile

    config = ensure_initialized()

    if profile not in config["profiles"]:
        raise click.ClickException(f"Profile not found: {profile}")

    # Resolve profile with inheritance
    resolved = resolve_profile(config, profile)

    click.echo(f"Applying profile: {profile}")
    if dry_run:
        click.secho("(dry-run mode - no changes will be made)", fg="yellow")

    # Install apps
    apps = resolved.get("apps", {})
    if apps:
        total = sum(len(pkgs) for pkgs in apps.values() if isinstance(pkgs, list))
        click.echo(f"\nInstalling {total} app(s)...")
        install_apps(apps, dry_run=dry_run)

    # Apply configs
    configs = resolved.get("configs", [])
    if configs:
        click.echo(f"\nApplying {len(configs)} config file(s)...")
        apply_configs(configs, dry_run=dry_run)

    if not dry_run:
        click.secho("\nDone!", fg="green")


@main.command("export")
@click.argument("destination", type=click.Path())
@click.option(
    "--password", "-p", prompt=True, hide_input=True,
    confirmation_prompt=True, help="Password for encryption"
)
def export_config(destination: str, password: str):
    """Export configuration to an encrypted archive."""
    from .export import create_archive

    ensure_initialized()
    dest_path = Path(destination).expanduser().resolve()

    click.echo(f"Exporting to {dest_path}...")
    archive_path = create_archive(dest_path, password)
    click.secho(f"Created: {archive_path}", fg="green")


@main.command("import")
@click.argument("archive", type=click.Path(exists=True))
@click.option("--password", "-p", prompt=True, hide_input=True,
              help="Password for decryption")
def import_config(archive: str, password: str):
    """Import configuration from an encrypted archive."""
    from .export import extract_archive

    archive_path = Path(archive).expanduser().resolve()

    click.echo(f"Importing from {archive_path}...")
    extract_archive(archive_path, password)
    click.secho("Import complete!", fg="green")


if __name__ == "__main__":
    main()
