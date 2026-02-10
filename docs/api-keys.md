# API Keys and Provider Credential Guide

This document explains how to obtain, store, rotate, and use API keys safely with SyncCraft.

## Important context

SyncCraft currently supports two provider adapters:

- `mock`: local fixture-based provider; **no API key required**
- `omni`: general adapter for API-backed workflows; key usage depends on your selected external provider

Because `omni` is adapter-oriented, SyncCraft does not hardcode one provider's signup flow. Instead, use this guide for a secure process that works with most commercial AI/transcription APIs.

## 1) How to obtain API keys

For most API providers, you will follow a similar process:

1. Create or sign into your provider account.
2. Open the provider's **Developer**, **API**, or **Credentials** section.
3. Create a new API key scoped to least privilege (for example, transcription-only).
4. Save the key once; many providers only show it at creation time.
5. If needed, create a dedicated project/workspace key for SyncCraft workloads.

## 2) Store keys securely

Preferred order:

1. Secret manager (production): AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Vault, etc.
2. CI/CD encrypted secrets (automation).
3. Local environment variables (development).

Avoid:

- Hardcoding keys in YAML committed to Git
- Sharing keys in issues, PRs, chat logs, or screenshots
- Reusing personal root keys across multiple applications

## 3) Local development pattern (recommended)

Set environment variables:

```bash
export SYNC_PROVIDER_API_KEY='your-real-key'
export SYNC_PROVIDER_ENDPOINT='https://api.your-provider.example/v1'
```

Use references in config:

```yaml
provider:
  name: omni
  api_key: "${SYNC_PROVIDER_API_KEY}"
  endpoint: "${SYNC_PROVIDER_ENDPOINT}"
```

Then run SyncCraft with your normal command.

## 4) Rotation and revocation policy

Use a predictable key hygiene workflow:

- Rotate keys on a schedule (for example, every 60-90 days)
- Immediately rotate if exposed or suspected leaked
- Revoke old keys once new deployments are healthy
- Prefer one key per environment (`dev`, `staging`, `prod`) for blast-radius control

## 5) Validating key configuration

Before production use:

1. Run with `--dry-run` to validate general configuration shape.
2. Run a low-cost real request in a non-production environment.
3. Confirm logs do not expose secrets.

SyncCraft sanitizes key/token/password-like fields in debug payload logs, but you should still treat logs as sensitive operational data.

## 6) CI/CD usage example

In CI pipelines:

- Store provider secrets in platform-managed encrypted variables.
- Inject them into environment variables at runtime.
- Build temporary config files during job execution.
- Delete temporary files after use.

Example runtime rendering snippet:

```bash
cat > /tmp/synccraft.ci.yaml <<'YAML'
input: {}
audio: {}
output:
  directory: /tmp
  filename_template: "ci_{index:03d}.txt"
provider:
  name: omni
  api_key: "${SYNC_PROVIDER_API_KEY}"
  endpoint: "${SYNC_PROVIDER_ENDPOINT}"
YAML
```

## 7) Incident response if a key leaks

1. Revoke/disable the leaked key in provider console.
2. Create a replacement key.
3. Update all deployment targets with the new secret.
4. Audit logs/usage to detect abuse.
5. Document the incident and harden controls (scoping, vault policy, secret scanning).

## 8) Provider onboarding checklist

When onboarding any new API provider with the `omni` adapter:

- [ ] Dedicated service account created
- [ ] Least-privilege API key generated
- [ ] Non-production test key separated from production key
- [ ] Endpoint and model parameters documented internally
- [ ] Cost and rate-limit alerts enabled
- [ ] Rotation owner assigned
