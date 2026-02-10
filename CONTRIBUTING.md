# Contributing

## Test-First Delivery Cycle

All behavior changes must follow this strict cycle per unit of behavior:

1. **Red**: create a failing test.
2. **Green**: add the smallest implementation needed.
3. **Refactor**: clean internals while keeping tests green.

Feature PR history must demonstrate test-first sequencing, e.g. `test:` commit before `feat:` commit.

## Required Test Layers

- **Unit tests** (`pytest -m unit`): pure logic such as config merge, filename templating, chunk planning.
- **Integration tests** (`pytest -m integration`): CLI invocation and filesystem results.
- **Contract tests** (`pytest -m contract`): provider adapter response contracts.

## Quality Gates

- Fast unit suite is mandatory for every PR.
- Integration suite is mandatory before release branch merges.
- CI fails if behavior files are changed without test updates.

## Fixtures and Mocking Strategy

- Keep lightweight test assets in `tests/fixtures/audio` and `tests/fixtures/image`.
- Keep mock provider payloads in `tests/fixtures/provider`.
- Fixture files must remain smaller than 256 KB.

## Negative-Path Requirements

All user-facing errors must include assertions for:

- `what:` what failed.
- `why:` why it failed.
- `how-to-fix:` immediate remediation.
