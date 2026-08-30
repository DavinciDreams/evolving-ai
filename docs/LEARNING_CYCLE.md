# Autonomous, measured learning cycle

The optional learning cycle schedules real paired response experiments while
Katbot is idle. It is intentionally narrower than arbitrary self-modification:
it explores a declared finite population of response strategies, measures them
against operator-curated fixtures, and stages successful candidates. An explicit
operator flag can enable promotion of eligible candidates. It never modifies
weights, source code, tool authority, tests, or expected answers.

This connects the two loops without turning dream speculation into truth:

```text
HAM source memories -> bounded dream synthesis -> latest dream ID as provenance
                                                   |
operator fixtures + fixed strategy population ------+-> paired lab evaluation
                                                        -> durable staged report
                                                        -> optional gated promotion
```

Dream text is not copied into instructions. It supplies a trigger and provenance,
not graders, fixtures, or free-form policies. The population probes five bounded
changes to the active baseline: distinguish evidence, acknowledge uncertainty,
verify calculations, use a 250-word preference, or prefer compatible JSON output.
Unchanged/duplicate strategies are skipped. Scores do not generate new candidates.

## Enablement and integration

```python
settings = LearningConfig.from_env()
learning = LearningCycle(
    steward,
    cases=load_suite(settings.suite_file),
    settings=settings,
)
learning.start()                 # schedules only; returns immediately
learning.note_activity()         # call before foreground work begins
job = await learning.run_once()  # admission only; returns steward job ID
await learning.stop()            # bounded cancellation before steward shutdown
```

`LearningCycle` requires an enabled `ImprovementLab` and authoritative HAM when
enabled. Root runtime integration owns foreground exclusivity. Every experiment
is admitted through `steward.submit("improvement", ...)`; it is not an independent
parallel agent or a blocking request handler. The loop's overall deadline also
covers HAM preflight and persistence. Timed-out dependencies retain the worker's
occupied state and cannot authorize a later promotion.

| Setting | Default | Meaning |
| --- | --- | --- |
| `LEARNING_CYCLE_ENABLED` | `false` | Explicit autonomous evaluation opt-in |
| `LEARNING_CYCLE_AUTO_PROMOTE` | `false` | Separate authorization to activate eligible guidance |
| `LEARNING_CYCLE_SUITE_FILE` | empty | Required operator-owned fixture JSON path at startup |
| `LEARNING_CYCLE_INTERVAL_SECONDS` | `900` | Minimum delay between admitted jobs |
| `LEARNING_CYCLE_IDLE_SECONDS` | `60` | Quiet period following foreground activity |
| `LEARNING_CYCLE_TIMEOUT_SECONDS` | `120` | Entire experiment/preflight deadline |
| `LEARNING_CYCLE_STOP_TIMEOUT_SECONDS` | `2` | Shutdown wait before reporting unfinished work |
| `LEARNING_CYCLE_MAX_DAILY_EXPERIMENTS` | `4` | Rolling 24-hour durable attempt quota |

The suite file must be a regular file, not a symlink or URL, and at most 1 MB.
It contains only `cases`, an array of 4–24 closed-schema fixtures. Example shape:

```json
{
  "cases": [
    {"case_id":"dev-1","prompt":"Return only 2 + 2.","expected":"4","split":"development","critical":true},
    {"case_id":"dev-2","prompt":"Return only 3 + 4.","expected":"7","split":"development"},
    {"case_id":"hold-1","prompt":"Return only 5 + 6.","expected":"11","split":"holdout"},
    {"case_id":"hold-2","prompt":"Return only 7 + 8.","expected":"15","split":"holdout"}
  ]
}
```

These illustrative arithmetic fixtures demonstrate the schema, **not a useful
production safety/general-quality suite**. Curate realistic regression and safety
fixtures before enabling experiments. The lab enforces unique case IDs, at least
two development/two holdout fixtures, and at least one critical fixture. Expected
answers never reach the response generator. Memory cannot supply grader code.

## Persistence, budgets, and promotion

A `learning_attempt` HAM reservation is written before model evaluation. Its
fingerprint identifies the suite digest, baseline strategy/revision, and candidate.
Failure, timeout, invalid output, or restart does not refund the attempt. Restart
skips attempted population members and proceeds to the next candidate; an exhausted
population stops spending. Manual investigation/retry remains a separate operator
action. No dream recursion or generation of new tests is performed.

The quota bounds experiment count, not currency. Each experiment also uses the
lab's call, token-debit, output, and timeout limits; the injected provider adapter
must enforce per-call generation caps and disclose retry/usage semantics. The
100-reservation lookback is bounded; it is not an exhaustive archive or a
distributed budget lock. Deploy exactly one worker per principal.

Default behavior is stage-only. Automatic promotion requires all of:

- Explicit `LEARNING_CYCLE_AUTO_PROMOTE=true` from operator configuration.
- The lab reports `eligible=true` and `status=staged` after its critical-fixture,
  per-case-regression, minimum holdout improvement, and quality-floor checks.
- The active baseline revision still equals the revision evaluated.
- The cycle has not been cancelled or exceeded its deadline.
- The lab durably commits its state transition before activation.

Active state restoration still uses the exact operator-pinned
`IMPROVEMENT_STATE_MEMORY_ID`. Search ranking is not an authoritative state pointer.
Rollback uses the existing revision-checked lab endpoint and durable history.

The same finite suite may evaluate several predeclared candidates. Its holdout
is not perpetually unseen, so results support only that curated finite suite—not
general intelligence, broad safety, or statistically independent improvements.
Reserve genuinely untouched evaluation for operator review before wider claims.

## Offline verification

```powershell
python -m pytest tests\test_learning_cycle.py tests\test_improvement_lab.py -q
```

Tests exercise the real lab against fake providers and memory. They do not call
production HAM, spend model credits, install credentials, or deploy anything.
