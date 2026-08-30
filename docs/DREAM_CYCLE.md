# Bounded dream consolidation

Dream consolidation is an opt-in, asynchronous pass over recent **HAM-backed**
memory. It appends derived memories and never edits, deletes, prunes, or promotes
the source memories. It does not execute code, call tools, install plugins, or
authorize actions. A dream is an interpretation to examine, not proof of progress
or a replacement for its sources.

## Runtime contract

```python
dreams = DreamConsolidationService(
    memory,
    llm_manager,
    settings=DreamConfig.from_env(),
    is_idle=lambda: not foreground_work_is_running(),
)
dreams.start()                  # synchronous; schedules without waiting
dreams.note_activity()          # call BEFORE foreground work's first await
result = await dreams.run_once()  # also obeys idle, interval, quota, HAM gates
await dreams.stop()             # shutdown; returns false if cancellation stuck
```

Use one service per HAM principal. The runtime must supply a fast synchronous
idle predicate, call `note_activity()` for each accepted foreground task, and
stop dreaming before closing its LLM/HAM transports. The start call does not
perform I/O. Manual requests should enqueue a background job and return its ID;
they must not hold an HTTP/chat request open while dreaming. `status()` exposes
counts, last outcome, source counts, timing, and state, never prompts or content.
Serve it behind the existing authenticated runtime boundary.

The service never waits for a busy cycle; it returns `already_running`. New
foreground activity cancels synthesis and prevents late consolidation. The
overall deadline includes storage reads/writes, not only the model call. A
dependency that ignores cancellation keeps the single-flight slot occupied;
it cannot make a later cycle overlap. `stop()` has a separate short deadline.
As with any remote request, cancellation cannot undo a write already accepted
by HAM; deterministic receipts allow recovery after uncertain responses.

## Evidence and provenance

1. Read at most 100 recent receipts, reservations, and source memories each.
2. Select at most 12 distinct eligible source contents; exclude dreams,
   evaluations, quarantined/private records, and other derived memories.
3. Redact known credential shapes and private keys **before** sending excerpts
   to a model. No source metadata or credentials are sent to the model.
4. Append a `dream_attempt` quota reservation before spending model tokens.
5. Ask for a bounded JSON synthesis. Reject malformed/oversized output, unknown
   citation IDs, fabricated observation quotes, and detected credential output.
6. Append one `dream_consolidation` receipt with source IDs, full-redacted-content
   SHA-256 checksums, excerpt truncation flags, timestamps, and the schema version.

Observations must quote the exact source excerpt and establish **only what the
source said**. The summary is explicitly unverified. Hypotheses cite supplied
source IDs and include proposed falsifiable checks, which still require their
own authorization. Citation existence does not prove that a hypothesis follows
from the source. Downstream retrieval must preserve this epistemic distinction.
If no model is injected, the pass stores labeled extractive excerpts with no
invented hypotheses; it does not pretend to have performed model synthesis.

Duplicate full content contributes one unit of evidence while retaining every
source ID found in the scanned window. The checksum covers the full redacted
content, not merely the excerpt, so matching prefixes do not imply equality.
An excerpt marked truncated does **not** represent exhaustive source coverage.
Consolidated sources remain in HAM for direct retrieval and future targeted work.
Known-pattern redaction is defense in depth, not proof that arbitrary secrets or
personal information have been detected; only ingest appropriately scoped data.

## Restart behavior and quotas

Each receipt uses a deterministic `dream-v1:<batch digest>` source ID. The
existing HAM adapter turns that into a stable ingest idempotency key. Recent
receipts supply source checksums, so a restarted worker skips already covered
sources without making a model call. If a write succeeds but its HTTP response
is lost, the next cycle recovers from the durable receipt.

This is **bounded recent-memory consolidation, not an exhaustive backfill**.
Sources/receipts outside the 100-row read window are not guaranteed discoverable.
HAM idempotency prevents duplicate persistence of the same batch even beyond
the receipt lookback; a changed grouping can still reconsolidate old sources.
Run archive/backfill migration as an explicit separate workflow.

Quota reservations are append-only and counted over the previous rolling 24
hours, including failed, invalid, cancelled, and uncertain model attempts. The
default limit is 24 passes and 21,600 reserved **output** tokens. Input is bounded
by prompt characters, but this is not a currency or total-token billing cap.
Output reservations are conservative: a short response does not refund unused
allowance. Missing/corrupt budget state fails closed.

Inject a single-attempt generation adapter when strict accounting is required.
The general `LLMManager` can internally retry/fall back to multiple providers;
one reservation here counts one logical call, not those hidden attempts. SDK
retry policy and actual provider usage must be accounted for separately.

Reservations and idempotency are not a distributed lease. Multiple processes
sharing one principal could race the quota read; deploy a singleton worker per
principal until HAM-backed transactional reservation/lease support is added.
Do not use this scheduler as a fleet-wide budget enforcement mechanism.

## Configuration

Environment variables use `DREAM_CYCLE_` plus the uppercase `DreamConfig` field:

| Variable suffix | Default | Meaning |
| --- | --- | --- |
| `ENABLED` | `false` | Explicit opt-in, HAM required |
| `INTERVAL_SECONDS` | `900` | Minimum delay after any attempted pass |
| `IDLE_SECONDS` | `60` | Foreground quiet period before starting |
| `TIMEOUT_SECONDS` | `45` | Whole-cycle deadline |
| `LLM_TIMEOUT_SECONDS` | `20` | Model call deadline within cycle |
| `STOP_TIMEOUT_SECONDS` | `2` | Shutdown cancellation wait |
| `SCAN_LIMIT` | `100` | Maximum recent source rows |
| `MIN_SOURCES` / `MAX_SOURCES` | `2` / `12` | Distinct source contents per pass |
| `MAX_SOURCE_CHARS` | `1600` | Per-source excerpt bound |
| `MAX_INPUT_CHARS` | `16000` | Entire prompt, including instructions/JSON |
| `MAX_OUTPUT_CHARS` | `6000` | Generated JSON and final stored-content bound |
| `MAX_TOKENS` | `900` | Requested maximum model output tokens |
| `MAX_HYPOTHESES` | `5` | Maximum speculative links |
| `MAX_DAILY_CYCLES` | `24` | Rolling 24-hour reservation count |
| `MAX_DAILY_OUTPUT_TOKENS` | `21600` | Rolling reserved output allowance |

Invalid, nonfinite, negative, oversized, and inconsistent limits fail at startup.
Boolean values must be `true`, `false`, `1`, or `0`.

## Offline verification

```powershell
python -m pytest tests\test_dream_cycle.py -q
```

Tests use fake model/storage dependencies: no production HAM writes, real model
calls, paid evaluation, deployment, or credentials are involved. They cover
restart deduplication, uncertain writes, exact cited synthesis, source immutability,
credential redaction, reservations after failures, idle/single-flight behavior,
storage/model deadlines, cancellation-resistant dependencies, and input bounds.
