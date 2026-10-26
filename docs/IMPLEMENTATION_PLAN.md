# PharmaSource — Implementation Plan

## Repository findings

`D:\Nexora` was empty (no manifests, no Git history). Environment: Node 24, npm 11, Python 3.14, Git 2.55.
**Docker is not installed on the build machine**, so PostgreSQL could not be exercised locally; backend
tests run against SQLite through the same SQLAlchemy models, and the Compose file is provided but untested here.

## Modules

| Area | Module (backend/app) | Responsibility |
|---|---|---|
| Config/infra | `config.py`, `logging_setup.py`, `db.py`, `errors.py` | env settings, JSON logs, engine/session, uniform errors |
| Domain schemas | `schemas/` | Pydantic v2 models: identity, offers, pricing, search |
| Persistence | `models/`, `repositories/`, `alembic/` | products, suppliers, offers, observations, evidence, searches |
| Vision providers | `providers/` | `VisionProvider` interface, OpenAI + Gemini adapters, registry |
| Identification | `identification/` | image validation, GTIN check, ambiguity rules |
| Connectors | `connectors/` | connector interface, demo fixtures, Tavily discovery, page extraction, reference data, SSRF guard |
| Verification | `verification/` | deterministic product-match, price-evidence and status rules |
| Pricing | `pricing/` | FX, unit/requested/landed cost, dedupe, ranking |
| Workflow | `workflow/` | LangGraph state, nodes, graph, background runner |
| API | `api/` | routes, session cookie, rate limiting |
| Frontend | `frontend/src` | pages, shared UI kit, pure offer logic (`lib/`), API client |

## Phases

1. **Foundation** — scaffolding, config, DB models + migration, health, design system.
2. **Identification** — upload validation, providers, structured extraction, review UI.
3. **Workflow** — LangGraph nodes, conditional edges, connectors, bounded concurrency, partial results.
4. **Evidence & comparison** — verification rules, pricing, dedupe, ranking.
5. **Product UI** — search flow, comparison table, modes, filters, progress/empty/error states.
6. **Hardening** — security review, lint/type/test/build, documentation.

## Key decisions

- One LangGraph graph, 12 explicit nodes, deterministic Python for everything except image analysis.
- The same graph runs in `identify_only` mode (stops after the ambiguity check) and `full` mode.
- Verification is rule-based; there is no AI confidence score in status decisions.
- Progress is persisted as a checkpoint on the search row; SSE streams the persisted state (works across restarts, no pub/sub infra).
- Background work uses an in-process `TaskRunner` abstraction; a Redis/worker implementation can replace it.
- Anonymous, server-issued httpOnly session cookie scopes searches (no accounts in the MVP).
- Uploaded images are processed in memory and never stored.

## Risks

- Real supplier APIs/credentials are unavailable → only interfaces, Tavily discovery and JSON-LD page extraction are live-capable; the demo connector is labeled fictional.
- Web pages vary; JSON-LD extraction will verify only a minority of pages. Unverifiable offers stay `UNVERIFIED`.
- Provider structured-output behaviour differs per SDK version → adapters are tested with mocks only, live calls unverified without keys.
- No Docker locally → PostgreSQL path untested here.

## Test strategy

Pytest with mocks/fixtures (no paid calls): validation, provider routing/errors, identity rules, verification, pricing, dedupe, ranking, workflow transitions (incl. connector timeouts/failures), SSRF, session ownership.
Vitest + Testing Library for upload, provider/mode selection, filters/sorting, status labels, states and external links.
