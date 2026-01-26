"""Remote deployment via SSH for my-config."""

import os
import tempfile
from pathlib import Path

import click

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

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


def get_default_ssh_key() -> Path | None:
    """Get the default SSH key path."""
    ssh_dir = Path.home() / ".ssh"

    # Try common key names in order of preference
    key_names = ["id_ed25519", "id_ecdsa", "id_rsa"]
    for name in key_names:
        key_path = ssh_dir / name
        if key_path.exists():
            return key_path

    return None


def ensure_ssh_key_on_remote(
    client: "paramiko.SSHClient",
    local_key_path: Path,
) -> None:
    """Ensure the local public key is in remote authorized_keys."""
    pub_key_path = local_key_path.with_suffix(".pub")

    if not pub_key_path.exists():
        click.secho(
            f"Warning: No public key found at {pub_key_path}",
            fg="yellow",
        )
        return

    pub_key = pub_key_path.read_text().strip()

    # Check if key already exists
    stdin, stdout, stderr = client.exec_command(
        "cat ~/.ssh/authorized_keys 2>/dev/null || echo ''"
    )
    authorized_keys = stdout.read().decode()

    if pub_key in authorized_keys:
        click.echo("  SSH key already authorized on remote")
        return

    # Add key
    click.echo("  Adding SSH key to remote authorized_keys...")
    commands = [
        "mkdir -p ~/.ssh",
        "chmod 700 ~/.ssh",
        f"echo '{pub_key}' >> ~/.ssh/authorized_keys",
        "chmod 600 ~/.ssh/authorized_keys",
    ]

    for cmd in commands:
        stdin, stdout, stderr = client.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error = stderr.read().decode()
            raise click.ClickException(f"Failed to setup SSH key: {error}")

    click.secho("  SSH key added to remote", fg="green")


def remote_deploy(
    target: str,
    profile: str,
    key_path: str | None = None,
) -> None:
    """Deploy configuration to a remote host.

    Args:
        target: user@host or user@host:port
        profile: Profile name to deploy
        key_path: Optional path to SSH private key
    """
    if not HAS_PARAMIKO:
        raise click.ClickException(
            "paramiko is required for remote deployment. "
            "Install it with: pip install paramiko"
        )

    user, host, port = parse_target(target)
    click.echo(f"Connecting to {user}@{host}:{port}...")

    # Determine SSH key
    if key_path:
        ssh_key = Path(key_path)
    else:
        ssh_key = get_default_ssh_key()

    if not ssh_key:
        raise click.ClickException(
            "No SSH key found. Use --key or create ~/.ssh/id_ed25519"
        )

    # Load and resolve profile
    config = load_config()
    resolved = resolve_profile(config, profile)

    # Connect via SSH
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=user,
            key_filename=str(ssh_key),
            look_for_keys=True,
            allow_agent=True,
        )
        click.secho("  Connected!", fg="green")

        # Ensure SSH key is authorized
        ensure_ssh_key_on_remote(client, ssh_key)

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
            sftp = client.open_sftp()
            remote_archive = f"/tmp/myconfig_deploy_{os.getpid()}.tar.gz.enc"
            sftp.put(str(archive_path), remote_archive)
            sftp.close()

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
                stdin, stdout, stderr = client.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error = stderr.read().decode()
                    click.secho(f"  Warning: {error}", fg="yellow")

        # Install packages
        apps = resolved.get("apps", {})
        if apps:
            click.echo(f"  Installing {len(apps)} app(s)...")
            preference = config["package_managers"]["preference"]

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
                    elif mgr == "snap":
                        cmd = f"sudo snap install {app_name}"
                    elif mgr == "cargo":
                        cmd = f"cargo install {app_name}"
                    else:
                        continue

                    click.echo(f"    {app_name} via {mgr}...")
                    stdin, stdout, stderr = client.exec_command(cmd)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status == 0:
                        click.secho(f"    {app_name}: installed", fg="green")
                        installed = True
                        break
                    else:
                        msg = f"    {app_name}: failed via {mgr}"
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
                target = f"~/{cfg}"

                commands = [
                    # Create parent directory
                    f"mkdir -p $(dirname {target})",
                    # Backup existing
                    f"[ -f {target} ] && cp {target} "
                    f"{target}.bak.$(date +%Y%m%d_%H%M%S) || true",
                    # Copy new file
                    f"cp {source} {target}",
                ]

                for cmd in commands:
                    stdin, stdout, stderr = client.exec_command(cmd)
                    stdout.channel.recv_exit_status()

                click.secho(f"    Applied: {cfg}", fg="green")

        click.secho("\nDeployment complete!", fg="green", bold=True)

    finally:
        client.close()
