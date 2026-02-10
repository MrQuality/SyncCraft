# SyncCraft Tutorial: From Zero to First Transcript

This tutorial walks through the full setup and first run of SyncCraft using both supported providers:

- `mock` provider (local JSON fixture; easiest way to validate your environment)
- `omni` provider (parameterized provider adapter for real API-backed integrations)

If you are brand new to the project, follow this in order.

## 1) Prerequisites

- Python 3.11 or newer
- `pip` available in your shell
- A checkout of this repository

Verify your Python version:

```bash
python --version
```

## 2) Install SyncCraft

### Option A (recommended for contributors): editable install

```bash
python -m pip install -e .
```

### Option B (with developer tooling)

```bash
python -m pip install -e .[dev]
```

Validate that the CLI is installed:

```bash
synccraft --version
```

## 3) Understand the runtime inputs

Every SyncCraft run needs:

1. **Image path** (first positional argument)
2. **Audio path** (second positional argument)
3. **Config YAML** passed with `--config`

Config sections are:

- `input`
- `audio`
- `output`
- `provider`

## 4) Quick success path with the `mock` provider

Use the repository fixtures to verify end-to-end behavior without any external API account.

Create a config file:

```bash
cat > /tmp/synccraft.mock.yaml <<'YAML'
input: {}
audio: {}
output:
  directory: /tmp
  filename_template: "quickstart_{index:03d}.txt"
provider:
  name: mock
YAML
```

Run SyncCraft:

```bash
synccraft \
  tests/fixtures/image/sample.png \
  tests/fixtures/audio/tone.wav \
  --config /tmp/synccraft.mock.yaml
```

Expected outcome:

- progress/status logs in your terminal
- transcript output written under `/tmp`

## 5) Configure output naming

You can control file names using `output.filename_template`.

Supported placeholders are:

- `{stem}`
- `{index}`
- `{ext}`
- `{chunk_start}`
- `{chunk_end}`

Example:

```yaml
output:
  directory: ./out
  filename_template: "{stem}_{chunk_start}_{chunk_end}_{index:03d}.{ext}"
```

## 6) Process long audio with chunking

When provider limits require shorter clips, configure chunking:

```yaml
audio:
  chunk_seconds: 30
  on_chunk_failure: continue
```

`on_chunk_failure` options:

- `stop` (default): fail immediately on first chunk error
- `continue`: keep processing remaining chunks

## 7) Use the `omni` provider

The `omni` provider passes provider parameters through the adapter.

Create a config:

```bash
cat > /tmp/synccraft.omni.yaml <<'YAML'
input: {}
audio:
  chunk_seconds: 45
output:
  directory: /tmp
  filename_template: "omni_{index:03d}.txt"
provider:
  name: omni
  api_key: "${SYNC_PROVIDER_API_KEY}"
  endpoint: "${SYNC_PROVIDER_ENDPOINT}"
YAML
```

Export environment variables before running:

```bash
export SYNC_PROVIDER_API_KEY='replace-me'
export SYNC_PROVIDER_ENDPOINT='https://api.your-provider.example/v1'
```

Then run:

```bash
synccraft \
  tests/fixtures/image/sample.png \
  tests/fixtures/audio/tone.wav \
  --config /tmp/synccraft.omni.yaml
```

> For API key lifecycle guidance (where to get keys, rotation, and safe storage), see [`docs/api-keys.md`](./api-keys.md).

## 8) Useful CLI flags

- `--verbose`: enable INFO logging
- `--debug`: enable DEBUG logging (includes sanitized request/response payload logs)
- `--dry-run`: validate and print a summary without performing provider generation
- `--version`: print version and exit

Examples:

```bash
synccraft tests/fixtures/image/sample.png tests/fixtures/audio/tone.wav --config /tmp/synccraft.mock.yaml --dry-run
synccraft tests/fixtures/image/sample.png tests/fixtures/audio/tone.wav --config /tmp/synccraft.mock.yaml --debug
```

## 9) Troubleshooting checklist

If a run fails:

1. Confirm the config shape includes only supported sections (`input`, `audio`, `output`, `provider`).
2. Confirm file paths exist and are readable.
3. Re-run with `--debug` to inspect sanitized execution details.
4. Validate dependencies are installed in the current Python environment.

Common fix:

```bash
python -m pip install -e .[dev]
```

## 10) Next steps

- Explore `docs/config.examples.yaml` for additional patterns.
- Read [`docs/architecture.md`](./architecture.md) to understand module boundaries.
- Follow `CONTRIBUTING.md` for test-first contribution workflow.
