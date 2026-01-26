"""Package manager abstraction for my-config."""

import shutil
import subprocess
from abc import ABC, abstractmethod

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
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        """Install multiple packages at once.

        Returns (successful, failed) tuple of package lists.
        """
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
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        # Filter out already installed packages
        to_install = [p for p in packages if not cls.is_installed(p)]
        already_installed = [p for p in packages if cls.is_installed(p)]

        if not to_install:
            return packages, []

        cmd = ["sudo", "apt", "install", "-y"] + to_install
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return packages, []

        try:
            subprocess.run(cmd, check=True)
            return packages, []
        except subprocess.CalledProcessError:
            # Fall back to individual installation to identify failures
            successful = list(already_installed)
            failed = []
            for pkg in to_install:
                if cls.install(pkg, dry_run=False):
                    successful.append(pkg)
                else:
                    failed.append(pkg)
            return successful, failed

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
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        # Filter out already installed packages
        to_install = [p for p in packages if not cls.is_installed(p)]
        already_installed = [p for p in packages if cls.is_installed(p)]

        if not to_install:
            return packages, []

        # Snap can install multiple packages at once
        cmd = ["sudo", "snap", "install"] + to_install
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return packages, []

        try:
            subprocess.run(cmd, check=True)
            return packages, []
        except subprocess.CalledProcessError:
            # Fall back to individual installation to identify failures
            successful = list(already_installed)
            failed = []
            for pkg in to_install:
                if cls.install(pkg, dry_run=False):
                    successful.append(pkg)
                else:
                    failed.append(pkg)
            return successful, failed

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
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        # Cargo doesn't batch well, install sequentially
        successful = []
        failed = []
        for pkg in packages:
            if cls.is_installed(pkg):
                successful.append(pkg)
            elif cls.install(pkg, dry_run=dry_run):
                successful.append(pkg)
            else:
                failed.append(pkg)
        return successful, failed

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


class NpmManager(PackageManager):
    """NPM package manager (Node.js)."""

    name = "npm"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("npm") is not None

    @classmethod
    def install(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["npm", "install", "-g", package]
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        # Filter out already installed packages
        to_install = [p for p in packages if not cls.is_installed(p)]
        already_installed = [p for p in packages if cls.is_installed(p)]

        if not to_install:
            return packages, []

        # npm can install multiple packages at once
        cmd = ["npm", "install", "-g"] + to_install
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return packages, []

        try:
            subprocess.run(cmd, check=True)
            return packages, []
        except subprocess.CalledProcessError:
            # Fall back to individual installation to identify failures
            successful = list(already_installed)
            failed = []
            for pkg in to_install:
                if cls.install(pkg, dry_run=False):
                    successful.append(pkg)
                else:
                    failed.append(pkg)
            return successful, failed

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(
            ["npm", "list", "-g", package, "--depth=0"],
            capture_output=True,
        )
        return result.returncode == 0

    @classmethod
    def uninstall(cls, package: str, dry_run: bool = False) -> bool:
        cmd = ["npm", "uninstall", "-g", package]
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
    "npm": NpmManager,
}


def get_available_managers() -> list[str]:
    """Get list of available package managers on this system."""
    return [name for name, mgr in MANAGERS.items() if mgr.is_available()]


def install_apps(
    apps: dict[str, list[str]],
    dry_run: bool = False,
) -> None:
    """Install applications grouped by package manager.

    Args:
        apps: Dict of manager_name -> list of package names
        dry_run: If True, only show what would be done
    """
    available = get_available_managers()

    for manager_name, packages in apps.items():
        if not packages or not isinstance(packages, list):
            continue

        if manager_name not in available:
            click.secho(f"  Package manager not available: {manager_name}", fg="red")
            for pkg in packages:
                click.secho(f"    Skipping: {pkg}", fg="yellow")
            continue

        mgr = MANAGERS[manager_name]
        click.echo(f"  Installing via {manager_name}: {', '.join(packages)}")

        successful, failed = mgr.install_batch(packages, dry_run=dry_run)

        if not dry_run:
            for pkg in successful:
                click.secho(f"    {pkg}: installed", fg="green")
            for pkg in failed:
                click.secho(f"    {pkg}: failed", fg="red")
