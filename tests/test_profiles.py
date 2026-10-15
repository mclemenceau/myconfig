"""Tests for profile inheritance."""

import pytest
from click import ClickException

from myconfig.profiles import resolve_profile


def make(**profiles):
    return {"version": 1, "profiles": profiles}


def test_resolve_merges_parent_first():
    config = make(
        base={"apps": {"apt": ["git", "curl"]}, "configs": [".bashrc"]},
        work={
            "extends": "base",
            "apps": {"apt": ["docker"], "snap": [{"code": "--classic"}]},
            "configs": [".kube/config"],
        },
    )
    resolved = resolve_profile(config, "work")
    assert resolved["apps"] == {
        "apt": ["git", "curl", "docker"],
        "snap": [{"code": "--classic"}],
    }
    assert resolved["configs"] == [".bashrc", ".kube/config"]


def test_resolve_deduplicates():
    config = make(
        base={"apps": {"apt": ["git"]}, "configs": [".bashrc"]},
        work={
            "extends": "base",
            "apps": {"apt": ["git"]},
            "configs": [".bashrc"],
        },
    )
    resolved = resolve_profile(config, "work")
    assert resolved["apps"] == {"apt": ["git"]}
    assert resolved["configs"] == [".bashrc"]


def test_resolve_multi_level():
    config = make(
        a={"configs": [".a"]},
        b={"extends": "a", "configs": [".b"]},
        c={"extends": "b", "configs": [".c"]},
    )
    assert resolve_profile(config, "c")["configs"] == [".a", ".b", ".c"]


@pytest.mark.parametrize(
    "config, name, message",
    [
        (make(), "base", "Profile not found: base"),
        (make(a={"extends": "zzz"}), "a", "inheritance chain: zzz"),
        (make(a={"extends": "a"}), "a", "Circular inheritance"),
    ],
)
def test_resolve_errors(config, name, message):
    with pytest.raises(ClickException, match=message):
        resolve_profile(config, name)
