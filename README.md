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

## CLI usage

```bash
python -m synccraft.cli \
  --audio tests/fixtures/audio/tone.wav \
  --provider-payload tests/fixtures/provider/success.json \
  --output ./out/transcript.txt
```

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
