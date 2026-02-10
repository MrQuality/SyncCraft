# Installation and Runtime Dependencies

This document defines the packaging/install workflow for `synccraft` and runtime dependency policy.

## Install from PyPI-style package artifacts

Once a wheel (`.whl`) or source distribution (`.tar.gz`) is built and published, install with:

```bash
python -m pip install synccraft
```

Validate installation:

```bash
synccraft --version
```

## Install from local build artifacts

Build artifacts locally:

```bash
python -m pip install --upgrade build
python -m build
```

Install from the built wheel:

```bash
python -m pip install dist/*.whl
synccraft --version
```

Install from the built sdist:

```bash
python -m pip install dist/*.tar.gz
synccraft --version
```

## Runtime dependencies

Required runtime dependencies are declared in `pyproject.toml` and installed automatically by `pip`.

Current runtime dependencies:

- `PyYAML>=6.0`

Python version requirement:

- Python `>=3.11`

## FFmpeg policy

SyncCraft does **not** bundle FFmpeg in wheels or standalone binaries.

- Current audio validation/extraction supports WAV-only workflows and does not require FFmpeg for the shipped CLI behavior.
- If future workflows add FFmpeg-backed transcoding/probing, users must install FFmpeg separately via their OS package manager (for example `apt`, `brew`, or `choco`) and ensure `ffmpeg`/`ffprobe` are available on `PATH`.

Rationale: keeping FFmpeg external avoids license/binary-size complications and keeps package artifacts lightweight.
