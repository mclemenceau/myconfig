"""Tests for secret detection."""

import pytest

from myconfig.secrets import check_secrets


@pytest.mark.parametrize(
    "name", [".env", ".env.local", "id_rsa", "id_ed25519", ".netrc",
             "server.pem", "github_token", "aws_credentials"],
)
def test_secret_file_names(tmp_path, name):
    path = tmp_path / name
    path.write_text("nothing to see\n")
    assert check_secrets(path, name)


@pytest.mark.parametrize(
    "content",
    [
        "-----BEGIN OPENSSH PRIVATE KEY-----\n",
        "-----BEGIN PRIVATE KEY-----\n",
        "token = ghp_" + "a" * 36 + "\n",
        "github_pat_" + "a" * 40 + "\n",
        "aws_access_key_id = AKIA" + "A" * 16 + "\n",
        "password: hunter2hunter2\n",
        "API_KEY=" + "x" * 32 + "\n",
    ],
)
def test_secret_contents(tmp_path, content):
    path = tmp_path / "config"
    path.write_text(content)
    warnings = check_secrets(path, "config")
    assert len(warnings) == 1


def test_clean_file(tmp_path):
    path = tmp_path / ".bashrc"
    path.write_text("alias ll='ls -l'\nexport EDITOR=hx\n")
    assert check_secrets(path, ".bashrc") == []


def test_binary_file(tmp_path):
    path = tmp_path / "blob"
    path.write_bytes(bytes(range(256)))
    assert check_secrets(path, "blob") == []
