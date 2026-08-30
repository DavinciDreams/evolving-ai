# Operating the Katbot steward

Katbot can consolidate recent HAM memories, run bounded response-strategy
experiments, and activate or roll back measured guidance. These are opt-in
capabilities, not unrestricted self-modification. The implementation does not
change model weights, execute generated code, grant tools, publish repositories,
or treat a dream as fact. Offline tests demonstrate the control flow; **real
provider quality gains, production HAM behavior, and deployment readiness still
require separate authorized verification**.

## Deployment and authority boundary

Run **one application worker and one owning process per HAM principal**. Set
`WEB_CONCURRENCY=1`, retain `API_AUTH_REQUIRED=true`, and keep the backend private
until the [secure HAM migration gates](SECURE_HAM_MIGRATION.md) are satisfied.
Process-local admission and revision checks are not a distributed lease or HAM
transactional compare-and-swap. A second replica can race budgets and activation.

Project access, HAM service identity, model access, webhook signing, and external
repository authority are separate credentials. Install credentials only through
the authorized runtime secret mechanism; do not place them in prompts, fixtures,
HAM content, Git, browser storage, or `VITE_*` variables. The browser project key
is kept in memory for its authenticated session. A readiness indicator means
configuration is present, not that identity or provider access was tested live.

The HAM adapter verifies the configured principal and scope. Durable source
memories and dream/learning evidence belong in HAM/PostgreSQL. Legacy Chroma
must remain contained and read-only after verified migration. Local interaction
history and the connector delivery inbox are operational stores, not replacements
for HAM or sources of independent benchmark authority.

## Activation sequence

1. Complete the migration runbook: owner-attested credential revocation,
   least-privilege replacement identities, a controlled legacy snapshot,
   redacted export/quarantine, idempotent import, mapping/checksum verification,
   and read-only containment. A fresh off-host backup and restore drill precede
   any production HAM mutation. Source changes here do not authorize deployment,
   credential installation, reopening a public route, or volume mutation.
2. Start privately with one worker and all new feature flags disabled. Verify
   project authorization, HAM identity/scope, intended memory visibility, and
   chat behavior using explicitly authorized checks. Check storage status as
   well as the returned response: a usable reply is not proof of persistence.
3. Configure the selected text provider and review its access and cost. Dreams
   and the lab use a bounded single-attempt, tool-free adapter: no fallback,
   hidden retries, redirects, or health-probe calls. It supports the configured
   ZAI, OpenRouter, OpenAI, or Anthropic provider and requires an approved HTTPS
   endpoint. A local HTTP OpenAI-compatible URL suitable for another chat path
   is not accepted by this adapter. Never substitute a different provider key.
4. Enable dreaming first. After at least 60 idle seconds, request one cycle
   from the Status page, inspect its terminal result and exact HAM source IDs,
   and verify preservation of the original memories. Manual requests still
   obey minimum interval, idle, source-count, and quota checks; a skipped cycle
   is not a synthesized memory.
5. Enable the improvement lab with a deliberately curated benchmark. Evaluate
   manually and inspect failures, critical cases, and durable evidence before
   activating a candidate. Pin the latest returned `state_memory_id` in
   `IMPROVEMENT_STATE_MEMORY_ID` after every activation or rollback.
6. Only then consider autonomous learning. Supply an operator-owned suite file
   and leave automatic promotion off initially. Enabling auto-promotion is a
   distinct authorization to activate eligible guidance. Media and connectors
   are independent opt-ins; review their external-data boundaries separately.

Apply environment changes through the normal reviewed restart workflow. These
steps describe operator gates, not a script that silently performs them.

## Configuration map

Defaults below describe this implementation, not an observed deployment. See
[`.env.example`](../.env.example) for the broader application configuration.

| Setting | Default / required value | Purpose |
| --- | --- | --- |
| `API_AUTH_REQUIRED` | `true` | Keep private API authorization enabled |
| `PROJECT_API_KEY` | separately provisioned | Project control-plane access |
| `MEMORY_BACKEND` | `ham` | Authoritative durable memory |
| `HAM_API_URL`, `HAM_KEY` | reviewed HTTPS endpoint and dedicated credential | HAM transport and principal |
| `HAM_PROJECT`, `HAM_SCOPE`, `HAM_EXPECTED_AGENT_ID` | explicitly scoped deployment values | Verified project/service identity |
| `LEGACY_MEMORY_READ_ONLY` | `true` | Legacy containment; also enforce volume permissions |
| `WEB_CONCURRENCY` | `1` | Required singleton ownership |
| `CHAT_TIMEOUT_SECONDS` | `60` | Foreground deadline |
| `EVALUATION_TIMEOUT_SECONDS` | `8` | Optional response self-evaluation deadline |
| `RESOURCE_SHUTDOWN_SECONDS` | `5`, maximum `10` | Final resource-cleanup wait |
| `DREAM_CYCLE_ENABLED` | `false` | Append provenance-linked dream synthesis |
| `DREAM_CYCLE_INTERVAL_SECONDS` / `DREAM_CYCLE_IDLE_SECONDS` | `900` / `60` | Minimum cadence and quiet period |
| `IMPROVEMENT_LAB_ENABLED` | `false` | Trusted-fixture evaluation and revision-checked activation |
| `IMPROVEMENT_STATE_MEMORY_ID` | empty initially | Exact latest HAM activation/rollback state ID |
| `LEARNING_CYCLE_ENABLED` | `false` | Autonomous finite-population experiments |
| `LEARNING_CYCLE_SUITE_FILE` | required when learning enabled | Operator-owned JSON fixture file |
| `LEARNING_CYCLE_AUTO_PROMOTE` | `false` | Separate eligible-candidate activation opt-in |
| `LEARNING_CYCLE_INTERVAL_SECONDS` / `LEARNING_CYCLE_IDLE_SECONDS` | `900` / `60` | Experiment cadence and quiet period |
| `LEARNING_CYCLE_MAX_DAILY_EXPERIMENTS` | `4` | Rolling 24-hour attempt quota, failures included |

