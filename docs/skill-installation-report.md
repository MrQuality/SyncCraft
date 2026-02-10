# SyncCraft Skill Installation Report

This report documents skill discovery, matching, and installation for SyncCraft.

## Sources searched

1. `openai/skills` curated registry (via `list-curated-skills.py`).
2. Community collection: `jMerta/codex-skills`.
3. Community collection: `ComposioHQ/awesome-codex-skills` (evaluated for candidates).
4. Community collection: `Dimillian/Skills` (evaluated for candidates).

## Installed skills and role mapping

| Requested role / intent | Installed skill | Source | Why this match |
|---|---|---|---|
| Solution Architect | `plan-work` | `jMerta/codex-skills` | Focuses on planning, architecture options, risk analysis, and scoping before implementation. |
| QA Engineer | `coding-guidelines-verify` | `jMerta/codex-skills` | Runs formatting/lint/tests and checks scoped compliance for changed files. |
| Security Best Practices | `security-best-practices` | `openai/skills` curated | Exact match by name and purpose. |
| Release Manager | `release-notes` | `jMerta/codex-skills` | Generates structured release notes/changelog content, including breaking changes and upgrades. |
| CLI UX Reviewer | `create-cli` | `jMerta/codex-skills` | Reviews CLI flags, help text, output/error conventions, exit codes, and UX consistency. |
| README Consistency Checker | `docs-sync` | `jMerta/codex-skills` | Keeps README/docs aligned with actual behavior and code changes. |
| Edge Case Enumerator (closest) | `bug-triage` | `jMerta/codex-skills` | Emphasizes repro/isolation and verification workflows that surface edge behavior while debugging. |

## Installed supporting security skills

These were added because they are curated and strengthen the requested quality/security posture:

- `security-threat-model` (openai curated)
- `security-ownership-map` (openai curated)

## Requested skills with no strong public match found

- Provider Interface Auditor
- Config Schema Validator
- Golden Path Test Generator
- Secret Leakage Scanner
- Backward Compatibility Checker

Reason: no direct or high-confidence equivalent was found in the curated `openai/skills` set or the reviewed community collections at install time; nearest alternatives were either too generic or outside the requested responsibility boundaries.

## Post-install note

Restart Codex to pick up newly installed skills.
