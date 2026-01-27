"""Profile inheritance logic for my-config."""

from typing import Any


def get_app_name(item):
    """Extract app name from a list item (string or dict)."""
    if isinstance(item, str):
        return item
    elif isinstance(item, dict):
        return list(item.keys())[0]
    return None


def resolve_profile(
    config: dict[str, Any], profile_name: str
) -> dict[str, Any]:
    """Resolve a profile with its inheritance chain.

    Returns a merged profile dict with all inherited apps and configs.
    """
    profiles = config.get("profiles", {})

    if profile_name not in profiles:
        raise ValueError(f"Profile not found: {profile_name}")

    # Build inheritance chain (child -> parent -> grandparent -> ...)
    chain = []
    current = profile_name
    visited = set()

    while current:
        if current in visited:
            raise ValueError(f"Circular inheritance detected: {current}")
        visited.add(current)

        if current not in profiles:
            msg = f"Profile not found in inheritance chain: {current}"
            raise ValueError(msg)

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
                existing_names = [get_app_name(item) for item in merged["apps"][manager]]
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


def list_profiles(config: dict[str, Any]) -> list[str]:
    """List all profile names."""
    return list(config.get("profiles", {}).keys())


def get_profile_info(
    config: dict[str, Any], profile_name: str
) -> dict[str, Any]:
    """Get information about a profile including inheritance."""
    profiles = config.get("profiles", {})

    if profile_name not in profiles:
        raise ValueError(f"Profile not found: {profile_name}")

    prof = profiles[profile_name]
    resolved = resolve_profile(config, profile_name)

    # Count direct apps (sum of all packages across managers)
    direct_apps = prof.get("apps", {})
    direct_app_count = sum(
        len(pkgs) for pkgs in direct_apps.values() if isinstance(pkgs, list)
    )

    # Count resolved apps
    resolved_apps = resolved["apps"]
    resolved_app_count = sum(
        len(pkgs) for pkgs in resolved_apps.values() if isinstance(pkgs, list)
    )

    return {
        "name": profile_name,
        "extends": prof.get("extends"),
        "direct_apps": direct_apps,
        "direct_app_count": direct_app_count,
        "direct_configs": prof.get("configs", []),
        "resolved_apps": resolved_apps,
        "resolved_app_count": resolved_app_count,
        "resolved_configs": resolved["configs"],
    }
