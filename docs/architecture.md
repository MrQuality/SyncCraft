# SyncCraft Architecture Note

## Purpose and scope

This document defines the target module boundaries and core interfaces for SyncCraft's transcription pipeline. It separates provider-agnostic logic from provider-specific integrations so that new provider versions can be added without changing the CLI contract.

## High-level module map

### `cli`

**Responsibility**
- Parse command-line arguments.
- Resolve command orchestration for a single run.
- Construct a `RunContext` using resolved configuration and filesystem paths.
- Invoke `pipeline` and convert raised errors into user-facing exit codes.

**Owns**
- Argument schema and defaults exposed to users.
- Mapping from CLI args to configuration overrides.

**Does not own**
- Provider API details.
- Chunk planning rules.
- Output naming algorithms.

### `config`

**Responsibility**
- Load YAML configuration files.
- Validate schema-compatible keys and value types.
- Resolve deterministic precedence:
  1. built-in defaults,
  2. config file,
  3. CLI overrides.

**Owns**
- Config parsing/merging.
- Creation of a normalized settings object consumed by `RunContext`.

**Does not own**
- Runtime execution of providers.
- Media-domain validation.

### `domain`

**Responsibility**
- Provider-agnostic business rules for transcript runs.
- Input validation (paths, durations, chunk constraints).
- Chunk planning and policy enforcement.
- Output naming strategies independent of any provider SDK.

**Owns**
- `AudioChunkPlan` and `ChunkPolicy` types.
- Validation and deterministic naming conventions.

**Does not own**
- HTTP/API calls.
- CLI parsing.

### `providers`

**Responsibility**
- Define provider contract and capability model.
- Host concrete implementations (`omni` today).
- Translate provider-specific request/response models to domain-neutral results.

**Owns**
- `ProviderClient` interface.
- Provider limits/capabilities declarations.
- Error mapping from SDK/network errors to SyncCraft error types.

**Does not own**
- CLI argument parsing.
- Cross-provider orchestration policies.

### `pipeline`

**Responsibility**
- End-to-end execution flow from validated context to persisted outputs.
- Coordinate modules in order: config/domain/providers/output.
- Enforce run lifecycle (plan chunks, invoke provider, aggregate, write results).

**Owns**
- Sequencing and orchestration.
- Cross-cutting telemetry points (timings, counters, phase transitions).

**Does not own**
- Provider protocol internals.
- CLI interface shape.

### `logging`

**Responsibility**
- Structured log schema and levels.
- Correlation IDs and run-scoped metadata injection.
- Redaction rules for sensitive values.

### `errors`

**Responsibility**
- Typed error taxonomy shared across modules.
- User-safe error rendering for CLI.
- Mapping of internal exceptions to actionable `what/why/how-to-fix` output.

## Core interface definitions

## `ProviderClient` contract

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_streaming: bool
    supports_timestamps: bool
    supports_language_hint: bool


@dataclass(frozen=True)
class ProviderLimits:
    max_file_bytes: int
    max_chunk_seconds: int
    requests_per_minute: int | None


@dataclass(frozen=True)
class GenerationRequest:
    audio_path: Path
    language: str | None
    prompt: str | None


@dataclass(frozen=True)
class GenerationResult:
    transcript: str
    confidence: float | None
    raw_provider_payload: dict


class ProviderClient(Protocol):
    @property
    def capabilities(self) -> ProviderCapabilities: ...

    @property
    def limits(self) -> ProviderLimits: ...

    def generate(self, request: GenerationRequest) -> GenerationResult: ...
```

**Contract notes**
- `capabilities` describes optional features used by `pipeline` for behavior gating.
- `limits` enables pre-flight domain checks before provider calls.
- `generate` is the single provider execution entrypoint and returns a provider-neutral result.

## `AudioChunkPlan` and `ChunkPolicy`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPolicy:
    target_chunk_seconds: int
    min_chunk_seconds: int
    max_chunk_seconds: int
    allow_single_chunk_fallback: bool


@dataclass(frozen=True)
class AudioChunk:
    index: int
    start_seconds: int
    end_seconds: int


@dataclass(frozen=True)
class AudioChunkPlan:
    total_seconds: int
    policy: ChunkPolicy
    chunks: list[AudioChunk]
```

