"""Unit tests for typed config merge, validation, and secret warnings."""

from __future__ import annotations

import logging

import pytest

from synccraft.config import (
    default_config,
    merge_typed_config,
    validate_execution_requirements,
    warn_on_possible_secrets,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("yaml_config", "cli_args", "expected_chunk_seconds", "expected_directory"),
    [
        ({}, {}, None, "./out"),
        ({"audio": {"chunk_seconds": 45}, "output": {"directory": "./yaml-out"}}, {}, 45, "./yaml-out"),
        (
            {"audio": {"chunk_seconds": 45}, "output": {"directory": "./yaml-out"}},
            {"audio": {"chunk_seconds": 10}, "output": {"directory": "./cli-out"}},
            10,
            "./cli-out",
        ),
        ({"audio": {"chunk_seconds": 45}}, {"audio": {"chunk_seconds": None}}, 45, "./out"),
    ],
)
def test_precedence_matrix_defaults_yaml_cli(
    yaml_config: dict,
    cli_args: dict,
    expected_chunk_seconds: int | None,
    expected_directory: str,
) -> None:
    merged = merge_typed_config(defaults=default_config(), yaml_config=yaml_config, cli_args=cli_args)

    assert merged.audio.chunk_seconds == expected_chunk_seconds
    assert merged.output.directory == expected_directory


@pytest.mark.unit
def test_execution_requirements_missing_audio_has_remediation_hint() -> None:
    merged = merge_typed_config(defaults=default_config(), yaml_config={}, cli_args={})

    with pytest.raises(
        ValueError,
        match="what: input.audio_path is required at execution time.*how-to-fix: set input.audio_path",
    ):
        validate_execution_requirements(merged)


@pytest.mark.unit
def test_invalid_on_chunk_failure_has_remediation_hint() -> None:
    with pytest.raises(
        ValueError,
        match="what: audio.on_chunk_failure must be one of: continue, stop.*how-to-fix",
    ):
        merge_typed_config(
            defaults=default_config(),
            yaml_config={"audio": {"on_chunk_failure": "explode"}},
            cli_args={},
        )


@pytest.mark.unit
def test_invalid_filename_template_placeholder_has_remediation_hint() -> None:
    with pytest.raises(
        ValueError,
        match="what: output.filename_template uses unsupported placeholder 'api_key'.*how-to-fix",
    ):
        merge_typed_config(
            defaults=default_config(),
            yaml_config={"output": {"filename_template": "{stem}_{api_key}.{ext}"}},
            cli_args={},
        )


@pytest.mark.unit
def test_secret_warning_sanitizes_output_and_omits_raw_secret(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    secret_value = "sk-live-raw-value-123"

    merged = merge_typed_config(
        defaults=default_config(),
        yaml_config={"provider": {"api_key": secret_value}},
        cli_args={},
    )

    warnings = warn_on_possible_secrets(merged)

    assert len(warnings) == 1
    assert "provider.api_key" in warnings[0]
    assert secret_value not in warnings[0]
    assert "redacted" in warnings[0].lower()
    assert secret_value not in caplog.text
