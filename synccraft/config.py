"""Configuration merge logic for SyncCraft."""

from __future__ import annotations

from typing import Any

from synccraft.errors import format_user_error

# Optional keys accepted even when absent from hard defaults.
KNOWN_OPTIONAL_CONFIG_KEYS = {"language"}


def merge_config(*, defaults: dict[str, Any], file_config: dict[str, Any], cli_args: dict[str, Any]) -> dict[str, Any]:
    """Merge layered config with validation and deterministic precedence.

    Precedence order is defaults < file_config < cli_args (non-None values only).
    """
    allowed_keys = set(defaults) | KNOWN_OPTIONAL_CONFIG_KEYS
    unknown_keys = [key for key in file_config if key not in allowed_keys]
    if unknown_keys:
        key = unknown_keys[0]
        raise ValueError(
            format_user_error(
                what=f"unknown config key '{key}'.",
                why="configuration file contains unsupported fields",
                how_to_fix="remove it or add it to the default config schema",
            )
        )

    merged = dict(defaults)
    merged.update(file_config)
    for key, value in cli_args.items():
        if value is not None:
            merged[key] = value
    return merged
