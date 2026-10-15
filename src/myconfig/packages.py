"""Package manager abstraction for myconfig."""

import shutil
import subprocess

import click

from .config import get_app_name, get_app_params


class PackageManager:
    """Base class for package managers.

    Subclasses set the install command and override is_installed().
    """

    name: str
    install_cmd: list[str]
    # Whether several packages can be installed in a single command
    batch: bool = True

    @classmethod
    def is_available(cls) -> bool:
        """Check if this package manager is available on the system."""
        return shutil.which(cls.name) is not None

    @classmethod
    def is_installed(cls, package: str) -> bool:
        """Check if a package is installed."""
        raise NotImplementedError

    @classmethod
    def _run(cls, cmd: list[str], dry_run: bool) -> bool:
        if dry_run:
            click.echo(f"    Would run: {' '.join(cmd)}")
            return True
        return subprocess.run(cmd).returncode == 0

    @classmethod
    def install(
        cls, package: str, params: str | None = None, dry_run: bool = False
    ) -> bool:
        """Install a package. Returns True on success."""
        cmd = list(cls.install_cmd)
        if params:
            cmd.extend(params.split())
        cmd.append(package)
        return cls._run(cmd, dry_run)

    @classmethod
    def install_batch(
        cls, packages: list[str], dry_run: bool = False
    ) -> tuple[list[str], list[str]]:
        """Install the packages that are not already installed.

        Returns (successful, failed) tuple of package lists.
        """
        successful = []
        to_install = []
        for pkg in packages:
            if cls.is_installed(pkg):
                successful.append(pkg)
            else:
                to_install.append(pkg)

        if not to_install:
            return successful, []

        if cls.batch and cls._run(cls.install_cmd + to_install, dry_run):
            return successful + to_install, []

        # Install one by one, which also identifies batch failures
        failed = []
        for pkg in to_install:
            if cls.install(pkg, dry_run=dry_run):
                successful.append(pkg)
            else:
                failed.append(pkg)
        return successful, failed


class AptManager(PackageManager):
    """APT package manager (Debian/Ubuntu)."""

    name = "apt"
    install_cmd = ["sudo", "apt", "install", "-y"]

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() == "install ok installed"


class SnapManager(PackageManager):
    """Snap package manager."""

    name = "snap"
    install_cmd = ["sudo", "snap", "install"]

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(["snap", "list", package], capture_output=True)
        return result.returncode == 0


class CargoManager(PackageManager):
    """Cargo package manager (Rust)."""

    name = "cargo"
    install_cmd = ["cargo", "install"]
    # One failing crate would abort the whole batch after a long build
    batch = False

    @classmethod
    def is_installed(cls, package: str) -> bool:
        # Crates are listed unindented as "<name> v<version>:"
        result = subprocess.run(
            ["cargo", "install", "--list"], capture_output=True, text=True
        )
        if result.returncode != 0:
            return False
        return any(
            line.split(" ", 1)[0] == package
            for line in result.stdout.splitlines()
            if line and not line[0].isspace()
        )


class NpmManager(PackageManager):
    """NPM package manager (Node.js)."""

    name = "npm"
    install_cmd = ["npm", "install", "-g"]

    @classmethod
    def is_installed(cls, package: str) -> bool:
        result = subprocess.run(
            ["npm", "list", "-g", package, "--depth=0"],
            capture_output=True,
        )
        return result.returncode == 0


# Registry of supported package managers
MANAGERS: dict[str, type[PackageManager]] = {
    m.name: m for m in (AptManager, SnapManager, CargoManager, NpmManager)
}


def install_apps(
    apps: dict[str, list],
    dry_run: bool = False,
) -> None:
    """Install applications grouped by package manager.

    Args:
        apps: Dict of manager name -> list of items (str or {name: params})
        dry_run: If True, only show what would be done
    """
    for manager_name, packages in apps.items():
        if not packages or not isinstance(packages, list):
            continue

        mgr = MANAGERS.get(manager_name)
        if mgr is None or not mgr.is_available():
            click.secho(
                f"  Package manager not available: {manager_name}", fg="red"
            )
            for pkg in packages:
                click.secho(f"    Skipping: {get_app_name(pkg)}", fg="yellow")
            continue

        # Separate packages with params from simple ones
        simple_pkgs = []
        parameterized_pkgs = []
        for item in packages:
            name = get_app_name(item)
            params = get_app_params(item)
            if params:
                parameterized_pkgs.append((name, params))
            else:
                simple_pkgs.append(name)

        # Batch install simple packages
        if simple_pkgs:
            click.echo(
                f"  Installing via {manager_name}: {', '.join(simple_pkgs)}"
            )
            successful, failed = mgr.install_batch(simple_pkgs, dry_run)
            if not dry_run:
                for pkg in successful:
                    click.secho(f"    {pkg}: installed", fg="green")
                for pkg in failed:
                    click.secho(f"    {pkg}: failed", fg="red")

        # Install parameterized packages individually
        for name, params in parameterized_pkgs:
            click.echo(f"  Installing via {manager_name}: {name} {params}")
            if mgr.is_installed(name):
                click.secho(f"    {name}: already installed", fg="green")
            elif mgr.install(name, params=params, dry_run=dry_run):
                if not dry_run:
                    click.secho(f"    {name}: installed", fg="green")
            else:
                click.secho(f"    {name}: failed", fg="red")
