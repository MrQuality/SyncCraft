"""Unit tests for configuration merge behavior."""

import pytest

from synccraft.config import merge_config


@pytest.mark.unit
def test_merge_config_prefers_cli_values_and_preserves_defaults() -> None:
    defaults = {"provider": "mock", "chunk_size": 25, "output": "./out"}
    file_config = {"chunk_size": 20, "language": "en"}
    cli = {"output": "./custom", "chunk_size": None}

    merged = merge_config(defaults=defaults, file_config=file_config, cli_args=cli)

    assert merged == {
        "provider": "mock",
        "chunk_size": 20,
        "output": "./custom",
        "language": "en",
    }


@pytest.mark.unit
def test_merge_config_rejects_unknown_keys_with_fix_hint() -> None:
    with pytest.raises(ValueError, match="what: unknown config key 'bogus'.*how-to-fix: remove it"):
        merge_config(defaults={"provider": "mock"}, file_config={"bogus": 1}, cli_args={})
