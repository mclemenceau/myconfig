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
        ssh_cmd.append("-tt")  # Force pseudo-TTY allocation for interactive commands

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
        raise click.ClickException(f"SSH connection failed: {e.stderr}")

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
            raise click.ClickException(f"Upload failed: {e.stderr}")

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

    # Install packages
    apps = resolved.get("apps", {})
    if apps:
        click.echo(f"  Installing {len(apps)} app(s)...")
        preference = config["package_managers"]["preference"]

        # Check if passwordless sudo is available
        sudo_check = ssh_exec(
            user, host, port, "sudo -n true 2>/dev/null", key_path, check=False
        )
        needs_sudo_password = sudo_check.returncode != 0

        if needs_sudo_password:
            click.secho(
                "  Note: sudo requires password - you will be prompted interactively",
                fg="yellow",
            )
            click.echo("  (Tip: configure passwordless sudo for non-interactive deploys)")

        for app_name, app_config in apps.items():
            prefer = app_config.get("prefer")
            if prefer:
                managers = [prefer]
            else:
                managers = preference

            installed = False
            for mgr in managers:
                if mgr == "apt":
                    cmd = f"sudo apt install -y {app_name}"
                    needs_tty = needs_sudo_password
                elif mgr == "snap":
                    cmd = f"sudo snap install {app_name}"
                    needs_tty = needs_sudo_password
                elif mgr == "cargo":
                    cmd = f"cargo install {app_name}"
                    needs_tty = False
                else:
                    continue

                click.echo(f"    {app_name} via {mgr}...")
                result = ssh_exec(
                    user, host, port, cmd, key_path,
                    check=False, interactive=needs_tty
                )
                if result.returncode == 0:
                    click.secho(f"    {app_name}: installed", fg="green")
                    installed = True
                    break
                else:
                    # Get error message (only available in non-interactive mode)
                    err = result.stderr if hasattr(result, 'stderr') and result.stderr else ""
                    msg = f"    {app_name}: failed via {mgr}"
                    if err and "not found" in err.lower():
                        msg += " (package not found)"
                    click.secho(msg, fg="yellow")

            if not installed:
                click.secho(f"    {app_name}: could not install", fg="red")

    # Apply config files
    configs = resolved.get("configs", [])
    if configs:
        click.echo(f"  Applying {len(configs)} config file(s)...")

        for cfg in configs:
            # Source is in ~/.config/myconfig/files/
            source = f"~/.config/myconfig/files/{cfg}"
            # Target is in home directory
            cfg_target = f"~/{cfg}"

            commands = [
                # Create parent directory
                f"mkdir -p $(dirname {cfg_target})",
                # Backup existing
                f"[ -f {cfg_target} ] && cp {cfg_target} "
                f"{cfg_target}.bak.$(date +%Y%m%d_%H%M%S) || true",
                # Copy new file
                f"cp {source} {cfg_target}",
            ]

            for cmd in commands:
                ssh_exec(user, host, port, cmd, key_path, check=False)

            click.secho(f"    Applied: {cfg}", fg="green")
