# Supplier connectors

## Status of integrations

| Connector | Kind | Status |
|---|---|---|
| `TavilyDiscoveryConnector` (`tavily_web`) | web discovery | Implemented; needs `TAVILY_API_KEY`; mock-tested, not run live |
| `PageExtractionConnector` | page extraction | Implemented (JSON-LD/meta price extraction); fixture-tested, not run against real sites |
| `DemoFixtureConnector` (`demo_fixture`) | demo | Implemented; **fictional**; only with `DEMO_MODE=true` |
| `CsvReferenceData` | reference data | Implemented as an adapter; no official data bundled |
| `CatalogueApiConnector` | supplier API | **Base class only.** No real supplier API is integrated |

No supplier API, price, URL, stock level or credential in this repository is real, other than what a configured live source returns at run time.

## Interface (`backend/app/connectors/base.py`)

```python
class SupplierConnector(ABC):
    id: str; name: str; kind: ConnectorKind; is_demo: bool; markets: frozenset[Market]
    def is_configured(self) -> bool
    def config_hint(self) -> str
    async def search_products(self, query: ConnectorQuery) -> list[RawOffer]      # required
    async def get_offer_details(self, offer: RawOffer) -> RawOffer | None          # default None
    async def get_supplier_details(self, supplier_name: str) -> dict | None        # default None
    async def check_availability(self, offer: RawOffer) -> Availability            # default UNKNOWN
```

Optional capabilities default to "unknown"/`None`; a source that cannot report stock must leave `Availability.UNKNOWN`. Raise `ConnectorTemporaryError` for retryable failures (timeouts, 5xx, rate limits) and `ConnectorError` for permanent ones (bad credentials). The orchestrator applies timeouts, bounded retries and concurrency; connectors should not.

A connector returns **candidates** (`RawOffer`). It cannot set a verification status: that field does not exist on `RawOffer`.

## Writing a real supplier connector

1. Subclass `CatalogueApiConnector`; set `id`, `name`, `markets`, `is_configured()` (credentials present) and `config_hint()`.
2. In `search_products`, call the supplier's documented API and map the response to `RawOffer`: price, `currency`, `pack_units`, `moq_packs`, `price_breaks` (only if the API returns them), `shipping_cost`/`tax_included`/`tax_amount` (only if stated), `availability` (only if stated), `product_url` or `api_ref`, and a **direct** `Evidence(type=API_RESPONSE, api_ref=..., observed={"price": ..., "currency": ...}, retrieved_at=now)`. Put the attributes the supplier states in `declared`.
3. Leave unknown values as `None`/`UNKNOWN`. Never fill from an LLM or from defaults.
4. Register it in `connectors/registry.py` (`candidates`).
5. Add fixture-based tests (deterministic, no credentials) like `tests/test_connectors.py`.

Only evidence of type `api_response` or `page_extraction` counts as direct price evidence; a connector claiming a price with no such evidence ends up `UNVERIFIED`.

## Web discovery and page extraction

Tavily (`POST https://api.tavily.com/search`, bearer auth; checked against Tavily's documentation) supplies URLs and snippets only. Each result becomes a candidate with `needs_page_extraction=True` and snippet evidence, which cannot verify anything.

`extract_and_normalize_offers` then asks `PageExtractionConnector` to read each URL through `SafeFetcher`:

- public `http`/`https` only, ports 80/443, no embedded credentials, no internal hostnames;
- every resolved address must be globally routable (loopback, private, link-local incl. cloud metadata, multicast, reserved and IPv4-mapped IPv6 are refused), re-checked on each redirect (max 3), with the connection pinned to the validated IP;
- `robots.txt` is honoured (disallowed, forbidden or unreachable robots → no fetch); no CAPTCHA/login/anti-bot bypass;
- response size capped, content types restricted to HTML/JSON/text.

Only machine-readable data is read (schema.org `Product`/`Offer` JSON-LD, or `product:price:*` meta tags). Page text is never given to an LLM and instructions embedded in a page have no effect. Pages without structured price data stay unverified and are listed under "Unresolved".

## Reference data (regulated prices)

`ReferenceDataAdapter.lookup(identity) -> ReferencePrice | None`. `CsvReferenceData` reads `REFERENCE_DATA_CSV` with columns `active_ingredients,strength,dosage_form,ceiling_price_per_unit,currency,source,as_of,source_url`. A match adds a note when an offer's unit price exceeds the ceiling (same currency only). Reference prices are context, never offers. Supply data from an official source and keep `as_of` accurate.

## Compliance notes

Respect each supplier's terms and rate limits, and prefer official APIs. Prescription-only status and import rules are only shown when a source states them; the app does not decide legality.
