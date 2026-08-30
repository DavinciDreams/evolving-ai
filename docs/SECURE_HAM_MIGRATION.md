# Secure HAM migration and deployment runbook

This change is intentionally non-deploying. Production must not be changed until
the containment, credential, and migration gates below are satisfied by an
authorized operator.

## Observed topology and exposure

Read-only checks on 2026-08-14 established this topology:

- `https://www.evolvingai.bio` is the canonical Vercel-hosted Vite frontend.
- `https://evolving-ai-mauve.vercel.app` serves the same frontend. The checked-in
  Vercel configuration now redirects that hostname to the canonical domain while
  preserving the path.
- `/api/*` is rewritten by Vercel to the Coolify backend at
  `https://evolvingai.flobots.xyz/api/*`.
- The legacy Chroma collection is `agent_memory` in the named
  `evolving-ai-memory` volume mounted at `/app/data/memory_db`.
- Before containment, an unauthenticated request to `/api/memories` returned 218
  complete records. A security report identified credential-shaped content in
  that legacy corpus. Do not inspect, print, copy, or publish those values.

## Gate 1: rotate the compromised credential

The reported Tellus credential must be revoked or rotated by an operator with
Tellus administration authority. This repository and its runtime must not be
used as the rotation channel, and the replacement value must not be placed in
GitHub issues, pull requests, HAM memories, logs, or migration artifacts.

Record only the rotation timestamp, responsible authority, and a value-free
confirmation that revocation succeeded. Deployment remains blocked until this
gate is confirmed.

## Gate 2: provision distinct least-privilege credentials

Provision these as separate secrets. The application refuses to start if the
HAM, GitHub, and project-access credentials reuse the same value.

```text
PROJECT_API_KEY       project user access; sent as X-API-Key by the frontend
HAM_API_KEY           HAM service credential bound to katbot-evolving-ai
GITHUB_TOKEN          GitHub self-PR capability only
ZAI_API_KEY           Z AI coding-plan capability only
DISCORD_BOT_TOKEN     Discord bot capability only
```

Create a HAM project with these exact attributes:

```text
slug:  evolving-ai
scope: project:evolving-ai
repo:  DavinciDreams/evolving-ai
agent principal: katbot-evolving-ai
actor type: service
allowed scopes: [project:evolving-ai]
```

Set the backend environment:

```bash
API_AUTH_REQUIRED=true
PROJECT_API_KEY=<separately-managed-project-key>
CORS_ORIGINS=

MEMORY_BACKEND=ham
HAM_API_URL=https://ham.flobots.xyz
HAM_API_KEY=<katbot-service-credential>
HAM_PROJECT=evolving-ai
HAM_SCOPE=project:evolving-ai
HAM_REPO=DavinciDreams/evolving-ai
HAM_EXPECTED_AGENT_ID=katbot-evolving-ai

LEGACY_MEMORY_READ_ONLY=true
MEMORY_PERSIST_DIRECTORY=/app/data/memory_db
MEMORY_COLLECTION_NAME=agent_memory

ZAI_BASE_URL=https://api.z.ai/api/coding/paas/v4
ZAI_MODEL=glm-5.1
DEFAULT_LLM_PROVIDER=zai
DEFAULT_MODEL=glm-5.1

TPMJS_ENABLED=false
```

The frontend holds `PROJECT_API_KEY` only in JavaScript memory after a successful
`GET /status` check. It is not written to local storage or session storage.

Before any mutation the HAM adapter calls `/whoami` and requires the expected
agent, non-admin role, and exactly the project scope above, then validates the
project catalog. Broad/admin or wrong-agent credentials are rejected before a
write. HAM transport must use HTTPS. Identity/credential metadata supplied by
callers is removed; only server-side attribution is authoritative.

## Gate 3: export a redacted, attributable snapshot

Take a consistent, quiesced backup/copy of the legacy volume first, then run the
export against that copy inside the controlled maintenance environment. Chroma's
`PersistentClient` may update internal database metadata on opening; do not point
it at the only original volume or assume the client itself guarantees read-only
access. Preserve the original volume unchanged and mounted read-only.
The export scans content and metadata before persistence. Credential-shaped
values are replaced with detector labels; the quarantine manifest contains only
source IDs, timestamps, detector classes, and one-way hashes.

```bash
python -m scripts.migrate_chroma_to_ham export \
  --persist-directory /app/data/backups/legacy-chroma-copy \
  --snapshot-directory /app/data/backups/chroma-to-ham
```

Expected private artifacts (`0600` permissions):

```text
chroma-memory.jsonl           redacted records with stable source IDs/timestamps
quarantine-manifest.jsonl     value-free attribution for redacted records
manifest.json                 counts, filenames, checksums, detector version
```

Artifacts use atomic, canonical UTF-8 byte writes so checksums agree on Windows
and Linux. On Windows, `0600` does not establish a private ACL: use an
operator-controlled directory with a private Windows ACL. The export fails rather
than silently dropping records if Chroma result arrays differ in length.

Review counts and checksums only. Never paste record content into an operator
terminal, issue, PR, chat, or HAM memory.

## Gate 4: idempotent import and verification

Only after the distinct Katbot HAM credential has been provisioned:

```bash
python -m scripts.migrate_chroma_to_ham import \
  --snapshot-directory /app/data/backups/chroma-to-ham

python -m scripts.migrate_chroma_to_ham verify \
  --snapshot-directory /app/data/backups/chroma-to-ham
```

Each import uses an idempotency key derived from the collection, stable source
ID, and redacted content checksum. Verification checks the mapping's checksum and
complete one-to-one source coverage, then checks **every** imported record's
content checksum and legacy source attribution. Semantic recall is sampled and
reported separately. It also verifies that the server attributed
writes to `katbot-evolving-ai`; callers cannot assert that identity themselves.

Legacy records are `visibility=shared` within `project:evolving-ai`, not globally
public and not agent-private. The application keeps their `audience=project` so
public memory routes do not expose them. Quarantine labels remain attached;
successful transport is not authority to use quarantined content as guidance.

If verification fails, stop. Keep `MEMORY_BACKEND=chroma` only in an isolated
maintenance environment with writes disabled. Do not delete or alter the source
volume.

## Gate 5: mark legacy storage read-only

After verification passes:

```bash
python -m scripts.migrate_chroma_to_ham mark-read-only \
  --snapshot-directory /app/data/backups/chroma-to-ham
```

The command checks that verification is bound to the current snapshot and mapping
before writing an auditable marker; it does not delete data or itself remount a
volume/change deployment configuration. Keep the
`evolving-ai-memory` volume mounted read-only for the rollback window. Rollback
requires an explicit operator decision and must never be triggered automatically.

## Pre-deployment verification

Use test-only credentials and never the reported legacy credential.

```bash
pytest tests/test_ham_memory.py tests/test_chroma_ham_migration.py \
  tests/test_api_routes.py tests/test_discord_integration.py -q

cd frontend
npm ci
npm test
npm run lint
npm run build
npm audit --audit-level=low
```

Direct API expectations:

```text
GET /health                         200 without credentials
GET /memories                      401 without X-API-Key
GET /knowledge                     401 without X-API-Key
GET /github/status                 401 without X-API-Key
GET /public/memories               200; only audience=public records
GET /memories + valid X-API-Key    200
missing server PROJECT_API_KEY     503 for every private route
```

No production deploy, volume mutation, credential rotation, or redundant-host
removal is authorized by this runbook alone.
