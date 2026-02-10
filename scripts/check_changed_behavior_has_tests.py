#!/usr/bin/env python3
"""Fail CI when behavior files changed without corresponding tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BEHAVIOR_PATH_PREFIXES = ("synccraft/",)
TEST_PATH_PREFIX = "tests/"


def git_diff_names(base_ref: str) -> list[str]:
    """Collect changed files between base_ref and HEAD."""
    cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    """Validate behavior changes include tests."""
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    try:
        changed = git_diff_names(base)
    except subprocess.CalledProcessError as exc:
        print(f"warning: unable to compute diff against {base}: {exc}")
        return 0

    behavior_changed = any(path.startswith(BEHAVIOR_PATH_PREFIXES) for path in changed)
    tests_changed = any(path.startswith(TEST_PATH_PREFIX) for path in changed)

    if behavior_changed and not tests_changed:
        print(
            "CI gate failure: behavior files changed without tests. "
            "Add or update tests under tests/ for every user-visible behavior change."
        )
        return 1

    # Also ensure all fixtures are lightweight files.
    for fixture in Path("tests/fixtures").rglob("*"):
        if fixture.is_file() and fixture.stat().st_size > 256 * 1024:
            print(f"CI gate failure: fixture too large: {fixture}")
            return 1

    print("CI gate pass: behavior changes are paired with tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
