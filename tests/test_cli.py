"""End-to-end tests for the command-line interface."""

import yaml


def load(config_dir):
    return yaml.safe_load((config_dir / "config.yml").read_text())


def test_commands_require_init(run):
    result = run("list")
    assert result.exit_code == 1
    assert "Run 'myconfig init' first" in result.output
    assert "Traceback" not in result.output


def test_init_is_idempotent(run, initialized):
    result = run("init")
    assert result.exit_code == 0
    assert "Already initialized" in result.output


def test_add_and_remove_config(run, home, initialized):
    (home / ".bashrc").write_text("alias ll='ls -l'\n")

    result = run("add", "config", str(home / ".bashrc"))
    assert result.exit_code == 0, result.output
    assert load(initialized)["profiles"]["base"]["configs"] == [".bashrc"]
    assert (initialized / "files" / ".bashrc").exists()

    result = run("add", "config", str(home / ".bashrc"))
    assert "Already tracking" in result.output

    result = run("remove", "config", ".bashrc")
    assert result.exit_code == 0, result.output
    assert load(initialized)["profiles"]["base"]["configs"] == []
    assert not (initialized / "files" / ".bashrc").exists()
    # The real file is never touched by remove
    assert (home / ".bashrc").exists()


def test_add_config_keeps_symlink_path(run, home, initialized):
    (home / "dotfiles").mkdir()
    (home / "dotfiles" / "bashrc").write_text("x\n")
    (home / ".bashrc").symlink_to(home / "dotfiles" / "bashrc")

    result = run("add", "config", str(home / ".bashrc"))
    assert result.exit_code == 0, result.output
    assert load(initialized)["profiles"]["base"]["configs"] == [".bashrc"]


def test_add_config_outside_home_rejected(run, tmp_path, initialized):
    outside = tmp_path / "outside.conf"
    outside.write_text("x\n")

    result = run("add", "config", str(outside))
    assert result.exit_code == 1
    assert "Only files under $HOME" in result.output
    assert outside.read_text() == "x\n"


def test_add_config_directory_rejected(run, home, initialized):
    (home / ".vim").mkdir()
    result = run("add", "config", str(home / ".vim"))
    assert result.exit_code == 1
    assert "Cannot track directories" in result.output


def test_add_config_warns_on_secrets(run, home, initialized):
    (home / ".env").write_text("A=1\n")
    result = run("add", "config", str(home / ".env"))
    assert result.exit_code == 0
    assert "Warning: Environment file" in result.output


def test_profile_option_is_consistent(run, home, initialized):
    (home / ".foo").write_text("x\n")
    assert run("add", "config", str(home / ".foo"), "-P", "work").exit_code \
        == 0
    assert run("add", "app", "docker", "-P", "work").exit_code == 0

    profiles = load(initialized)["profiles"]
    assert profiles["work"]["configs"] == [".foo"]
    assert profiles["work"]["apps"] == {"apt": ["docker"]}

    result = run("list", "-P", "work")
    assert "[work]" in result.output
    assert "[base]" not in result.output


def test_add_and_remove_app(run, initialized):
    assert run("add", "app", "git").exit_code == 0
    assert run("add", "app", "helix-term", "-m", "cargo").exit_code == 0
    result = run("add", "app", "code", "-m", "snap", "-p", "--classic")
    assert result.exit_code == 0
    assert "[params: --classic]" in result.output

    apps = load(initialized)["profiles"]["base"]["apps"]
    assert apps == {
        "apt": ["git"],
        "cargo": ["helix-term"],
        "snap": [{"code": "--classic"}],
    }

    result = run("add", "app", "git", "-m", "snap")
    assert "Already tracking app: git (via apt)" in result.output

    assert run("remove", "app", "code").exit_code == 0
    assert "snap" not in load(initialized)["profiles"]["base"]["apps"]

    result = run("remove", "app", "missing")
    assert result.exit_code == 1


def test_list_output(run, home, initialized):
    (home / ".bashrc").write_text("x\n")
    run("add", "config", str(home / ".bashrc"))
    run("add", "app", "code", "-m", "snap", "-p", "--classic")

    result = run("list")
    assert "snap: code [--classic]" in result.output
    assert "[+] .bashrc" in result.output


def test_status_and_sync(run, home, initialized):
    rc = home / ".bashrc"
    rc.write_text("one\n")
    run("add", "config", str(rc))

    assert "All tracked files are in sync" in run("status").output

    rc.write_text("two\n")
    assert ".bashrc: modified" in run("status").output

    result = run("sync", "--dry-run")
    assert "Would sync: .bashrc" in result.output
    assert (initialized / "files" / ".bashrc").read_text() == "one\n"

    result = run("sync")
    assert "Synced: .bashrc" in result.output
    assert (initialized / "files" / ".bashrc").read_text() == "two\n"

    rc.unlink()
    assert ".bashrc: missing on system" in run("status").output


def test_apply_configs_with_backup(run, home, initialized):
    rc = home / ".bashrc"
    rc.write_text("stored\n")
    run("add", "config", str(rc))
    rc.write_text("local\n")

    result = run("apply", "--config", "--dry-run")
    assert "Would backup and replace: .bashrc" in result.output
    assert rc.read_text() == "local\n"

    result = run("apply", "--config")
    assert result.exit_code == 0, result.output
    assert rc.read_text() == "stored\n"
    backups = list(home.glob(".bashrc.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "local\n"

    result = run("apply", "--config")
    assert "Unchanged: .bashrc" in result.output


def test_apply_profile_inheritance(run, home, initialized):
    (home / ".a").write_text("a\n")
    (home / ".b").write_text("b\n")
    run("add", "config", str(home / ".a"))
    run("add", "config", str(home / ".b"), "-P", "work")
    config = load(initialized)
    config["profiles"]["work"]["extends"] = "base"
    (initialized / "config.yml").write_text(yaml.safe_dump(config))
    (home / ".a").unlink()
    (home / ".b").unlink()

    result = run("apply", "--config", "-P", "work")
    assert result.exit_code == 0, result.output
    assert (home / ".a").read_text() == "a\n"
    assert (home / ".b").read_text() == "b\n"


def test_apply_reports_bad_profiles(run, initialized):
    result = run("apply", "-P", "nope")
    assert result.exit_code == 1
    assert "Profile not found: nope" in result.output

    (initialized / "config.yml").write_text(
        "version: 1\nprofiles:\n"
        "  base: {extends: work}\n  work: {extends: base}\n"
    )
    result = run("apply", "--dry-run")
    assert result.exit_code == 1
    assert "Circular inheritance" in result.output


def test_tracked_path_traversal_rejected(run, initialized):
    (initialized / "config.yml").write_text(
        "version: 1\nprofiles:\n  base:\n    configs: [../../etc/passwd]\n"
    )
    result = run("status")
    assert result.exit_code == 1
    assert "Invalid tracked path" in result.output


def test_malformed_config(run, initialized):
    (initialized / "config.yml").write_text("profiles: [unclosed\n")
    result = run("list")
    assert result.exit_code == 1
    assert "Invalid" in result.output
    assert "Traceback" not in result.output


def test_apply_keeps_existing_permissions(run, home, initialized):
    netrc = home / ".netrc"
    netrc.write_text("stored\n")
    run("add", "config", str(netrc))
    (initialized / "files" / ".netrc").chmod(0o644)
    netrc.write_text("local\n")
    netrc.chmod(0o600)

    assert run("apply", "--config").exit_code == 0
    assert netrc.read_text() == "stored\n"
    assert netrc.stat().st_mode & 0o777 == 0o600
