# Contributing to SyncCraft

Thanks for contributing to SyncCraft. This repository uses a lightweight GitFlow-style workflow to keep production code stable while enabling rapid iteration.

## Branch Model

Use the following branch types:

- `main`: production-ready code only.
- `develop`: integration branch for the upcoming release.
- `feature/<scope>`: implementation branches cut from `develop`.
- `release/<version>`: release hardening, docs updates, and version bump.
- `hotfix/<version>`: urgent production fixes cut from `main`.

### Branch Naming Examples

- `feature/cli-entrypoint`
- `feature/config-loader`
- `feature/provider-omni`

## Merge Rules

- Feature branches merge into `develop` via pull request.
- Release branches are cut from `develop`, then merged into `main` and back into `develop`.
- Hotfix branches are cut from `main`, then merged into both `main` and `develop`.

## Release Flow (Reproducible)

Follow these steps for every release:

1. Ensure `develop` is green and up to date.
2. Create a release branch:
   - `git checkout develop`
   - `git pull --ff-only`
   - `git checkout -b release/<version>`
3. Perform release hardening:
   - finalize docs
   - bump version
   - run full test suite
4. Open a PR from `release/<version>` into `main`.
5. After merge to `main`, create a back-merge PR from `main` into `develop` (or merge `release/<version>` into `develop` if your host allows dual-target flow).
6. Tag the release from `main`.

## Hotfix Flow (Reproducible)

1. Create hotfix branch from production:
   - `git checkout main`
   - `git pull --ff-only`
   - `git checkout -b hotfix/<version>`
2. Implement fix + tests.
3. Open PR into `main`.
4. After merge to `main`, merge the same hotfix into `develop`.
5. Tag patch release from `main`.

## Pull Request Checklist

Every PR must satisfy all items before review:

- [ ] Tests added first or updated.
- [ ] All tests passing.
- [ ] Documentation updated.
- [ ] No secrets committed.

## Sample Feature PR (Naming + Checklist)

**Branch:** `feature/config-loader`

**Title:** `feat: add config loader defaults and validation`

**Description:**

- Adds a config loader with environment fallback.
- Includes tests for missing and malformed config values.
- Updates usage docs.

**Checklist**

- [x] Tests added first or updated.
- [x] All tests passing.
- [x] Documentation updated.
- [x] No secrets committed.

## Semantic Commit Convention

Use these commit prefixes:

- `feat:` for new user-facing functionality
- `fix:` for bug fixes
- `test:` for test additions or updates
- `docs:` for documentation changes
- `refactor:` for code restructuring without behavior change
- `chore:` for maintenance tasks

Examples:

- `feat: add provider selection for sync jobs`
- `fix: handle missing config path on startup`
- `docs: document release and hotfix branching model`
