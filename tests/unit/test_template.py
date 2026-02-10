"""Unit tests for filename templating."""

import pytest

from synccraft.templating import render_filename


@pytest.mark.unit
def test_render_filename_template_replaces_tokens() -> None:
    rendered = render_filename("{audio_basename}_{index:03d}_{start}_{end}.txt", audio_basename="clip", index=7, start=10, end=20)
    assert rendered == "clip_007_10_20.txt"


@pytest.mark.unit
def test_render_filename_template_error_includes_what_why_fix() -> None:
    with pytest.raises(ValueError, match="what: missing template token 'end'.*why: template requires it.*how-to-fix"):
        render_filename("{audio_basename}_{end}.txt", audio_basename="clip")


@pytest.mark.unit
def test_render_filename_supports_each_required_placeholder() -> None:
    rendered = render_filename("{index}-{start}-{end}-{audio_basename}", index=0, start=5, end=9, audio_basename="track")
    assert rendered == "0-5-9-track"
