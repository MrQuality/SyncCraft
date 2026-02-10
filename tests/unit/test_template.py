"""Unit tests for filename templating."""

import pytest

from synccraft.templating import render_filename


@pytest.mark.unit
def test_render_filename_template_replaces_tokens() -> None:
    rendered = render_filename("{stem}_{index:03d}.{ext}", stem="clip", index=7, ext="txt")
    assert rendered == "clip_007.txt"


@pytest.mark.unit
def test_render_filename_template_error_includes_what_why_fix() -> None:
    with pytest.raises(ValueError, match="what: missing template token 'ext'.*why: template requires it.*how-to-fix"):
        render_filename("{stem}.{ext}", stem="clip")
