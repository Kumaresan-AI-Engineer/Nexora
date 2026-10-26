# PharmaSource

AI-assisted pharmacy product identification and supplier price comparison. Upload a photo of a medicine, pharmacy supply or medical equipment; review what was read; compare supplier offers with explicit verification and deterministic pricing. Initial market: India.

PharmaSource is for **discovery and comparison only**. It does not give medical advice, dispense medicines, take payments or place orders. Users are redirected to the supplier.

> Status: MVP. Read [What actually works](#what-actually-works) before relying on any output.

## What actually works

| Area | State | Notes |
|---|---|---|
| Image validation, resizing, EXIF stripping | Implemented, tested | Magic-byte checks, size/pixel limits |
| OpenAI vision adapter (Responses API, structured output) | Implemented, tested; **one live call verified** | A synthetic pack image was read correctly with `gpt-4.1` (2026-10-24). Real-world photos not yet evaluated |
| Gemini vision adapter (JSON schema output) | Implemented, **mock-tested only** | No API key was available; never called live |
| Identity review, ambiguity rules, GTIN validation | Implemented, tested | |
| LangGraph workflow (12 nodes, conditional edges) | Implemented, tested with fake connectors | |
| Verification rules, pricing engine, dedupe, ranking | Implemented, tested | Deterministic Python, no LLM |
| Tavily public-web discovery | Implemented, **mock-tested only** | Needs `TAVILY_API_KEY`; results are candidates, never verified from snippets |
| Product-page extraction (JSON-LD / meta tags) | Implemented, tested with fixtures | SSRF-safe, robots.txt aware; real sites not exercised |
| Supplier API / catalogue connectors | **Interface only** | No real supplier API is integrated (see [docs/SUPPLIER_CONNECTORS.md](docs/SUPPLIER_CONNECTORS.md)) |
| Regulatory reference prices | Interface + CSV adapter | No official data bundled |
| Exchange rates | `none` (default), `static`, `frankfurter` | Frankfurter is mock-tested only |
| Demo connector | Implemented | **Fictional data**, off by default (`DEMO_MODE=true`), never verified |
| PostgreSQL | Models + Alembic migration written | **Not run against Postgres** (no Docker on the build machine); tested on SQLite |
| Checkout / payments / ordering | Not built, by design | |

Without a configured vision key and a discovery source, the UI loads but identification fails with a message naming the missing variables. With `DEMO_MODE=true` you can exercise the search flow using fictional offers (labelled as such everywhere).

## Repository layout

```
backend/    FastAPI app (app/), Alembic migrations, pytest suite (tests/)
frontend/   React + Vite + TypeScript + Tailwind app (src/), Vitest suite
docs/       Plan, architecture, API, connectors, verification & pricing
docker-compose.yml   Local PostgreSQL
```

## Prerequisites

- Python 3.11+ (developed on 3.14), Node 20+ (developed on 24)
- Docker (optional) for local PostgreSQL

## Quick start (Windows)

Double-click `run.bat` (or run it from a terminal). On first run it creates the Python virtual environment, installs backend and frontend dependencies, creates `backend\.env` with a local SQLite database and `DEMO_MODE=true`, applies migrations, then opens the API (http://localhost:8000) and web app (http://localhost:5173) in two windows. Edit `backend\.env` to add provider keys. Close the two windows to stop. Set `NOBROWSER=1` to skip opening the browser.

## Setup

### 1. Database

```bash
docker compose up -d db          # PostgreSQL 16 on localhost:5432
```

No Docker? Use SQLite for local experiments: set `DATABASE_URL=sqlite:///./pharmasource.db`.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate           # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env   (then edit)
alembic upgrade head             # create/upgrade tables
uvicorn app.main:app_factory --factory --reload --port 8000
```

Health: <http://localhost:8000/api/health>, readiness (DB): <http://localhost:8000/api/ready>, capabilities: <http://localhost:8000/api/config>.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173, proxies /api to :8000
```

Set `VITE_API_PROXY` if the backend is not on `http://localhost:8000`.

## Configuring vision providers

Choose model ids from each provider's current documentation. **A provider is "configured" only when both its key and model are set.** The user's selection is always honoured; there is no fallback to the other provider.

| Provider | Variables |
|---|---|
| OpenAI | `OPENAI_API_KEY`, `OPENAI_VISION_MODEL` (must support image input and structured outputs) |
| Gemini | `GEMINI_API_KEY`, `GEMINI_VISION_MODEL` (must support image input and JSON schema responses) |

Keys stay on the server. Quota or billing problems surface as a clear error (HTTP 429); neither provider should be assumed to be free.

## Environment variables

See [backend/.env.example](backend/.env.example) for the full documented list. Key ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL (PostgreSQL via psycopg, or SQLite for experiments) |
| `OPENAI_*`, `GEMINI_*` | Vision providers |
| `TAVILY_API_KEY` | Enables public-web discovery |
| `FX_PROVIDER`, `FX_STATIC_RATES` | `none` / `static` / `frankfurter` currency conversion |
| `DEMO_MODE` | Serve clearly-labelled fictional offers |
| `CORS_ORIGINS`, `COOKIE_SECURE` | Browser access; set `COOKIE_SECURE=true` behind HTTPS |
| `MAX_UPLOAD_MB`, `*_TIMEOUT_SECONDS`, `*_RATE_LIMIT_*` | Limits |
| `LOG_LEVEL` | Structured JSON logging level |

## Running checks

```bash
# backend (from backend/)
python -m pytest tests -q
ruff check . && ruff format --check .

# frontend (from frontend/)
npm run typecheck
npm run lint
npm test
npm run build
```

## Using the app

1. **Upload**: drop a product photo and click *Find offers*. That is all that is required. Under *Optional settings* you can set quantity, a price range, retail or business, India or Global, and the AI provider (a configured one is chosen automatically). Anything you fill in is used.
2. **Watch the agent**: right after upload you see the photo being read and the product identified, then a live *Agent activity* feed on the results page: sources queried, candidates found, each supplier page read, verification and ranking, with timestamps. Every line is a real recorded step, not an animation.
3. **Results**: the search starts automatically. There is no review form. If something on the pack was unclear (for example the pack size), the search still runs with what was readable, the unclear details are flagged on the results page, and offers cannot be marked fully source-verified until the details they depend on are known. Under *What we identified* you can optionally add or correct details and search again. Only if nothing at all could be identified does the search stop and ask for a clearer photo or a typed product name.
4. **Compare**: progress and source failures are shown as they happen. All offers appear in one list, each tagged *Source-verified*, *Partially verified* or *Unverified* (rejected ones are hidden unless you choose them in the Status filter); only direct source evidence can make an offer *Source-verified*. Filter instantly by price range, stock, country or text. Changing quantity, buying mode or market runs a fresh search for the same product. Expand a row for the evidence, checks and full cost breakdown. Links open the supplier's own page.

## Data retention

Uploaded images are processed in memory and **never stored**. Searches, offers, observations and evidence are stored in the database and tied to an anonymous, httpOnly browser-session cookie. Users can delete a search (removes the result rows from their history); offer observation history is kept as shared price history, detached from the search. There is no automatic expiry yet; operators should add a retention job before production use.

## More documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/API.md](docs/API.md)
- [docs/SUPPLIER_CONNECTORS.md](docs/SUPPLIER_CONNECTORS.md)
- [docs/VERIFICATION_AND_PRICING.md](docs/VERIFICATION_AND_PRICING.md)
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
