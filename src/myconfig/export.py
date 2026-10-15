"""Export and import functionality for myconfig."""

import hashlib
import os
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

import click

from .config import (
    get_config_dir,
    get_config_path,
    get_files_dir,
    validate_relative,
)


def _openssl(args: list[str], password: str) -> subprocess.CompletedProcess:
    """Run openssl enc, passing the password on stdin.

    Passing it as an argument would expose it to other local users
    through the process list.
    """
    return subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-pass", "stdin",
         *args],
        input=password + "\n",
        capture_output=True,
        text=True,
    )


def _write_file(path: Path, data: bytes, mode: int) -> None:
    """Write a file with the given permissions (e.g. 0600 for secrets).

    The file is never readable with wider permissions, even briefly.
    """
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode & 0o777)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.chmod(path, mode & 0o777)  # O_CREAT mode is filtered by umask


def create_archive(destination: Path, password: str) -> Path:
    """Create an encrypted archive of the configuration.

    Args:
        destination: Directory or file path for the archive
        password: Password for encryption

    Returns:
        Path to the created archive
    """
    config_dir = get_config_dir()

    if not config_dir.exists():
        msg = "Configuration not initialized. Run 'myconfig init' first."
        raise click.ClickException(msg)

    # Determine output path
    if destination.is_dir():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"myconfig_{timestamp}.tar.gz.enc"
        output_path = destination / archive_name
    else:
        output_path = destination
        if not output_path.suffix:
            output_path = output_path.with_suffix(".tar.gz.enc")

    # Create temporary tar.gz
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Create tar.gz archive
        with tarfile.open(tmp_path, "w:gz") as tar:
            # Add config.yml
            config_path = get_config_path()
            if config_path.exists():
                tar.add(config_path, arcname="config.yml")

            # Add files directory
            files_dir = get_files_dir()
            if files_dir.exists():
                for file_path in files_dir.rglob("*"):
                    if file_path.is_file():
                        rel = str(file_path.relative_to(files_dir))
                        tar.add(file_path, arcname="files/" + rel)

        # Encrypt with openssl (widely available), AES-256-CBC with PBKDF2
        result = _openssl(
            ["-salt", "-in", str(tmp_path), "-out", str(output_path)],
            password,
        )

        if result.returncode != 0:
            raise click.ClickException(f"Encryption failed: {result.stderr}")

        # Create checksum
        checksum = hashlib.sha256(output_path.read_bytes()).hexdigest()
        checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
        checksum_path.write_text(f"{checksum}  {output_path.name}\n")

        click.echo(f"Checksum: {checksum_path}")

        return output_path

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()


def extract_archive(archive_path: Path, password: str) -> None:
    """Extract an encrypted archive to the configuration directory.

    Args:
        archive_path: Path to the encrypted archive
        password: Password for decryption
    """
    config_dir = get_config_dir()

    # Verify checksum if available
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if checksum_path.exists():
        expected = checksum_path.read_text().split()[0]
        actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if expected != actual:
            raise click.ClickException(
                f"Checksum mismatch! Expected {expected}, got {actual}"
            )
        click.echo("Checksum verified.")

    # Create temporary decrypted file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Decrypt with openssl
        result = _openssl(
            ["-d", "-in", str(archive_path), "-out", str(tmp_path)],
            password,
        )

        if result.returncode != 0:
            raise click.ClickException(
                "Decryption failed. Wrong password or corrupted archive."
            )

        # Extract tar.gz
        files_dir = get_files_dir()
        files_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tmp_path, "r:gz") as tar:
            members = tar.getmembers()
            if not any(m.name == "config.yml" for m in members):
                click.secho("  Warning: no config.yml in archive", fg="yellow")

            # Validate everything before writing anything. Only regular
            # files at known locations are accepted, which rejects links,
            # devices and path traversal.
            plan = []
            for member in members:
                if member.isdir():
                    continue
                if member.name == "config.yml":
                    target = config_dir / "config.yml"
                elif member.name.startswith("files/"):
                    relative = validate_relative(member.name[len("files/"):])
                    target = files_dir / relative
                else:
                    raise click.ClickException(
                        f"Unexpected entry in archive: {member.name}"
                    )
                if not member.isfile():
                    raise click.ClickException(
                        f"Archive contains a non-regular file: {member.name}"
                    )
                plan.append((member, target))

            for member, target in plan:
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_file(
                    target, tar.extractfile(member).read(), member.mode
                )
                click.echo(f"  Extracted: {member.name}")

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
