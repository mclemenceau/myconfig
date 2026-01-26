"""Package manager abstraction for my-config."""

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

import click


class PackageManager(ABC):
    """Base class for package managers."""

    name: str

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this package manager is available on the system."""
        pass

    @classmethod
    @abstractmethod
    def install(cls, package: str, dry_run: bool = False) -> bool:
        """Install a package. Returns True on success."""
        pass

    @classmethod
    @abstractmethod
    def is_installed(cls, package: str) -> bool:
        """Check if a package is installed."""
        pass

    @classmethod
    @abstractmethod
    def uninstall(cls, package: str, dry_run: bool = False) -> bool:
        """Uninstall a package. Returns True on success."""
        pass


class AptManager(PackageManager):
    """APT package manager (Debian/Ubuntu)."""

    name = "apt"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("apt") is not None

    @classmethod
    def install(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["sudo", "apt", "install", "-y", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(
            ["dpkg", "-s", package],
            capture_output=True,
        )
        return result.returncode == 0

    @classmethod
    def uninstall(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["sudo", "apt", "remove", "-y", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class SnapManager(PackageManager):
    """Snap package manager."""

    name = "snap"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("snap") is not None

    @classmethod
    def install(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["sudo", "snap", "install", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(
            ["snap", "list", package],
            capture_output=True,
        )
        return result.returncode == 0

    @classmethod
    def uninstall(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["sudo", "snap", "remove", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class CargoManager(PackageManager):
    """Cargo package manager (Rust)."""

    name = "cargo"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("cargo") is not None

    @classmethod
    def install(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["cargo", "install", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def is_installed(cls, package: str) -> bool:
        # Check if binary exists in cargo bin
        cargo_home = subprocess.run(
            ["cargo", "--version"],
            capture_output=True,
            text=True,
        )
        if cargo_home.returncode != 0:
            return False

        # Simple check: see if the binary exists
        return shutil.which(package) is not None

    @classmethod
    def uninstall(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["cargo", "uninstall", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


# Registry of available package managers
MANAGERS: dict[str, type[PackageManager]] = {
    "apt": AptManager,
    "snap": SnapManager,
    "cargo": CargoManager,
}


def get_available_managers() -> list[str]:
    """Get list of available package managers on this system."""
    return [name for name, mgr in MANAGERS.items() if mgr.is_available()]


def install_apps(
    apps: dict[str, dict[str, Any]],
    preference: list[str],
    dry_run: bool = False,
) -> None:
    """Install applications using preferred package managers.

    Args:
        apps: Dict of app_name -> app_config (may include 'prefer' key)
        preference: Global preference order of package managers
        dry_run: If True, only show what would be done
    """
    available = get_available_managers()

    for app_name, app_config in apps.items():
        # Determine manager preference for this app
        app_prefer = app_config.get("prefer")
        if app_prefer and app_prefer in available:
            managers_to_try = [app_prefer]
        else:
            managers_to_try = [m for m in preference if m in available]

        if not managers_to_try:
            click.secho(f"  No package manager for: {app_name}", fg="red")
            continue

        # Try to install with first available manager
        installed = False
        for mgr_name in managers_to_try:
            mgr = MANAGERS[mgr_name]

            # Check if already installed
            if mgr.is_installed(app_name):
                click.echo(f"  {app_name}: already installed ({mgr_name})")
                installed = True
                break

            # Try to install
            click.echo(f"  {app_name}: installing via {mgr_name}...")
            if mgr.install(app_name, dry_run=dry_run):
                installed = True
                if not dry_run:
                    click.secho(f"  {app_name}: installed", fg="green")
                break
            else:
                click.secho(f"  {app_name}: failed via {mgr_name}", fg="yellow")

        if not installed and not dry_run:
            click.secho(f"  {app_name}: could not install", fg="red")
