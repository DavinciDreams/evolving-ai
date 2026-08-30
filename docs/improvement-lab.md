# Measured guidance improvement

`evolving_agent.self_modification.improvement_lab` implements a small, genuine
feedback loop: propose a bounded response strategy, measure baseline and candidate
on the same trusted fixtures, stage only demonstrated improvements, explicitly
activate, and roll back. It changes response guidance, **not model weights**. It
does not execute candidate code, edit source, run shell commands, open pull
requests, merge, deploy, or grant tools. Those require separate authorized flows.

## Contract

```python
from evolving_agent.self_modification.improvement_lab import (
    BenchmarkCase, GuidanceCandidate, GuidanceStrategy, ImprovementLab,
    ImprovementPolicy, ModelOutput,
)

# runner is a trusted async callback; expected answer, split, and grader are
# intentionally absent. Never wire candidate-provided code into this callback.
async def runner(guidance: str, prompt: str) -> ModelOutput:
    text, actual_tokens = await bounded_model_request(guidance, prompt)
    return ModelOutput(text, actual_tokens, usage_kind="provider_reported")

lab = ImprovementLab(memory, runner, ImprovementPolicy())
candidate = GuidanceCandidate(
    candidate_id="evidence-v2",
    strategy=GuidanceStrategy(separate_evidence=True, acknowledge_uncertainty=True),
    source_memory_ids=("123", "456"),
    rationale="Redacted observation explaining the proposed response preference",
)
report = await lab.evaluate(candidate, trusted_fixture_suite, run_id="unique-run-id")
if report["eligible"]:
    # An explicit control-plane operation, not permission supplied by a dream.
    state = await lab.promote(report["run_id"], expected_revision=lab.revision)
    # Pin state["state_memory_id"] in the authorized deployment control plane.
await lab.rollback(expected_revision=lab.revision, reason="Observed regression")
```

The strategy vocabulary is closed: plain/JSON response format, word limit,
evidence separation, uncertainty acknowledgment, and calculation verification.
Guidance is rendered from fixed templates subordinate to system instructions,
user requests, and authorization boundaries. Candidate rationale and source
memories never enter the benchmark runner as executable instructions. The caller
must redact rationale and rollback reasons before submitting them.

The root runtime must include `lab.active_guidance` in its actual response path
for promotion to have an effect. Baseline and candidate use the same fixed base
prompt/model configuration during evaluation. A dream may **propose** a
strategy from this schema; it cannot define benchmark answers, modify the grader,
assert that it passed, or authorize its own promotion.

## Harness identity and limits

The runtime runner shares `core.identity.BASE_STEWARD_PROMPT` (identity and safety)
with chat, followed by a fixed experiment boundary and the candidate's bounded
preferences. This is intentionally a **narrow text-guidance trial**, not a replica
of production chat: there is no retrieval, conversation history, tool execution,
connector state, or external action. Passing cannot establish retrieval quality,
tool safety, multi-turn behavior, or end-to-end production equivalence.

An immutable `HarnessDescriptor` records the provider label, SHA-256 digests of
selected model/endpoint identifiers, adapter identity and fixed prompts, the
no-tools/no-retrieval boundary, redaction transform version, temperature 0 and
512-token output cap. Raw model/endpoint configuration and credentials are not
stored. The descriptor and its digest are included in input fingerprints,
evaluation reports and active-state artifacts. Configuration drift is rejected
before another runtime provider call. A changed model, endpoint or base prompt
requires fresh evaluation; restore rejects mismatched or legacy un-fingerprinted
states instead of silently treating their evidence as current.

The descriptor is trusted-adapter provenance, not a sandbox attestation. Generic
injected runners default to `unspecified` metadata and must provide their own
accurate descriptor; this module cannot introspect arbitrary callable behavior.
Provider-side model aliases may change behind the same identifier, temperature
zero does not guarantee determinism, and hashing does not establish model weights
or service version. Pin versioned models and curate repeat trials when available.

## Evidence and gates

- Deterministic exact-match grading after outer whitespace removal; no LLM's
  self-score and no fabricated default success score.
- Separate development and held-out fixtures, unique IDs/prompts, minimum sample
  counts, and at least one critical safety/regression fixture.
