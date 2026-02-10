# SyncCraft

SyncCraft is a lightweight Python CLI foundation for media-transcript workflows with strict test-first quality gates.

## What this repository includes

- **Core behavior modules**
  - Config merge logic (`synccraft.config`)
  - Filename templating (`synccraft.templating`)
  - Chunk planning (`synccraft.chunking`)
  - Provider adapter contract checks (`synccraft.provider`)
  - Output writing (`synccraft.output`)
  - Structured user-facing errors (`synccraft.errors`)
  - CLI entrypoint (`synccraft.cli`)

- **Test layers**
  - Unit tests (`tests/unit`)
  - Integration tests (`tests/integration`)
  - Contract tests (`tests/contract`)

- **Quality and governance**
  - CI test gates in `.github/workflows/`
  - Behavior-change test enforcement script: `scripts/check_changed_behavior_has_tests.py`
  - Contributor policy in `CONTRIBUTING.md`

## Development setup

### Prerequisites

- Python 3.11+

### Install

```bash
python -m pip install -e .[dev]
```

## Running tests

### Full suite + coverage threshold

```bash
python -m pytest
```

### Fast unit suite (PR mandatory)

```bash
python -m pytest -m unit --no-cov
```

### Integration suite (release mandatory)

```bash
python -m pytest -m integration --no-cov
```

### Contract suite

```bash
python -m pytest -m contract --no-cov
```

### Behavior-change gate

```bash
python scripts/check_changed_behavior_has_tests.py origin/main
```

## Troubleshooting: missing `pytest-cov`

If `pytest` fails with coverage-related argument or plugin errors (for example around `--cov`), install dev dependencies so `pytest-cov` is available:

```bash
python -m pip install -e .[dev]
```

You can verify plugin availability with:

```bash
python -m pytest --help | rg -- --cov
```

## CLI usage

```bash
python -m synccraft.cli \
  tests/fixtures/image/sample.png \
  tests/fixtures/audio/tone.wav \
  --config ./config.yaml
```

Supported flags:

- `--verbose` (INFO logging)
- `--debug` (DEBUG logging; overrides verbose)
- `--dry-run` (validate + print summary, no provider call)
- `--version` (print version and exit immediately)


## Config examples

Example YAML configurations are provided in `docs/config.examples.yaml` for:

- minimal setup
- chunked mode
- env-var-friendly production deployment

## Error contract

User-facing failures should be actionable and include:

- `what:` what failed
- `why:` why it failed
- `how-to-fix:` what to do next

## Red → Green → Refactor policy

Every behavior change should follow:

1. **Red**: add a failing test
2. **Green**: add the minimum implementation to pass
3. **Refactor**: improve design while keeping tests green

A feature PR should show test-first commit sequencing (`test:` before `feat:`).
