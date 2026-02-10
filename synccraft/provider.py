"""Provider adapter implementations and contracts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from synccraft.errors import format_user_error

if TYPE_CHECKING:
    from synccraft.chunking import ChunkMetadata


@dataclass(frozen=True)
class ProviderLimits:
    """Declared provider limits used for preflight validation."""

    max_audio_seconds: int | None = None


class ProviderAdapter(Protocol):
    """Contract implemented by all transcription providers."""

    def limits(self) -> ProviderLimits:
        """Return provider execution limits."""

    def generate(
        self,
        *,
        image: str | Path,
        audio_chunk: str | Path,
        params: dict[str, Any] | None = None,
        chunk: ChunkMetadata | None = None,
    ) -> dict[str, Any]:
        """Generate provider response for an image+audio chunk request."""


class OmniProviderAdapter:
    """Default provider adapter that forwards params without provider-specific hardcoding."""

    def __init__(
        self,
        *,
        default_params: dict[str, Any] | None = None,
        limits: ProviderLimits | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.default_params = dict(default_params or {})
        self._limits = limits or ProviderLimits()
        self._logger = logger or logging.getLogger(__name__)

    def limits(self) -> ProviderLimits:
        """Return static limits for the omni adapter."""
        return self._limits

    def generate(
        self,
        *,
        image: str | Path,
        audio_chunk: str | Path,
        params: dict[str, Any] | None = None,
        chunk: ChunkMetadata | None = None,
    ) -> dict[str, Any]:
        """Return a deterministic response while preserving call-time params."""
        merged_params = {**self.default_params, **(params or {})}
        request = {
            "request_id": str(merged_params.get("request_id") or "omni-request"),
            "image": str(image),
            "audio_chunk": str(audio_chunk),
            "params": merged_params,
        }
        self._debug_log_request_response(request=request, response={"request_id": request["request_id"]})

        return {
            "request_id": request["request_id"],
            "transcript": str(merged_params.get("transcript", "omni transcript")),
            "params": merged_params,
            "chunk_index": chunk.index if chunk is not None else None,
        }

    def sanitize_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Sanitize request payload for debug logs."""
        return _sanitize_payload(payload)

    def sanitize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Sanitize response payload for debug logs."""
        return _sanitize_payload(payload)

    def _debug_log_request_response(self, *, request: dict[str, Any], response: dict[str, Any]) -> None:
        """Log sanitized request/response payloads at debug level."""
        self._logger.debug("Omni request: %s", self.sanitize_request(request))
        self._logger.debug("Omni response: %s", self.sanitize_response(response))


class MockProviderAdapter:
    """Test-friendly provider adapter backed by a local JSON payload."""

    def __init__(self, *, payload_file: str | Path) -> None:
        self.payload_file = Path(payload_file)

    def limits(self) -> ProviderLimits:
        """Return provider-side limits from fixture payload."""
        return ProviderLimits(max_audio_seconds=self.get_max_audio_seconds())

    def generate(
        self,
        *,
        image: str | Path,
        audio_chunk: str | Path,
        params: dict[str, Any] | None = None,
        chunk: ChunkMetadata | None = None,
    ) -> dict[str, Any]:
        """Generate transcript data from fixture payload while validating contract."""
        _ = image
        _ = params
        return self.transcribe(audio_path=audio_chunk, chunk=chunk)

    def transcribe(self, *, audio_path: str | Path, chunk: ChunkMetadata | None = None) -> dict[str, Any]:
        """Return transcript data from fixture payload while validating contract.

        The optional ``chunk`` parameter enables deterministic failure simulation
        and chunk-specific transcript values for integration tests.
        """
        path = Path(audio_path)
        if not path.exists():
            raise ValueError(
                format_user_error(
                    what=f"audio file not found: {path}",
                    why="CLI was given a path that does not exist",
                    how_to_fix="provide an existing audio path under tests/fixtures/audio or your media directory",
                )
            )

        data = self._load_payload()
        result = dict(data)

        if chunk is not None:
            if chunk.index in self._failed_chunk_indices(data):
                raise ValueError(
                    format_user_error(
                        what=f"provider failed for chunk index {chunk.index}.",
                        why="mock payload requested a deterministic chunk failure",
                        how_to_fix="remove this index from fail_on_chunk_indices or change failure policy",
                    )
                )

            chunk_transcripts = data.get("chunk_transcripts")
            if isinstance(chunk_transcripts, dict):
                candidate = chunk_transcripts.get(str(chunk.index))
                if isinstance(candidate, str):
                    result["transcript"] = candidate

        if "transcript" not in result:
            raise ValueError(
                format_user_error(
                    what="provider response missing 'transcript'.",
                    why="adapter contract requires a transcript field",
                    how_to_fix="ensure provider response JSON includes a non-empty transcript value",
                )
            )
        return result

    def get_max_audio_seconds(self) -> int | None:
        """Return provider-side max duration limit when declared in payload."""
        if not self.payload_file.exists():
            return None
        data = json.loads(self.payload_file.read_text(encoding="utf-8"))
        limit = data.get("max_audio_seconds")
        if isinstance(limit, int) and limit > 0:
            return limit
        return None

    def validate_chunking_payload_schema(self) -> None:
        """Validate chunk-related mock payload keys before execution."""
        data = self._load_payload()

        fail_on_chunk_indices = data.get("fail_on_chunk_indices")
        if fail_on_chunk_indices is not None:
            if not isinstance(fail_on_chunk_indices, list):
                raise ValueError(
                    format_user_error(
                        what="provider.fail_on_chunk_indices must be a list of non-negative integers.",
                        why="chunk failure simulation requires explicit chunk indices",
                        how_to_fix="set fail_on_chunk_indices like [0, 2] or remove it",
                    )
                )
            if any(not isinstance(value, int) or value < 0 for value in fail_on_chunk_indices):
                raise ValueError(
                    format_user_error(
                        what="provider.fail_on_chunk_indices contains invalid values.",
                        why="all chunk indices must be non-negative integers",
                        how_to_fix="use only integer indices >= 0, for example [1, 3]",
                    )
                )

        chunk_transcripts = data.get("chunk_transcripts")
        if chunk_transcripts is not None:
            if not isinstance(chunk_transcripts, dict):
                raise ValueError(
                    format_user_error(
                        what="provider.chunk_transcripts must be a mapping of chunk index to transcript.",
                        why="chunk-specific transcript overrides require key/value pairs",
                        how_to_fix="set chunk_transcripts like {'0': 'intro', '1': 'middle'} or remove it",
                    )
                )

            for key, value in chunk_transcripts.items():
                if not isinstance(key, str) or not key.isdigit():
                    raise ValueError(
                        format_user_error(
                            what="provider.chunk_transcripts contains an invalid key.",
                            why="chunk transcript keys must be numeric strings like '0' or '2'",
                            how_to_fix="replace keys with numeric strings only",
                        )
                    )
                if not isinstance(value, str):
                    raise ValueError(
                        format_user_error(
                            what=f"provider.chunk_transcripts['{key}'] must be a string transcript.",
                            why="chunk transcript overrides require text values",
                            how_to_fix="set each chunk_transcripts value to a string",
                        )
                    )

    def _load_payload(self) -> dict[str, Any]:
        """Load payload JSON and enforce basic file and shape invariants."""
        if not self.payload_file.exists():
            raise ValueError(
                format_user_error(
                    what=f"provider payload file not found: {self.payload_file}",
                    why="adapter expects a JSON payload file",
                    how_to_fix="create a JSON fixture with transcript/confidence fields and pass its path",
                )
            )

        data = json.loads(self.payload_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(
                format_user_error(
                    what="provider payload must be a JSON object.",
                    why="the adapter expects named fields like transcript and max_audio_seconds",
                    how_to_fix="use JSON object syntax, for example {'transcript': '...'}",
                )
            )
        return data

    @staticmethod
    def _failed_chunk_indices(data: dict[str, Any]) -> set[int]:
        """Parse configured chunk failure indices from payload fixtures."""
        raw = data.get("fail_on_chunk_indices")
        if not isinstance(raw, list):
            return set()

        parsed: set[int] = set()
        for value in raw:
            if isinstance(value, int) and value >= 0:
                parsed.add(value)
        return parsed


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets from structured payloads while preserving debug identifiers."""

    def _sanitize(value: Any, key_hint: str | None = None) -> Any:
        if isinstance(value, dict):
            return {k: _sanitize(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [_sanitize(item, key_hint) for item in value]
        if key_hint and any(token in key_hint.lower() for token in {"secret", "token", "key", "password"}):
            return "***REDACTED***"
        return value

    return {k: _sanitize(v, k) for k, v in payload.items()}


def build_provider_adapter(*, config: dict[str, Any]) -> ProviderAdapter:
    """Construct a provider adapter from CLI config."""
    provider_name = str(config.get("provider", "omni")).strip().lower()

    if provider_name == "omni":
        raw_default_params = config.get("provider_params")
        default_params = raw_default_params if isinstance(raw_default_params, dict) else {}

        max_audio_seconds: int | None = None
        raw_limits = config.get("provider_limits")
        if isinstance(raw_limits, dict):
            candidate = raw_limits.get("max_audio_seconds")
            if isinstance(candidate, int) and candidate > 0:
                max_audio_seconds = candidate

        return OmniProviderAdapter(
            default_params=default_params,
            limits=ProviderLimits(max_audio_seconds=max_audio_seconds),
        )

    if provider_name == "mock":
        payload_file = config.get("provider_payload")
        if not payload_file:
            raise ValueError(
                format_user_error(
                    what="missing required config key: provider_payload.",
                    why="mock provider requires a JSON payload fixture",
                    how_to_fix="set provider_payload to an existing JSON file path or use provider: omni",
                )
            )
        return MockProviderAdapter(payload_file=payload_file)

    raise ValueError(
        format_user_error(
            what=f"unsupported provider: {provider_name}.",
            why="SyncCraft only supports configured provider adapters",
            how_to_fix="set provider to one of: omni, mock",
        )
    )
