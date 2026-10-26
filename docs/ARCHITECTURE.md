# Architecture

```
React SPA ──/api──► FastAPI ──► WorkflowService ──► LangGraph (one orchestrator)
                       │                                 │
                       │                     ┌───────────┼─────────────────┐
                       ▼                     ▼           ▼                 ▼
                  SQLAlchemy/PG       VisionProvider  Connectors      Pure functions
                 (searches, offers,   (OpenAI|Gemini)  (API, web,     (verify, price,
                  evidence, history)                    page, demo)    dedupe, rank)
```

## Backend modules (`backend/app`)

| Module | Responsibility |
|---|---|
| `config.py` | Typed env settings; no model names hardcoded |
| `schemas/` | Pydantic v2 domain and API models |
| `models/`, `repositories/`, `alembic/` | Persistence and migrations |
| `providers/` | `VisionProvider` interface, OpenAI/Gemini adapters, `ProviderRegistry` (no fallback) |
| `identification/` | Image validation, normalisation, GTIN check, ambiguity rules |
| `connectors/` | `SupplierConnector` interface, Tavily, page extraction, demo fixtures, reference data, SSRF-safe fetcher |
| `verification/` | Attribute normalisation and the verification rules |
| `pricing/` | FX providers, price engine, dedupe/rank pipeline |
| `workflow/` | State, nodes, graph, background `TaskRunner` |
| `api/` | Routes, session cookie, rate limiter |

Dependency direction: `api → workflow → {providers, connectors, pricing, verification, identification, repositories} → schemas`. Business rules live in plain functions; routes and nodes only orchestrate.

## Workflow

One LangGraph graph is used in two modes:

- `identify_only` (`POST /api/identify`): `validate_request → analyze_image → resolve_product_identity → check_identity_ambiguity → finalize_results`. Runs synchronously and returns the identity for review.
- `full` (`POST /api/searches`): starts from the user-confirmed identity and runs the remaining nodes in the background.

In `full` mode, unclear identity details never stop the search; they become `progress.warnings` and reduce what can be verified. The search only stops (`NEEDS_CLARIFICATION`) when there is nothing to search for. The web UI always runs identify and then search in one go; it has no review page.

```
validate_request ─► analyze_image ─► resolve_product_identity ─► check_identity_ambiguity
        │ (identity supplied)                                          │
        └──────────────────────────────────────────────────────────────┤
                                  needs clarification / identify_only ─┴─► finalize_results
                                                                   │ otherwise
discover_supplier_sources ─► search_supplier_connectors ──(no offers)──► finalize_results
                                       │
extract_and_normalize_offers ─► deduplicate_offers ─► verify_offer_evidence
        ─► calculate_comparable_costs ─► rank_eligible_offers ─► finalize_results
```

Notes and deliberate choices:

- **Only `analyze_image` calls an LLM.** Everything else is deterministic Python.
- **`deduplicate_offers` runs before verification** (the brief lists it after costing). Merging first unions evidence from repeated listings so conflicts are visible to the verification rules.
- **Concurrency.** `search_supplier_connectors` runs connectors concurrently behind a semaphore (`SOURCE_MAX_CONCURRENCY`), with a per-source timeout and limited retries (retries apply to timeouts and temporary errors only). A crashing connector is isolated and reported without its internals.
- **Partial results.** As each source returns, candidates are deduplicated, verified, priced and ranked, then persisted, so the UI can show them immediately. The final pass recomputes everything from all offers, so late, cheaper offers re-rank correctly.
- **The orchestrator owns status.** Connectors return `RawOffer` candidates that have no status field. Only `verify_offer` assigns one.
- **States:** `REQUEST_RECEIVED`, `IDENTIFYING_PRODUCT`, `IDENTITY_READY`*, `NEEDS_CLARIFICATION`, `SEARCHING_SUPPLIERS`, `VERIFYING_OFFERS`, `PARTIAL_RESULTS`, `RESULTS_READY`, `NO_MATCHES`, `SOURCE_UNAVAILABLE`, `FAILED`. (*added: identify-only completion.) `Progress.finished` distinguishes a final `PARTIAL_RESULTS` from an in-flight one.
- **Checkpoints.** Progress (state, sources, counts, completed nodes) is persisted after each node and on every connector completion. It is the single source of truth for status and SSE. On restart, unfinished searches are marked `FAILED` (the workflow is not resumed).
- **Timeouts.** An overall search timeout keeps any partial results (`PARTIAL_RESULTS`) or fails if none exist.

## Progressive updates

`GET /api/searches/{id}/events` is a Server-Sent Events stream that re-reads the persisted state every 500 ms and emits when it changes. This works across restarts and needs no pub/sub. The frontend falls back to 2 s polling if SSE is unavailable.

## Background tasks

`TaskRunner` is an interface; `InProcessTaskRunner` uses `asyncio` tasks. To scale out, implement the interface on a queue (Redis/RQ/Arq/Celery); the workflow only needs `submit(name, coroutine)`. Redis was deliberately not added to the MVP.

## Data model

`Product` (+`ProductIdentifier`) is separate from `Supplier`, `Offer` (unique per supplier+product+listing key), and time-stamped `OfferObservation` rows with `OfferEvidence`. `SearchSession` holds the identity, options and checkpoint; `SearchResult` links a search to offers/observations with the serialised view. Rejected offers keep their evidence for audit. `SupplierSource` is defined for connector registration but is not populated yet.

## Identity, ownership and sessions

There are no accounts in the MVP. The server issues a random 128-bit id in an httpOnly, SameSite=Lax cookie; every search belongs to it, and all reads, SSE streams and deletes check ownership (other sessions get 404). Replace with real authentication before multi-user deployment.

## Security controls

Content-based upload validation; size/pixel limits; metadata stripped by re-encoding; images never persisted; SSRF protection (public-address-only, per-redirect-hop validation, DNS pinning, port/scheme limits, size caps, robots.txt); retrieved web content is parsed only for structured price fields and never sent to an LLM or treated as instructions; secrets redacted from logs; rate limits and per-session search concurrency limits; bounded identity payload sizes; `nosniff`/`no-store` headers; CORS restricted to configured origins. The rate limiter is in-memory and per-process.

## Frontend

Pages (`/`, `/review`, `/searches/:id`, `/history`) over a small shared UI kit (`components/ui`). TanStack Query owns server state; a small zustand store holds the draft (image, options, identity under review). Filtering/sorting logic lives in `lib/offers.ts` (pure, tested). Verification and pricing are never computed in the browser. Outbound links render only for `http(s)` URLs and never for reserved `.invalid` demo hosts.
