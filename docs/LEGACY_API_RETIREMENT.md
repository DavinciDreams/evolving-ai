# Legacy write and unbounded analysis routes

The private steward baseline deliberately retires these authenticated POST routes with **HTTP 410 Gone**, even if legacy feature flags or GitHub credentials are configured:

| Retired route | Reason / current workflow |
| --- | --- |
| `/analyze` | Direct unbounded analysis injected fabricated default evaluation scores. Inspect `/steward/status`; supply real trusted fixtures to `/steward/improvement/evaluate` for measured response-strategy adaptation. |
| `/self-improve` | Direct modifier execution could bypass steward admission, deadlines, and evaluation gates, then publish a PR. Use the bounded evaluate/promote/rollback strategy workflow; repository changes remain separately reviewed work. |
| `/github/demo-pr` | A demo label does not grant publication authority or make an unbounded modifier safe. Publish only through a separately authorized repository workflow. |
| `/github/issue` | Direct external publication bypassed the review-only connector boundary. Signed app events may enter the connector inbox; acknowledging an event does not publish an issue. |

No request body, legacy analyzer, GitHub modifier, model, or background job is executed by these retired handlers. They remain authenticated and are marked deprecated in OpenAPI. No compatibility flag re-enables them. A future replacement must implement explicit effect authorization, bounded non-reentrant job ownership, durable idempotent evidence, and an operator-visible outcome before publication can return.

`GET /analysis-history` remains read-only, with `limit` constrained to 1–100 and credential-shaped values redacted. It does not run analysis or invent metrics. Existing historical scores are not recertified as measured evidence. The read-only GitHub endpoints remain available; this retirement does not imply a new deployed release.

The measured steward changes a closed set of response preferences, **not model weights or arbitrary code**. Benchmark fixtures and grading authority belong to the operator. Automatic dreaming preserves original memories and labels derived content; incoming connector events do not automatically become memories, prompts, tool calls, or repository effects.

`tests/test_legacy_steward_routes.py` verifies the registered routes cannot reach legacy adapters, including when old flags are true or request bodies are malformed. Historical live-server scripts are not evidence that these endpoints should still perform writes; use the network-free registered-app suite instead.

GitHub dashboard reads share one read-only snapshot with a 15-second deadline and 15-second in-process cache. Lazy PyGithub reads execute off the event loop, and a timed-out worker retains the lease until it actually exits. Concurrent dashboard reads coalesce; repeated polling cannot launch replacement threads over a stalled read. Provider errors return safe unavailable/timeout responses, never fabricated empty histories. Snapshot projections contain at most 50 PRs and 50 commits, omit PR bodies and author email addresses, and redact credential-shaped text. PR responses include the total count and a truncation flag. Commit `limit` is 1–50; local historical improvement reads are limited to 1–100 and do not recertify old scores or invoke providers. The bridge grants no write authority, even when a legacy configuration enabled automatic PRs.
