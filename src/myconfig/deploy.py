"""Remote deployment via SSH for my-config."""

import os
import subprocess
import tempfile
from pathlib import Path

import click

from .config import load_config
from .export import create_archive
from .profiles import resolve_profile


def parse_target(target: str) -> tuple[str, str, int]:
    """Parse user@host:port target string.

    Returns (user, host, port) tuple.
    """
    port = 22

    # Handle port
    if ":" in target and "@" in target:
        # user@host:port format
        user_host, port_str = target.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            # Not a port, might be IPv6 or something else
            user_host = target
    else:
        user_host = target

    # Handle user
    if "@" in user_host:
        user, host = user_host.split("@", 1)
    else:
        user = os.environ.get("USER", "root")
        host = user_host

    return user, host, port


def ssh_exec(
    user: str,
    host: str,
    port: int,
    command: str,
    key_path: str | None = None,
    check: bool = True,
    interactive: bool = False,
) -> subprocess.CompletedProcess:
    """Execute a command on a remote host via SSH.

    Uses the system's ssh command, which respects SSH config,
    ControlMaster multiplexing, and hardware security keys.

    Args:
        interactive: If True, allocate a TTY and pass through stdin/stdout
                     for commands that need user interaction (e.g., sudo).
    """
    ssh_cmd = ["ssh", "-p", str(port)]

    if interactive:
        # Force pseudo-TTY allocation for interactive commands
        ssh_cmd.append("-tt")

    if key_path:
        ssh_cmd.extend(["-i", key_path])

    ssh_cmd.append(f"{user}@{host}")
    ssh_cmd.append(command)

    if interactive:
        # For interactive commands, don't capture output - let user interact
        return subprocess.run(
            ssh_cmd,
            check=check,
        )
    else:
        return subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            check=check,
        )


def scp_upload(
    local_path: Path,
    user: str,
    host: str,
    port: int,
    remote_path: str,
    key_path: str | None = None,
) -> subprocess.CompletedProcess:
    """Upload a file to a remote host via SCP.

    Uses the system's scp command for compatibility with SSH config.
    """
    scp_cmd = ["scp", "-P", str(port)]

    if key_path:
        scp_cmd.extend(["-i", key_path])

    scp_cmd.append(str(local_path))
    scp_cmd.append(f"{user}@{host}:{remote_path}")

    return subprocess.run(
        scp_cmd,
        capture_output=True,
        text=True,
        check=True,
    )


