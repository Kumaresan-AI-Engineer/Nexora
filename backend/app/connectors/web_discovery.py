"""Public-web discovery via Tavily. Results are *candidate sources*: snippets, never verified offers."""

import logging
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from app.connectors.base import (
    ConnectorError,
    ConnectorKind,
    ConnectorQuery,
    ConnectorTemporaryError,
    SupplierConnector,
)
from app.schemas.common import Market
from app.schemas.offers import Evidence, EvidenceType, RawOffer

log = logging.getLogger("pharmasource.connectors.tavily")
TAVILY_URL = "https://api.tavily.com/search"


def build_query(query: ConnectorQuery) -> str:
    i = query.identity
    parts = [
        i.value("brand_name") or i.value("product_name") or i.value("generic_name"),
        i.value("active_ingredients") if i.value("brand_name") else None,
        i.value("strength"),
        i.value("dosage_form"),
        i.value("model_sku"),
        i.value("size_dimensions"),
        f"{i.pack_units} pack" if i.pack_units else None,
    ]
    text = " ".join(p for p in parts if p)
    suffix = "buy online price India" if query.market == Market.INDIA else "buy online price"
    return f"{text} {suffix}".strip()


class TavilyDiscoveryConnector(SupplierConnector):
    id = "tavily_web"
    name = "Public web discovery (Tavily)"
    kind = ConnectorKind.WEB_DISCOVERY
    capabilities = frozenset({"search_products"})

    def __init__(
        self,
        api_key: str,
        max_results: int = 8,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._key = api_key
        self._max = max_results
        self._timeout = timeout
        self._transport = transport

    def is_configured(self) -> bool:
        return bool(self._key.strip())

    def config_hint(self) -> str:
        return "Set TAVILY_API_KEY to enable public-web discovery."

    async def search_products(self, query: ConnectorQuery) -> list[RawOffer]:
        body: dict = {
            "query": build_query(query),
            "search_depth": "basic",
            "max_results": self._max,
            "include_answer": False,
            "include_raw_content": False,
        }
        if query.market == Market.INDIA:
            body["country"] = "india"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(
                    TAVILY_URL, json=body, headers={"Authorization": f"Bearer {self._key}"}
                )
        except httpx.TimeoutException as exc:
            raise ConnectorTemporaryError("Tavily request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ConnectorTemporaryError("Could not reach Tavily.") from exc
        if resp.status_code in (401, 403):
            raise ConnectorError("Tavily rejected the configured API key.")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ConnectorTemporaryError(f"Tavily returned HTTP {resp.status_code}.")
        if resp.status_code >= 400:
            raise ConnectorError(f"Tavily returned HTTP {resp.status_code}.")
        try:
            results = resp.json().get("results", [])
        except ValueError as exc:
            raise ConnectorError("Tavily returned invalid JSON.") from exc

        now = datetime.now(UTC)
        offers: list[RawOffer] = []
        seen: set[str] = set()
        for r in results:
            url = r.get("url")
            if (
                not isinstance(url, str)
                or not url.startswith(("http://", "https://"))
                or url in seen
            ):
                continue
            seen.add(url)
            domain = (urlsplit(url).hostname or "").removeprefix("www.")
            title = str(r.get("title") or "")[:300]
            snippet = str(r.get("content") or "")[:600]  # untrusted text: stored as data only
            offers.append(
                RawOffer(
                    connector_id=self.id,
                    connector_kind=self.kind.value,
                    supplier_name=domain,
                    supplier_domain=domain,
                    title=title,
                    product_url=url,
                    needs_page_extraction=True,
                    evidence=[
                        Evidence(
                            type=EvidenceType.SEARCH_SNIPPET,
                            source_url=url,
                            excerpt=snippet,
                            observed={},
                            retrieved_at=now,
                        )
                    ],
                )
            )
        return offers
