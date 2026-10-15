"""Tests for package manager handling."""

from unittest.mock import MagicMock, patch

from myconfig.packages import (
    AptManager,
    CargoManager,
    SnapManager,
    install_apps,
)

CARGO_LIST = """\
helix-term v25.7.1 (/src/helix/helix-term):
    hx
ripgrep v14.1.1:
    rg
"""


@patch("myconfig.packages.subprocess.run")
def test_cargo_is_installed_uses_crate_names(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout=CARGO_LIST)
    assert CargoManager.is_installed("helix-term")
    assert CargoManager.is_installed("ripgrep")
    # Binary names are not crate names
    assert not CargoManager.is_installed("hx")
    assert not CargoManager.is_installed("rg")


@patch("myconfig.packages.subprocess.run")
def test_apt_is_installed_ignores_removed(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0, stdout="deinstall ok config-files"
    )
    assert not AptManager.is_installed("vim")
    mock_run.return_value = MagicMock(
        returncode=0, stdout="install ok installed"
    )
    assert AptManager.is_installed("vim")


def test_install_batch_skips_installed():
    with patch.object(
        AptManager, "is_installed", side_effect=lambda p: p == "git"
    ), patch.object(AptManager, "_run", return_value=True) as run:
        ok, failed = AptManager.install_batch(["git", "curl"])
    assert sorted(ok) == ["curl", "git"]
    assert failed == []
    run.assert_called_once_with(
        ["sudo", "apt", "install", "-y", "curl"], False
    )


def test_install_batch_falls_back_to_individual():
    def fake_run(cmd, dry_run):
        # The batch fails because of "bad"; individual installs work
        return "bad" not in cmd

    with patch.object(SnapManager, "is_installed", return_value=False), \
            patch.object(SnapManager, "_run", side_effect=fake_run):
        ok, failed = SnapManager.install_batch(["good", "bad"])
    assert ok == ["good"]
    assert failed == ["bad"]


def test_cargo_installs_one_by_one():
    with patch.object(CargoManager, "is_installed", return_value=False), \
            patch.object(CargoManager, "_run", return_value=True) as run:
        CargoManager.install_batch(["a", "b"])
    assert [c.args[0] for c in run.call_args_list] == [
        ["cargo", "install", "a"],
        ["cargo", "install", "b"],
    ]


def test_install_with_params():
    with patch.object(SnapManager, "_run", return_value=True) as run:
        SnapManager.install("code", params="--classic --channel=stable")
    run.assert_called_once_with(
        ["sudo", "snap", "install", "--classic", "--channel=stable", "code"],
        False,
    )


def test_install_apps_unavailable_manager(capsys):
    with patch.object(CargoManager, "is_available", return_value=False):
        install_apps({"cargo": ["ripgrep"], "brew": ["x"]})
    out = capsys.readouterr().out
    assert "Package manager not available: cargo" in out
    assert "Package manager not available: brew" in out
    assert "Skipping: ripgrep" in out


def test_install_apps_dry_run(capsys):
    with patch.object(SnapManager, "is_available", return_value=True), \
            patch.object(SnapManager, "is_installed", return_value=False):
        install_apps(
            {"snap": ["vlc", {"code": "--classic"}]}, dry_run=True
        )
    out = capsys.readouterr().out
    assert "Would run: sudo snap install vlc" in out
    assert "Would run: sudo snap install --classic code" in out
