"""Profile inheritance logic for myconfig."""

from typing import Any

import click

from .config import get_app_name


def resolve_profile(
    config: dict[str, Any], profile_name: str
) -> dict[str, Any]:
    """Resolve a profile with its inheritance chain.

    Returns a merged profile dict with all inherited apps and configs.
    """
    profiles = config.get("profiles", {})

    if profile_name not in profiles:
        raise click.ClickException(f"Profile not found: {profile_name}")

    # Build inheritance chain (child -> parent -> grandparent -> ...)
    chain = []
    current = profile_name
    visited = set()

    while current:
        if current in visited:
            raise click.ClickException(
                f"Circular inheritance detected: {current}"
            )
        visited.add(current)

        if current not in profiles:
            msg = f"Profile not found in inheritance chain: {current}"
            raise click.ClickException(msg)

        chain.append(current)
        current = profiles[current].get("extends")

    # Reverse to process from base to child (so child overrides parent)
    chain.reverse()

    # Merge profiles
    merged = {"apps": {}, "configs": []}
    seen_configs = set()

    for prof_name in chain:
        prof = profiles[prof_name]

        # Merge apps (grouped by manager)
        for manager, pkg_list in prof.get("apps", {}).items():
            if isinstance(pkg_list, list):
                if manager not in merged["apps"]:
                    merged["apps"][manager] = []
                # Get existing app names for dedup
                existing_names = [
                    get_app_name(item) for item in merged["apps"][manager]
                ]
                for pkg in pkg_list:
                    pkg_name = get_app_name(pkg)
                    if pkg_name not in existing_names:
                        merged["apps"][manager].append(pkg)
                        existing_names.append(pkg_name)

        # Merge configs (deduplicate, preserve order)
        for cfg in prof.get("configs", []):
            if cfg not in seen_configs:
                seen_configs.add(cfg)
                merged["configs"].append(cfg)

    return merged