Keep `ENABLE_SELF_MODIFICATION`, `AUTO_PR_ENABLED`, `AUTO_UPDATE_KNOWLEDGE`,
`ENABLE_HOST_TOOLS`, `ENABLE_BEST_OF_N`, and `ENABLE_ENSEMBLE_JUDGE` disabled
unless their separate behavior has been reviewed. Optional chat self-evaluation
is not the measured lab: its LLM judgments are labeled as such, missing scores
are not invented, and legacy unverified history is not hydrated as evidence.
Free-form Reflexion does not automatically mutate the active system policy.
Legacy publishing/unbounded analysis routes are
[retired with HTTP 410](LEGACY_API_RETIREMENT.md), not restored by these flags.

The [dream configuration reference](DREAM_CYCLE.md) covers all source, prompt,
output, deadline, and quota limits. Default dreaming reserves at most 24 attempts
and 21,600 output tokens per rolling day, with a 45-second cycle deadline. The
[learning reference](LEARNING_CYCLE.md) covers its 120-second overall deadline
and fixture file. Each lab experiment separately defaults to at most 24 cases,
48 calls, a 24,000-token conservative debit, and a 60-second evaluation deadline.
These are not hard currency limits: input tokens cost money, debit is checked
after a call, and a timeout cannot refund a provider request already accepted.

## Operator UI and asynchronous API

Open the authenticated **Status** page (`/status` in the frontend). The
**Katbot steward** panel shows runtime occupancy, deadlines, failure counters,
dream outcomes, learning state, and recent job IDs. **Request one dream cycle**
admits an asynchronous job; it does not bypass the safety gates.

The **Measured learning lab** panel exposes the fixed strategy controls and a
benchmark JSON input. **Evaluate candidate — uses provider credits** starts a
paired baseline/candidate experiment. Inspect its development/holdout results,
critical failures, rejection reasons, provider-call count, and HAM evidence ID.
**Activate measured candidate** requires eligible staged evidence at the current
revision. **Restore previous guidance** records a reason and a new durable state
revision; update the exact state pin afterward. The UI does not enable backend
feature flags or turn acceptance into success.

API paths below are backend paths; the frontend deployment proxy may prepend
`/api`. All require project authorization (`X-API-Key` or supported bearer
credential).

| Route | Result |
| --- | --- |
| `GET /steward/status` | Value-free runtime, dream, lab, learning, storage, and recent job status |
| `POST /steward/dream` | HTTP 202 with job ID, or disabled/busy rejection |
| `GET /steward/jobs/{job_id}` | Job outcome and result while retained |
| `POST /steward/improvement/evaluate` | HTTP 202 for a validated candidate/fixture request |
| `GET /steward/improvement/runs/{run_id}` | Retained measured report |
| `POST /steward/improvement/promote` | Body: `{"run_id":"operator-unique-run","expected_revision":0}` |
| `POST /steward/improvement/rollback` | Body: `{"expected_revision":1,"reason":"Observed regression"}` |

Evaluation accepts exactly `candidate_id`, `run_id`, `strategy`, optional
`source_memory_ids` and `rationale`, and `cases`. The strategy vocabulary is:

```json
{
  "response_format": "plain",
  "max_response_words": 500,
  "separate_evidence": false,
  "acknowledge_uncertainty": false,
  "verify_calculations": false
}
```

`response_format` is `plain` or `json`; the word preference is an integer from
1 to 2,000. Other fields are booleans; unknown keys are rejected. Each fixture
has `case_id`, `prompt`, `expected`, `split` (`development` or `holdout`), and
optional boolean `critical`. Supply 4–24 unique fixtures with at least two per
split and one critical case. [The suite example](LEARNING_CYCLE.md) demonstrates
the schema, not an adequate production quality/safety benchmark. Expected
answers and graders never come from memories or candidate-generated code.
Evaluation bodies are capped at 1 MiB; promotion and rollback bodies have smaller
bounds. Invalid schemas and oversized bodies are rejected before model work.

