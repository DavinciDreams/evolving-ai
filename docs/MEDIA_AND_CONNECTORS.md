# Optional media and reviewed connector intake

These capabilities are implemented but **disabled by default**. Their status distinguishes enabled, credential-configured, and ready. Readiness does not claim that a provider accepted a live request. The automated tests use synthetic media and fake HTTP only; no production credentials, provider calls, or deployment are needed.

All routes remain under the existing project authorization middleware (`X-API-Key` or bearer credential). Keep `API_AUTH_REQUIRED=true`. Media credentials, webhook signing secrets, and project/HAM credentials must be separate. Never put credentials in chats, payloads, memories, Git, or client-side environment variables.

## Media

Operator environment settings:

| Variable | Default |
| --- | --- |
| `MEDIA_VISION_ENABLED` | `false` |
| `MEDIA_TRANSCRIPTION_ENABLED` | `false` |
| `MEDIA_SPEECH_ENABLED` | `false` |
| `MEDIA_OPENAI_API_KEY` | unset |
| `MEDIA_VISION_MODEL` | `gpt-4.1-mini` |
| `MEDIA_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` |
| `MEDIA_SPEECH_MODEL` | `gpt-4o-mini-tts` |
| `MEDIA_TIMEOUT_SECONDS` | `45` (range 1–120) |
| `MEDIA_MAX_CONCURRENT` | `2` (range 1–8) |

The optional fallback to `OPENAI_API_KEY` applies only when `OPENAI_BASE_URL` is unset or exactly `https://api.openai.com/v1`. A compatible-provider key is never silently sent to OpenAI. The destination is fixed to the official API; redirects and ambient HTTP proxy configuration are disabled. Requests cannot choose an endpoint or model. Account/model access and cost require operator verification. Restart to apply environment changes.

`GET /media/status` lists per-capability readiness, selected models, supported MIME types, and limits.

`POST /media/vision` accepts JSON:

```json
{"mime_type":"image/png","data_base64":"<raw base64 bytes>","prompt":"Describe this image.","detail":"low"}
```

Allowed image types: PNG, JPEG, WebP. Maximum decoded content is 5 MiB. Base64 must be strict: no URL, local path, or `data:` prefix. The default low detail limits expense; high and auto are optional. Input magic bytes are checked, but the service does not claim to fully validate/decode image containers. Provider parsing is still authoritative.

`POST /media/transcribe` accepts JSON:

```json
{"mime_type":"audio/webm","data_base64":"<raw base64 bytes>","language":"en"}
```

Allowed audio types: WAV, MPEG/MP3, WebM, Ogg, FLAC, MP4. Maximum decoded content is 10 MiB; language is optional. The provider receives an actual multipart file, with a generated filename rather than a user-supplied path. Transcription and vision return `text`, `model`, `provider`, `stored:false`, `untrusted_content:true`, and `redacted`.

`POST /media/speech` accepts `{"text":"Hello","voice":"coral"}` and returns MP3 bytes. Speech text is limited to 4,096 characters; voice selection uses a fixed allowlist. Responses include `X-Audio-Generated: ai`, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`. **Any player must clearly tell the listener that the voice is AI-generated.** No custom voice cloning is implemented.

Requests have body size/deadline limits, bounded provider responses, total request deadlines, and immediate busy rejection rather than an unbounded wait queue. Timeouts, provider errors, malformed responses, and redirects return sanitized errors. No provider diagnostics, uploaded content, or credentials are logged. Media and its output are not written to HAM or the local inbox. Content is still transmitted to OpenAI and is subject to the account's provider data controls; `store:false` for vision is not a zero-retention guarantee. Credential-shape redaction is defense-in-depth, not a promise to discover every secret.

The implementation follows the official [vision input format](https://developers.openai.com/api/docs/guides/images-vision), [transcription API](https://developers.openai.com/api/docs/guides/speech-to-text), and [speech generation API](https://developers.openai.com/api/docs/guides/text-to-speech).

## App, webhook, and plugin boundary

This initial connector is a **signed app-event bridge**, not an installed third-party OAuth integration or arbitrary plugin runner. The built-in `app-webhook` manifest declares only `events.receive`, `events.list`, and `events.acknowledge`. It cannot invoke tools, run code, fetch URLs, publish messages, call a model, or write memories. New connector code/manifests require code review and an operator allowlist entry; there is no dynamic import or remote manifest installation.

Set `CONNECTORS_ENABLED=true`, `CONNECTOR_ALLOWLIST=app-webhook`, and a dedicated `CONNECTOR_WEBHOOK_SECRET` of at least 32 random bytes encoded as a string in the secure runtime secret store. Use a persistent, access-controlled `PERSISTENT_DATA_DIR`. Configuration rejects unknown connector IDs, short secrets, and reuse of project/HAM/GitHub credentials.

`GET /connectors/status` exposes the manifest and readiness without secret values.

`POST /connectors/webhooks/app-webhook` requires project authentication **and**:

- `Content-Type: application/json`
- `X-Katbot-Timestamp`: Unix seconds as decimal text
- `X-Katbot-Signature`: `sha256=` plus the lowercase hex HMAC-SHA256 digest

The signed bytes are exactly:

```text
app-webhook + "." + timestamp + "." + raw_request_body
```

Use UTF-8 for the signing secret and header text. The body must be an object with exactly these fields:

```json
{"id":"unique-delivery-id","type":"app.updated","data":{"message":"new event"}}
```

`id` and `type` are bounded identifiers. Data is a bounded JSON object. Maximum body is 64 KiB; compressed bodies, duplicate keys, non-finite numeric literals, excessive nesting, unknown fields, and invalid signatures are rejected. Timestamps must be within five minutes. The SQLite delivery inbox atomically remembers signatures and delivery IDs, including across process restarts. Keep one shared inbox database for multiple workers on the same host; independent replicas do not share replay protection and require a future shared transactional delivery store.

A third-party service that cannot supply this signature plus project authorization needs a reviewed server-side bridge. Do not disable project authentication or expose the general project credential to an untrusted app. GitHub/Slack/etc. native signatures are not interchangeable with this protocol.

Accepted events return HTTP 202 and `dispatched:false`. They are untrusted content in a review queue, never instructions. `GET /connectors/events?status=pending&limit=50` lists sanitized events. An authenticated operator can `POST /connectors/events/app-webhook/{event_id}/acknowledge` with `{"disposition":"reviewed"}` or `{"disposition":"discarded"}`. Acknowledgement removes the stored payload and retains the delivery ID for deduplication; it does not execute anything or promote content to memory. SQLite WAL/backup copies can retain earlier bytes until normal checkpoint/retention processing, so operate this directory as sensitive data.

The queue retains at most 500 events for seven days and rejects overflow. Acknowledged IDs still consume retained capacity until expiry, avoiding a replay gap. Expired rows are cleaned during the next successful intake transaction; expired payloads are omitted from listing. Durable agent memory remains HAM/PostgreSQL: this small local database is operational delivery state only. Secret-bearing keys and credential-shaped text are redacted before insertion, but payloads should never intentionally include secrets.

## Verification

```powershell
python -m pytest tests/test_media_service.py tests/test_connector_service.py tests/test_media_connector_routes.py -q
```

Tests exercise provider payloads, disabled/missing-key behavior, URL rejection, MIME/size bounds, response redaction, provider failures/redirects, cancellation/concurrency, request body bounds, signatures, stale timestamps, persistent/concurrent replay rejection, nesting, credential-field sanitization, and explicit review. End-to-end provider acceptance remains a separate authorized deployment check.