**Design intent**
- `ChunkPolicy` is configuration input; `AudioChunkPlan` is validated runtime output.
- Planning belongs in `domain` and is independent from `providers`.

## `RunContext`

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunContext:
    run_id: str
    input_audio_path: Path
    output_dir: Path
    output_file_path: Path
    resolved_settings: dict
    chunk_policy: ChunkPolicy
    provider_name: str
```

**Design intent**
- Built once at the boundary between `cli/config` and `pipeline`.
- Carries fully resolved settings and normalized paths so downstream modules remain deterministic.

## Provider-agnostic vs provider-specific responsibilities

## Provider-agnostic (`cli`, `config`, `domain`, `pipeline`, `logging`, `errors`)
- Argument schema and precedence resolution.
- Validation rules (path existence, chunk bounds, naming format).
- Chunk creation and transcript aggregation policy.
- Output naming and persistence strategy.
- Error taxonomy and user-facing formatting.

## Provider-specific (`providers/*`)
- SDK/client initialization.
- Authentication and endpoint handling.
- Request shaping and retry/backoff tuned to provider limits.
- Response normalization into `GenerationResult`.

**Rule:** provider-specific code must not leak SDK types outside `providers`.

## Dependency and layering rules

Allowed dependency direction:

1. `cli` -> `config`, `pipeline`, `logging`, `errors`
2. `pipeline` -> `domain`, `providers`, `logging`, `errors`
3. `providers` -> `errors` (and internal provider helpers)
4. `domain` -> `errors`
5. `config` -> `errors`

Prohibited dependencies:
- `domain` -> `cli`
- `providers` -> `cli`
- `domain` <-> `providers` cyclic imports
- Any module importing `pipeline` except `cli` and tests

This prevents circular dependencies between `cli`, `domain`, and `providers`.

## Extensibility path: provider v2+ without CLI contract changes

1. Keep CLI provider selection stable (for example, `--provider omni`).
2. Add a new implementation under `providers/omni_v2.py` implementing `ProviderClient`.
3. Register versioned implementation in a provider registry/factory inside `providers`.
4. Choose implementation via config/env/internal feature flag, not new CLI shape.
5. Ensure both versions emit identical `GenerationResult` semantics.
6. Add contract tests that run shared provider test vectors against v1 and v2.

Outcome: new provider versions can be shipped with zero user-facing CLI argument changes.

## Verification checklist (architecture gate)

- [ ] Architecture doc reviewed and approved before first implementation branch.
- [ ] Every new module maps to one documented responsibility above.
- [ ] Dependency checks confirm no circular dependencies between `cli`, `domain`, `providers`.

## Future provider extension guide (current codebase)

The current repository keeps provider integration in `synccraft/provider.py` and wires adapters through `build_provider_adapter(config=...)`. To add another provider safely:

1. Add a new adapter class implementing the `ProviderAdapter` protocol (`limits` and `generate`).
2. Keep provider-specific authentication/request shaping inside the adapter; return provider-neutral fields (at minimum `transcript`).
3. Register the new provider string in `build_provider_adapter` and keep existing provider keys backward compatible.
4. Map provider failures to `format_user_error(...)` triads so CLI output remains actionable.
5. Extend `tests/contract/test_provider_adapter.py` for the shared adapter contract and add integration tests that execute the CLI with the new provider config path.

Suggested implementation skeleton:

```python
class NewProviderAdapter:
    def limits(self) -> ProviderLimits:
        return ProviderLimits(max_audio_seconds=...)

    def generate(self, *, image: str | Path, audio_chunk: str | Path, params: dict[str, Any] | None = None, chunk: ChunkMetadata | None = None) -> dict[str, Any]:
        ...  # provider SDK/API call
        return {
            "request_id": "...",
            "transcript": "...",
            "params": params or {},
            "chunk_index": chunk.index if chunk else None,
        }
```

