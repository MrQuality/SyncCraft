"""Media validation and deterministic metadata extraction utilities."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Protocol

from synccraft.errors import format_user_error

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_AUDIO_EXTENSIONS = {".wav"}


class AudioDurationExtractor(Protocol):
    """Abstraction for audio duration metadata extraction."""

    def duration_seconds(self, audio_path: str | Path) -> int:
        """Return rounded-down audio duration in seconds."""


class WaveDurationExtractor:
    """Duration extractor implementation for PCM WAV containers."""

    def duration_seconds(self, audio_path: str | Path) -> int:
        """Extract WAV duration in full seconds."""
        path = Path(audio_path)
        try:
            with wave.open(str(path), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                if frame_rate <= 0:
                    raise ValueError(
                        format_user_error(
                            what=f"unsupported WAV file with non-positive frame rate: {path}",
                            why="duration calculation requires a positive frame rate",
                            how_to_fix="re-encode the audio as a valid PCM WAV file",
                        )
                    )
                return int(wav_file.getnframes() / frame_rate)
        except wave.Error as exc:
            raise ValueError(
                format_user_error(
                    what=f"unsupported or invalid WAV file: {path}",
                    why=str(exc),
                    how_to_fix="provide a valid .wav file containing fmt and data chunks",
                )
            ) from exc


def validate_media_path(*, value: str, field_name: str, allowed_extensions: set[str]) -> None:
    """Validate media path existence and deterministic extension checks."""
    path = Path(value)
    if not path.exists():
        raise ValueError(
            format_user_error(
                what=f"{field_name} not found: {value}",
                why="the provided path does not exist",
                how_to_fix=f"provide an existing file path for {field_name}",
            )
        )
    if not path.is_file():
        raise ValueError(
            format_user_error(
                what=f"{field_name} must reference a file: {value}",
                why="directories cannot be processed as media inputs",
                how_to_fix=f"point {field_name} to a media file",
            )
        )

    extension = path.suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(
            format_user_error(
                what=f"unsupported {field_name} format '{extension or '<none>'}'.",
                why="SyncCraft validates media formats before execution",
                how_to_fix=f"use one of the supported extensions: {allowed}",
            )
        )


def validate_image_path(image_path: str) -> None:
    """Validate image path and extension."""
    validate_media_path(value=image_path, field_name="image", allowed_extensions=_IMAGE_EXTENSIONS)


def validate_audio_path(audio_path: str) -> None:
    """Validate audio path and extension."""
    validate_media_path(value=audio_path, field_name="audio", allowed_extensions=_AUDIO_EXTENSIONS)

