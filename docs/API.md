# API

Base path `/api`. JSON unless stated. Interactive docs: `/docs` (FastAPI). Authentication: an anonymous httpOnly session cookie (`ps_session`) is issued on first use; searches belong to it. Browsers must send credentials (the Vite proxy makes this same-origin).

## Errors

Every error uses one shape:

```json
{ "error": { "code": "provider_not_configured", "message": "gemini is not configured. Set GEMINI_API_KEY, GEMINI_VISION_MODEL in the backend environment.", "details": { "provider": "gemini", "missing": ["GEMINI_API_KEY", "GEMINI_VISION_MODEL"] } } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 404 | `not_found` | Unknown id **or not owned by this session** |
| 409 | `conflict` | Too many running searches for this session |
| 413 | `image_too_large` | Upload over `MAX_UPLOAD_MB` or pixel limit |
| 415 | `unsupported_image` | Not JPEG/PNG/WebP by content, or declared type mismatch |
| 422 | `validation_error` / `invalid_image` | Bad request body / unreadable image |
| 422 | `provider_rejected_input` | Provider refused the image/settings |
| 429 | `rate_limited` / `provider_quota_exceeded` | Request limit, or provider quota/billing |
| 502 | `provider_auth_failed` / `provider_bad_response` / `provider_error` | Provider problems |
| 503 | `provider_not_configured` / `not_ready` | Missing provider settings / DB down |
| 504 | `provider_timeout` | Provider timed out |

## Endpoints

### `GET /api/health` → `{"status":"ok"}`
Liveness.

### `GET /api/ready` → `{"status":"ready"}`
Checks the database; 503 `not_ready` otherwise.

### `GET /api/config`
Capability report, **never secrets**: `providers[{provider, configured, missing[]}]`, `markets`, `modes`, `demo_mode`, `limits{max_upload_mb, allowed_mime, max_quantity}`, `sources[{id,name,kind,is_demo,configured,hint?}]`, `currency{provider,india,global}`.

### `POST /api/identify` (multipart)
Fields: `image` (file), `provider` (`openai` | `gemini`, default `openai`). Validates the file, runs the identify-only workflow with **exactly the selected provider**, returns:

```json
{ "identity": { "category": "medicine", "strength": { "value": "500 mg", "status": "confirmed", "evidence": "..." }, "...": "...", "contradictions": [], "notes": [], "extracted_by": "openai:<model>" },
  "ambiguity": { "needs_clarification": false, "missing_essentials": [], "unconfirmed_essentials": [], "contradictions": [], "messages": [] },
  "provider": "openai", "model": "<model>", "duration_ms": 2300, "state": "IDENTITY_READY" }
```
`state` is `IDENTITY_READY` or `NEEDS_CLARIFICATION`. Field `status` is `confirmed | inferred | unknown`. Rate limit: `IDENTIFY_RATE_LIMIT_PER_MINUTE`.

### `POST /api/identity/check`
Body: a `ProductIdentity`. Returns an `ambiguity` object using the same deterministic rules. No LLM call. Field values are limited to 300 characters; `notes`/`contradictions` to 20 items.

### `POST /api/searches` → 202 `{ "id", "state" }`
Body:
```json
{ "identity": { "...ProductIdentity..." },
  "options": { "provider": "openai", "mode": "retail|business", "market": "india|global",
               "quantity": 1, "min_price": null, "max_price": null } }
```
`quantity` is in **packs of the identified pack** (1–100000). `min_price`/`max_price` apply to the supplier price per pack, in the market currency, only when set. Starts a background search. 409 when `MAX_CONCURRENT_SEARCHES_PER_SESSION` is reached. Unclear identity details do **not** block the search: they are returned in `progress.warnings` and limit verification. Only an identity with nothing to search for (no brand, product, generic or ingredient name) finishes immediately as `NEEDS_CLARIFICATION`.

### `GET /api/searches?limit=20&offset=0`
`{ items[{id, created_at, product_label, options, state, is_terminal, offers_discovered}], total, limit, offset }`, newest first, this session only.

### `GET /api/searches/{id}`
`SearchDetail`: `identity`, `options`, `progress`, `is_terminal`, `is_demo_data_present`, `target_currency`, and `offers[]` (ranked: eligible first by tier then cost; ineligible/rejected after, with `rank: null`).

`progress`: `state`, `message`, `current_node`, `completed_nodes[]`, `warnings[]` (unclear identity details), `activity[{at, phase, level, message}]` (the live agent feed, see below), `sources[{connector_id,name,kind,is_demo,status,offers,attempts,duration_ms,error}]`, `offers_discovered/verified/partially_verified/unverified/rejected`, `unresolved[]`, `error`, `finished`, `updated_at`. Counts reflect persisted work only.

Each **offer** carries: supplier (`name,country,domain`), `connector_id`, `is_demo`, `title`, `declared` attributes, `product_url`, `enquiry_url`, `availability` (`unknown` when not stated) + `availability_source`, `delivery_estimate`, `audience`, `prescription_required` (null when not stated), business-only `lead_time`/`credit_terms` (business mode, only if stated), `verification{status,reasons,checks,missing,conflicts,supplier_verification}`, `pricing{...}` (see [VERIFICATION_AND_PRICING.md](VERIFICATION_AND_PRICING.md)), `tier`, `eligible`, `ineligible_reasons`, `rank`, `source_retrieved_at`, `source_updated_at`, `evidence[]`, `duplicates_merged`.

### `GET /api/searches/{id}/events` (SSE)
`event: update` with a full `SearchDetail` payload whenever persisted state changes; `event: done` with `{"state": ...}` when finished; `: keepalive` comments. Ownership-checked.

### `GET /api/searches/{id}/offers/{offer_id}`
One offer with its evidence (`offer_id` is the stable id inside the search result).

### `DELETE /api/searches/{id}` → 204
Removes the search and its result rows from the session's history; observation history is detached and retained.

## Workflow states

`REQUEST_RECEIVED`, `IDENTIFYING_PRODUCT`, `IDENTITY_READY`, `NEEDS_CLARIFICATION`, `SEARCHING_SUPPLIERS`, `VERIFYING_OFFERS`, `PARTIAL_RESULTS`, `RESULTS_READY`, `NO_MATCHES`, `SOURCE_UNAVAILABLE`, `FAILED`. A search is complete when `progress.finished` is true (a final `PARTIAL_RESULTS` means some sources failed or the search timed out).

## Agent activity feed

`progress.activity` is an ordered list of events the workflow **actually recorded** (never generated by the UI): `at` (UTC timestamp), `phase` (`plan` | `search` | `read` | `verify` | `rank` | `done`), `level` (`info` | `success` | `warn` | `error`) and a short `message`. Examples: which sources are queried, per-source candidate counts and timings, sources skipped for missing configuration, each supplier page read (price found, or no readable price), the verification summary, ranking and the final result with elapsed time. The list is capped at 200 events, persisted with the search, and delivered live through the SSE stream. Messages contain only source names, host names and prices, never retrieved page text.
