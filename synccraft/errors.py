"""Error helpers and structured error types for user-facing failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ExitCode(IntEnum):
    """Process exit codes used by the SyncCraft CLI."""

    OK = 0
    INTERNAL = 1
    CONFIG = 2
    VALIDATION = 3
    PROVIDER = 4
    PROCESSING = 5


@dataclass(slots=True)
class SyncCraftError(Exception):
    """Structured base error carrying user-facing triad and an exit code."""

    what: str
    why: str
    remediation: str
    exit_code: int = int(ExitCode.VALIDATION)

    def __str__(self) -> str:
        """Render the standardized user-facing message."""
        return format_user_error(what=self.what, why=self.why, how_to_fix=self.remediation)


class ConfigError(SyncCraftError):
    """Failure caused by invalid or missing configuration."""

    def __init__(self, *, what: str, why: str, remediation: str) -> None:
        super().__init__(what=what, why=why, remediation=remediation, exit_code=int(ExitCode.CONFIG))


class ValidationError(SyncCraftError):
    """Failure caused by invalid user input or unsupported media."""

    def __init__(self, *, what: str, why: str, remediation: str) -> None:
        super().__init__(what=what, why=why, remediation=remediation, exit_code=int(ExitCode.VALIDATION))


class ProviderError(SyncCraftError):
    """Failure caused by provider payload or provider execution."""

    def __init__(self, *, what: str, why: str, remediation: str) -> None:
        super().__init__(what=what, why=why, remediation=remediation, exit_code=int(ExitCode.PROVIDER))


class ProcessingError(SyncCraftError):
    """Failure caused while chunking or assembling processing outputs."""

    def __init__(self, *, what: str, why: str, remediation: str) -> None:
        super().__init__(what=what, why=why, remediation=remediation, exit_code=int(ExitCode.PROCESSING))


def parse_user_error_message(message: str) -> tuple[str, str, str] | None:
    """Parse a formatted triad error message into its components when possible."""
    prefix_what = "what: "
    middle = "; why: "
    suffix = "; how-to-fix: "
    if not message.startswith(prefix_what) or middle not in message or suffix not in message:
        return None

    what_end = message.find(middle)
    why_end = message.find(suffix)
    if what_end < 0 or why_end < 0 or why_end < what_end:
        return None

    what = message[len(prefix_what):what_end]
    why = message[what_end + len(middle):why_end]
    remediation = message[why_end + len(suffix):]
    return what, why, remediation


def format_user_error(*, what: str, why: str, how_to_fix: str) -> str:
    """Build a structured error message for users.

    Args:
        what: A concise description of what failed.
        why: Why the failure happened.
        how_to_fix: Immediate actionable remediation steps.

    Returns:
        A three-part error message string.
    """
    return f"what: {what}; why: {why}; how-to-fix: {how_to_fix}"
