"""Typed configuration model and merge/validation helpers for SyncCraft."""

from __future__ import annotations

import copy
import logging
import string
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from synccraft.errors import format_user_error

_ALLOWED_CHUNK_FAILURE_POLICIES = {"stop", "continue"}
_ALLOWED_FILENAME_PLACEHOLDERS = {"stem", "index", "ext", "chunk_start", "chunk_end"}
_SECRET_FIELD_MARKERS = ("key", "token", "secret", "password", "credential")


@dataclass(slots=True)
class InputConfig:
    """Input media configuration."""

    audio_path: str | None = None


@dataclass(slots=True)
class AudioConfig:
    """Chunking and chunk-failure behavior configuration."""

    chunk_seconds: int | None = None
    on_chunk_failure: str = "stop"


@dataclass(slots=True)
class OutputConfig:
    """Filesystem output configuration."""

    directory: str = "./out"
    filename_template: str = "{stem}_{index:03d}.{ext}"


@dataclass(slots=True)
class ProviderConfig:
    """Provider integration configuration."""

    name: str = "mock"
    api_key: str | None = None
    endpoint: str | None = None


@dataclass(slots=True)
class AppConfig:
    """Top-level typed config mirroring PRD sections."""

    input: InputConfig
    audio: AudioConfig
    output: OutputConfig
    provider: ProviderConfig


# Optional keys accepted even when absent from hard defaults.
KNOWN_OPTIONAL_CONFIG_KEYS = {"language"}


def default_config() -> AppConfig:
    """Build the default typed configuration."""
    return AppConfig(input=InputConfig(), audio=AudioConfig(), output=OutputConfig(), provider=ProviderConfig())


def merge_typed_config(*, defaults: AppConfig, yaml_config: Mapping[str, Any], cli_args: Mapping[str, Any]) -> AppConfig:
    """Merge layered typed configuration with precedence defaults < YAML < CLI."""
    _validate_top_level_sections(yaml_config=yaml_config)
    _validate_top_level_sections(yaml_config=cli_args)

    merged_dict = _deep_merge(asdict(defaults), yaml_config)
    merged_dict = _deep_merge(merged_dict, _drop_none_values(cli_args))

    merged = _dict_to_typed_config(merged_dict)
    validate_config_values(merged)
    return merged


def validate_execution_requirements(config: AppConfig) -> None:
    """Validate fields that must be resolved at execution time."""
    if not config.input.audio_path:
        raise ValueError(
            format_user_error(
                what="input.audio_path is required at execution time.",
                why="the pipeline cannot run without an input audio file",
                how_to_fix="set input.audio_path in YAML or pass --audio",
            )
        )


def validate_config_values(config: AppConfig) -> None:
    """Validate enum-like and templating safety constraints."""
    if config.audio.on_chunk_failure not in _ALLOWED_CHUNK_FAILURE_POLICIES:
        options = ", ".join(sorted(_ALLOWED_CHUNK_FAILURE_POLICIES))
        raise ValueError(
            format_user_error(
                what=f"audio.on_chunk_failure must be one of: {options}.",
                why="unsupported chunk failure handling policy was provided",
                how_to_fix=f"choose one of {options} in YAML or CLI override",
            )
        )

    _validate_filename_template(config.output.filename_template)


def warn_on_possible_secrets(config: AppConfig, *, logger: logging.Logger | None = None) -> list[str]:
    """Warn when key-like fields appear populated without echoing the underlying value."""
    target_logger = logger or logging.getLogger(__name__)
    warnings: list[str] = []
    for field_path, value in _iter_nested_items(asdict(config)):
        leaf_name = field_path.split(".")[-1].lower()
        if any(marker in leaf_name for marker in _SECRET_FIELD_MARKERS) and value not in (None, ""):
            message = (
                f"Potential secret material detected at '{field_path}'. "
                "Do not commit secrets in config files. Value is redacted."
            )
            target_logger.warning(message)
            warnings.append(message)
    return warnings


def merge_config(*, defaults: dict[str, Any], file_config: dict[str, Any], cli_args: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible flat merge helper.

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


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge mapping values where `override` wins."""
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _drop_none_values(values: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively remove explicit None values from override maps."""
    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, Mapping):
            nested = _drop_none_values(value)
            if nested:
                cleaned[key] = nested
            continue
        cleaned[key] = value
    return cleaned


def _validate_top_level_sections(*, yaml_config: Mapping[str, Any]) -> None:
    """Ensure config contains only known top-level PRD sections."""
    allowed = {"input", "audio", "output", "provider"}
    unknown_sections = [key for key in yaml_config if key not in allowed]
    if unknown_sections:
        section = unknown_sections[0]
        raise ValueError(
            format_user_error(
                what=f"unknown config section '{section}'.",
                why="configuration must map to supported PRD sections",
                how_to_fix="use only: input, audio, output, provider",
            )
        )


def _dict_to_typed_config(raw: Mapping[str, Any]) -> AppConfig:
    """Map validated dictionary data into the typed config dataclasses."""
    input_data = dict(raw.get("input", {}))
    audio_data = dict(raw.get("audio", {}))
    output_data = dict(raw.get("output", {}))
    provider_data = dict(raw.get("provider", {}))

    return AppConfig(
        input=InputConfig(**input_data),
        audio=AudioConfig(**audio_data),
        output=OutputConfig(**output_data),
        provider=ProviderConfig(**provider_data),
    )


def _validate_filename_template(template: str) -> None:
    """Allow only safe placeholder tokens for output filename templates."""
    formatter = string.Formatter()
    for _, field_name, _, _ in formatter.parse(template):
        if not field_name:
            continue
        token_name = field_name.split("!", 1)[0].split(":", 1)[0]
        if token_name not in _ALLOWED_FILENAME_PLACEHOLDERS:
            allowed_list = ", ".join(sorted(_ALLOWED_FILENAME_PLACEHOLDERS))
            raise ValueError(
                format_user_error(
                    what=f"output.filename_template uses unsupported placeholder '{token_name}'.",
                    why="unsafe or unknown placeholders can produce invalid output paths",
                    how_to_fix=f"use only supported placeholders: {allowed_list}",
                )
            )


def _iter_nested_items(data: Mapping[str, Any], *, prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested dictionaries into dotted key paths."""
    flattened: list[tuple[str, Any]] = []
    for key, value in data.items():
        current_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            flattened.extend(_iter_nested_items(value, prefix=current_key))
        else:
            flattened.append((current_key, value))
    return flattened
