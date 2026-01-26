"""Profile inheritance logic for my-config."""

from typing import Any


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

        # Merge apps (child overrides parent)
        for app_name, app_config in prof.get("apps", {}).items():
            merged["apps"][app_name] = app_config.copy() if app_config else {}

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

    return {
        "name": profile_name,
        "extends": prof.get("extends"),
        "direct_apps": list(prof.get("apps", {}).keys()),
        "direct_configs": prof.get("configs", []),
        "resolved_apps": list(resolved["apps"].keys()),
        "resolved_configs": resolved["configs"],
    }
