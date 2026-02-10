"""Unit tests for structured error classes and message parsing."""

import pytest

from synccraft.errors import ConfigError, ExitCode, ProcessingError, ValidationError, format_user_error, parse_user_error_message


@pytest.mark.unit
def test_structured_errors_expose_message_triad() -> None:
    """Structured error classes retain what/why/remediation and formatted rendering."""
    error = ValidationError(
        what="invalid image",
        why="file extension unsupported",
        remediation="use a .png file",
    )

    assert error.what == "invalid image"
    assert error.why == "file extension unsupported"
    assert error.remediation == "use a .png file"
    assert str(error) == "what: invalid image; why: file extension unsupported; how-to-fix: use a .png file"


@pytest.mark.unit
def test_exit_codes_per_error_category() -> None:
    """Each major failure class maps to a deterministic non-zero exit code."""
    assert ConfigError(what="c", why="w", remediation="r").exit_code == int(ExitCode.CONFIG)
    assert ValidationError(what="c", why="w", remediation="r").exit_code == int(ExitCode.VALIDATION)
    assert ProcessingError(what="c", why="w", remediation="r").exit_code == int(ExitCode.PROCESSING)


@pytest.mark.unit
def test_parse_user_error_message_extracts_triads() -> None:
    """Triad parser decodes formatted user messages for structured wrapping."""
    rendered = format_user_error(what="a", why="b", how_to_fix="c")

    assert parse_user_error_message(rendered) == ("a", "b", "c")
    assert parse_user_error_message("plain error") is None
