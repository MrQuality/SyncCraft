"""Error helpers for consistent user-facing failure messages."""


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
