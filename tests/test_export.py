"""Tests for encrypted export and import."""

import io
import shutil
import tarfile

import pytest
from click import ClickException

from myconfig.export import _openssl, extract_archive

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="openssl not installed"
)


def test_roundtrip_preserves_permissions(run, home, initialized, tmp_path):
    netrc = home / ".netrc"
    netrc.write_text("machine example.com password hunter2\n")
    netrc.chmod(0o600)
    run("add", "config", str(netrc))

    out = tmp_path / "out"
    out.mkdir()
    result = run("export", str(out), input="pw\npw\n")
    assert result.exit_code == 0, result.output
    archive = next(out.glob("*.tar.gz.enc"))
    assert archive.with_suffix(".enc.sha256").exists()

    shutil.rmtree(initialized)
    netrc.unlink()

    result = run("import", str(archive), input="pw\n")
    assert result.exit_code == 0, result.output
    assert "Checksum verified" in result.output

    result = run("apply", "--config")
    assert result.exit_code == 0, result.output
    assert netrc.read_text() == "machine example.com password hunter2\n"
    assert netrc.stat().st_mode & 0o777 == 0o600


def test_wrong_password(run, initialized, tmp_path):
    out = tmp_path / "backup.tar.gz.enc"
    run("export", str(out), input="pw\npw\n")

    result = run("import", str(out), input="nope\n")
    assert result.exit_code == 1
    assert "Decryption failed" in result.output


def test_checksum_mismatch(run, initialized, tmp_path):
    out = tmp_path / "backup.tar.gz.enc"
    run("export", str(out), input="pw\npw\n")
    out.write_bytes(out.read_bytes() + b"x")

    result = run("import", str(out), input="pw\n")
    assert result.exit_code == 1
    assert "Checksum mismatch" in result.output


def make_archive(tmp_path, build):
    """Create an encrypted archive whose tar content is built by build()."""
    raw = tmp_path / "raw.tar.gz"
    with tarfile.open(raw, "w:gz") as tar:
        build(tar)
    enc = tmp_path / "evil.tar.gz.enc"
    result = _openssl(["-salt", "-in", str(raw), "-out", str(enc)], "pw")
    assert result.returncode == 0, result.stderr
    return enc


def add_file(tar, name, data=b"x"):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def add_symlink(tar, name, target):
    info = tarfile.TarInfo(name)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    tar.addfile(info)


@pytest.mark.parametrize(
    "build, message",
    [
        (lambda t: add_file(t, "files/../../evil"), "Invalid tracked path"),
        (lambda t: add_file(t, "/etc/evil"), "Unexpected entry"),
        (lambda t: add_file(t, "evil"), "Unexpected entry"),
        (lambda t: add_symlink(t, "config.yml", "/etc/passwd"),
         "non-regular file"),
        (lambda t: add_symlink(t, "files/.bashrc", "/etc/passwd"),
         "non-regular file"),
    ],
)
def test_unsafe_archives_rejected(home, tmp_path, build, message):
    def full(tar):
        add_file(tar, "config.yml", b"version: 1\nprofiles: {}\n")
        build(tar)

    archive = make_archive(tmp_path, full)
    with pytest.raises(ClickException, match=message):
        extract_archive(archive, "pw")
    # Nothing is written when the archive is rejected
    assert not (home / ".config" / "myconfig" / "config.yml").exists()