def remote_deploy(
    target: str,
    profile: str,
    key_path: str | None = None,
) -> None:
    """Deploy configuration to a remote host.

    Uses the system's ssh/scp commands for full compatibility with SSH config,
    ControlMaster multiplexing, and hardware security keys (like YubiKey).

    Args:
        target: user@host or user@host:port
        profile: Profile name to deploy
        key_path: Optional path to SSH private key
    """
    user, host, port = parse_target(target)
    click.echo(f"Connecting to {user}@{host}:{port}...")

    # Test SSH connection
    try:
        result = ssh_exec(user, host, port, "echo connected", key_path)
        if result.returncode != 0:
            raise click.ClickException(
                f"SSH connection failed: {result.stderr}"
            )
        click.secho("  Connected!", fg="green")
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"SSH connection failed: {e.stderr}") from e

    # Load and resolve profile
    config = load_config()
    resolved = resolve_profile(config, profile)

    # Create temporary encrypted archive
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Generate a random password for transfer
        import secrets
        transfer_password = secrets.token_urlsafe(32)

        # Create archive
        click.echo("  Creating archive...")
        archive_path = create_archive(tmp_path, transfer_password)

        # Upload archive
        click.echo("  Uploading archive...")
        remote_archive = f"/tmp/myconfig_deploy_{os.getpid()}.tar.gz.enc"
        try:
            scp_upload(archive_path, user, host, port, remote_archive, key_path)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Upload failed: {e.stderr}") from e

        # Extract on remote
        click.echo("  Extracting on remote...")
        remote_tar = remote_archive.replace(".enc", "")
        commands = [
            # Decrypt
            f"openssl enc -aes-256-cbc -d -pbkdf2 -in {remote_archive} "
            f"-out {remote_tar} -pass pass:{transfer_password}",
            # Create config dir
            "mkdir -p ~/.config/myconfig/files",
            # Extract
            f"tar -xzf {remote_tar} -C ~/.config/myconfig/",
            # Cleanup
            f"rm -f {remote_archive} {remote_tar}",
        ]

        for cmd in commands:
            result = ssh_exec(user, host, port, cmd, key_path, check=False)
            if result.returncode != 0:
                click.secho(f"  Warning: {result.stderr}", fg="yellow")

    # Install packages (grouped by manager)
    apps = resolved.get("apps", {})
    if apps:
        total = sum(len(pkgs) for pkgs in apps.values() if isinstance(pkgs, list))
        click.echo(f"  Installing {total} app(s)...")

        # Check if passwordless sudo is available
        sudo_check = ssh_exec(
            user, host, port, "sudo -n true 2>/dev/null", key_path, check=False
        )
        needs_sudo_password = sudo_check.returncode != 0

        if needs_sudo_password:
            click.secho(
                "  Note: sudo requires password - "
                "you will be prompted interactively",
                fg="yellow",
            )
            click.echo(
                "  (Tip: configure passwordless sudo "
                "for non-interactive deploys)"
            )

        def get_app_name(item):
            if isinstance(item, str):
                return item
            elif isinstance(item, dict):
                return list(item.keys())[0]
            return None

        def get_app_params(item):
            if isinstance(item, dict):
                return list(item.values())[0]
            return None

        for manager, packages in apps.items():
            if not packages or not isinstance(packages, list):
                continue

            # Separate simple packages from parameterized ones
            simple_pkgs = []
            param_pkgs = []
            for item in packages:
                name = get_app_name(item)
                params = get_app_params(item)
                if params:
                    param_pkgs.append((name, params))
                else:
                    simple_pkgs.append(name)

            # Batch install simple packages
            if simple_pkgs:
                click.echo(f"    Installing via {manager}: {', '.join(simple_pkgs)}")

                if manager == "apt":
                    cmd = f"sudo apt install -y {' '.join(simple_pkgs)}"
                    needs_tty = needs_sudo_password
                elif manager == "snap":
                    cmd = f"sudo snap install {' '.join(simple_pkgs)}"
                    needs_tty = needs_sudo_password
                elif manager == "cargo":
                    # Cargo doesn't batch well, install sequentially
                    for pkg in simple_pkgs:
                        cargo_cmd = f"cargo install {pkg}"
                        result = ssh_exec(
                            user, host, port, cargo_cmd, key_path, check=False
                        )
                        if result.returncode == 0:
                            click.secho(f"      {pkg}: installed", fg="green")
                        else:
                            click.secho(f"      {pkg}: failed", fg="red")
                    cmd = None
                elif manager == "npm":
                    cmd = f"npm install -g {' '.join(simple_pkgs)}"
                    needs_tty = False
                else:
                    click.secho(f"    Unknown manager: {manager}", fg="yellow")
                    cmd = None

                if cmd:
                    result = ssh_exec(
                        user, host, port, cmd, key_path,
                        check=False, interactive=needs_tty
                    )
                    if result.returncode == 0:
                        for pkg in simple_pkgs:
                            click.secho(f"      {pkg}: installed", fg="green")
                    else:
                        click.secho("      Batch failed, trying individually...", fg="yellow")
                        for pkg in simple_pkgs:
                            if manager == "apt":
                                single_cmd = f"sudo apt install -y {pkg}"
                            elif manager == "snap":
                                single_cmd = f"sudo snap install {pkg}"
                            elif manager == "npm":
                                single_cmd = f"npm install -g {pkg}"
                            else:
                                continue
                            single_result = ssh_exec(
                                user, host, port, single_cmd, key_path,
                                check=False, interactive=needs_tty
                            )
                            if single_result.returncode == 0:
                                click.secho(f"      {pkg}: installed", fg="green")
                            else:
                                click.secho(f"      {pkg}: failed", fg="red")

            # Install parameterized packages individually
            for name, params in param_pkgs:
                click.echo(f"    Installing via {manager}: {name} {params}")
                if manager == "apt":
                    cmd = f"sudo apt install -y {params} {name}"
                    needs_tty = needs_sudo_password
                elif manager == "snap":
                    cmd = f"sudo snap install {params} {name}"
                    needs_tty = needs_sudo_password
                elif manager == "cargo":
                    cmd = f"cargo install {params} {name}"
                    needs_tty = False
                elif manager == "npm":
                    cmd = f"npm install -g {params} {name}"
                    needs_tty = False
                else:
                    click.secho(f"    Unknown manager: {manager}", fg="yellow")
                    continue

                result = ssh_exec(
                    user, host, port, cmd, key_path,
                    check=False, interactive=needs_tty
                )
                if result.returncode == 0:
                    click.secho(f"      {name}: installed", fg="green")
                else:
                    click.secho(f"      {name}: failed", fg="red")

    # Apply config files
    configs = resolved.get("configs", [])
    if configs:
        click.echo(f"  Applying {len(configs)} config file(s)...")

        for cfg in configs:
            # Source is in ~/.config/myconfig/files/
            source = f"~/.config/myconfig/files/{cfg}"
            # Target is in home directory
            cfg_target = f"~/{cfg}"

            # Check if files are identical (skip backup if unchanged)
            diff_check = ssh_exec(
                user, host, port,
                f"diff -q {source} {cfg_target} 2>/dev/null",
                key_path, check=False
            )
            if diff_check.returncode == 0:
                click.echo(f"    Unchanged: {cfg}")
                continue

            commands = [
                # Create parent directory
                f"mkdir -p $(dirname {cfg_target})",
                # Backup existing (only if file exists and is different)
                f"[ -f {cfg_target} ] && cp {cfg_target} "
                f"{cfg_target}.bak.$(date +%Y%m%d_%H%M%S) || true",
                # Copy new file
                f"cp {source} {cfg_target}",
            ]

            for cmd in commands:
                ssh_exec(user, host, port, cmd, key_path, check=False)

            click.secho(f"    Applied: {cfg}", fg="green")