- Candidate must improve held-out pass rate by the configured gain, meet the
  held-out quality floor, pass **all** critical fixtures, and lose no case the
  baseline passed. An unchanged strategy cannot pass due to model randomness.
- Alternating baseline/candidate call order reduces simple ordering bias.
- Artifacts contain actual per-case outcomes, output/input/answer hashes,
  baseline revision, strategy, source memory IDs, suite digest, policy, call
  count, token debit, usage accounting source, and rejection/incomplete reasons.
  Raw prompts, expected answers, and model output are not persisted.

The supplied default sample floor is a plumbing minimum, not statistical proof.
Operators should use representative, larger, independently curated suites with
secret held-out answers, fresh rotating holdouts, and repeated seeded trials
where appropriate. Exact match fits structured tasks; it is not a universal
quality metric. Scores support only the finite tested suite, not a general claim
of smarter behavior. Repeated tuning on one visible holdout contaminates it.

## Budget and non-reentrancy

Default bounds: 24 fixtures / 48 calls, 24,000 token debit, 16,000 output characters,
60 seconds for evaluation, 10 seconds per callback, 10 seconds per persistence
call, and 16 retained reports/rollback states. Validation rejects impossible
fixture/call budgets before invoking a provider. Failure, overflow, incomplete
evaluation, or timeout never makes a candidate eligible.

`ModelOutput.usage_kind` distinguishes `provider_reported`, `conservative_bound`,
and the offline demo's `synthetic` debit. `unreported` (the constructor default)
is rejected. If a provider wrapper exposes only text, debit a documented
conservative upper bound (prompt bytes plus bounded output allowance); do not
label it actual provider usage. The lab checks debit **after** each call, so the
trusted runner must impose provider-side output limits and a budget-aware
allowance before submitting. A debit overflow rejects the run but cannot undo
tokens already spent.

One nonblocking operation at a time; overlapping requests fail immediately
instead of queueing. Timeouts request cancellation and return without awaiting a
cancellation-resistant callback indefinitely. The lab remains quarantined until
that callback exits. A callback that blocks the event-loop thread cannot be made
safe by asyncio: runners must use nonblocking transports, never arbitrary code.

## HAM durability and restart boundaries

The existing `memory.add_memory(entry)` interface writes append-only
`improvement_evaluation` and `improvement_state` artifacts. HAM derives
idempotency from stable source IDs. Evidence is persisted before activation;
state contains revision, previous state ID, active strategy, previous strategies,
and exact evaluation artifact ID. Failed writes do not update the active in-memory
strategy. An uncertain state write must be retried with exactly the same inputs
before a different state mutation; no silent fork of the local revision chain.

Within a running instance, retries of a retained `run_id` reuse measured evidence,
do not pay for a second evaluation, and reject changed inputs. Pending writes
reuse identical content and timestamps. Run IDs must be globally unique; bounded
in-memory replay retention is not an exhaustive distributed run registry.

On restart, explicitly call `await lab.restore(latest_state_memory_id)`. Do not
use ranked memory search as an active-policy selector. The caller must retain
the latest exact state ID; this module cannot prove an arbitrarily supplied old
ID is latest. Restoration validates the closed strategy/schema, preserves
rollback history, and clears staged evaluations; new promotion requires fresh
measurement against the restored baseline. Evaluation/state artifacts remain in
HAM independently of the in-memory retention window.

**Concurrency boundary:** revision checks are process-local, not distributed HAM
CAS. Run one owning lab in a single worker/process. Multiple service replicas
must not activate guidance until an authoritative HAM lease/transactional
compare-and-swap pointer exists. Evidence artifacts alone do not solve ownership.

## Offline demonstration and checks

```powershell
python -m evolving_agent.self_modification.improvement_lab --demo
python -m pytest tests\test_improvement_lab.py -q
```

The demo uses a clearly labeled deterministic synthetic runner and an ephemeral
memory sink. Baseline plain text fails JSON fixtures; the JSON strategy passes
both development and held-out fixtures while retaining a credential-refusal
fixture. It stages, promotes, and rolls back without network access, credentials,
database changes, or a paid model. This demonstrates the machinery, **not**
improvement by a real LLM, real HAM durability, or deployed behavior.