HTTP 202 means admitted, not completed. Poll the job until terminal, then inspect
the result: `completed` can contain a skipped dream or rejected experiment.
Busy work is rejected immediately with HTTP 409. A stale revision fails the
job, rather than silently applying a newer revision. Mutation requests are not
automatically replayed by the UI. After a transport timeout, inspect the known
job and durable evidence before an explicit retry; do not invent a new run ID
and risk paying for a duplicate experiment. Job history is bounded to 30 entries,
lab report history to 16; an expired local result is not missing HAM evidence.

## What learning establishes

Dreams preserve sources and append labeled unverified synthesis, exact source
IDs/checksums, quoted observations, and testable hypotheses. Quotes prove only
what a source said. Recent-window deduplication and attempt reservations survive
restarts through HAM, but bounded lookback is not exhaustive archive coverage.

Autonomous learning uses a dream ID as provenance and a trigger, never copies
dream text into policy, and tests a fixed finite population of response guidance.
It stages only measured candidates; promotion additionally requires no per-case
regressions, critical-case passes, sufficient holdout gain and quality, the same
baseline revision, and successful durable state persistence. Active guidance
affects subsequent chat responses. It is not weight training or code evolution.

Exact-match grading and a finite reused holdout establish only performance on
those fixtures. They do not establish general intelligence, broad safety, or
independently unseen quality improvement. Rotate realistic operator-owned suites
and reserve untouched evaluation before wider claims. See the
[lab evidence contract](improvement-lab.md).

The lab records an immutable harness descriptor and digest: provider label,
hashed model/endpoint/adapter/prompt identifiers, redaction transform, temperature,
and output cap. Trials share Katbot's base identity but intentionally omit chat
retrieval, conversation history, tools, and external effects. They are not an
end-to-end production replica. Configuration drift requires fresh measurement;
a stable provider alias alone does not prove unchanged model weights.

After restart, only the explicitly pinned latest `IMPROVEMENT_STATE_MEMORY_ID`
restores active guidance and rollback history. Ranked search does not select
policy, and the service cannot prove an old valid pin is the latest state.
Staged in-memory reports do not survive restart; durable HAM evidence does.
Restoration rejects a different harness or a legacy state without a matching
descriptor; do not erase the mismatch and label old evidence current.
Automatic promotions do not rewrite deployment environment configuration, so
operators must capture and update the newest pin before a later restart.

## Media and connector surfaces

In chat, **Audio & vision** supports explicit image analysis, audio-file
transcription, and reading the latest reply aloud. Uploads are sent only after
**Analyze / transcribe**; they are not automatically stored in HAM. Extracted
text remains unverified and editable. **Send reviewed text to chat** is a new
foreground message and therefore enters normal chat history/memory. Speech is
labeled AI-generated and reads at most the first 4,096 reply characters. This
is file-based media support, not continuous listening or realtime video.

Enable capabilities separately with `MEDIA_VISION_ENABLED`,
`MEDIA_TRANSCRIPTION_ENABLED`, and `MEDIA_SPEECH_ENABLED`; all default false.
Use a dedicated `MEDIA_OPENAI_API_KEY`. Media has a separate bounded concurrency
limit; the agent's single-flight lease is not a global media semaphore.

`CONNECTORS_ENABLED=false` by default. The sole built-in `app-webhook` connector
requires its allowlist entry, a distinct signing secret, project authentication,
and a timestamped body signature. It stores sanitized untrusted events for
explicit review/acknowledgement. Intake never calls a model, creates memory,
dispatches a tool, or installs code. This is a signed app-event foundation, not
native OAuth connectors or an arbitrary plugin marketplace. Read the exact
[media and webhook protocol](MEDIA_AND_CONNECTORS.md) before integration.

## Busy, timeout, and shutdown behavior

Chat, persistence/maintenance, dreaming, and lab work share single-worker
admission. A late task that ignores cancellation retains occupancy: status can
remain busy after the caller received a timeout. Do not launch a second worker,
clear an in-memory flag, or reenter the agent to work around this safeguard.
Inspect `active_workers`, `active_async_operations`, and `background_jobs`, plus
the dream/lab/learning running state and sanitized failure type.

Shutdown stops new admissions, requests cancellation, and waits only bounded
intervals. If dependencies remain active, cleanup reports incomplete and avoids
closing their underlying resources. An asyncio cancellation cannot kill a native
thread, interrupt arbitrary event-loop-blocking code, or undo an accepted remote
write. The external process supervisor still needs an explicit final grace and
termination policy. Reconcile uncertain durable outcomes before restarting work.

## Offline checks

From the repository root in the project's Python environment:

```powershell
python -m pytest tests\test_runtime.py tests\test_dream_cycle.py tests\test_learning_cycle.py tests\test_improvement_lab.py tests\test_steward_learning_integration.py tests\test_agent_cleanup.py tests\test_evaluation_provenance.py -q
```

The end-to-end learning test drives the real orchestration with synthetic model
output and an in-memory HAM substitute: dream, measured staging, activation,
rollback, exact-ID restoration, source preservation, and restart deduplication.
It spends no provider credits and writes no production memories. Passing it
does not substitute for a reviewed deployment or an authorized real-provider
quality experiment.
