"""Filename templating utilities."""

from __future__ import annotations

from synccraft.errors import format_user_error



def render_filename(template: str, **values: object) -> str:
    """Render an output filename template with strict token requirements."""
    try:
        return template.format(**values)
    except KeyError as exc:
        missing = str(exc).strip("\"'")
        raise ValueError(
            format_user_error(
                what=f"missing template token '{missing}'.",
                why="template requires it to render a valid filename",
                how_to_fix=f"pass '{missing}' or remove that token from the template",
            )
        ) from exc
