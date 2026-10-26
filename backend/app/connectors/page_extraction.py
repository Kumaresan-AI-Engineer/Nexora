"""Direct product-page extraction from structured data (JSON-LD / meta tags). No LLM, no script execution.

Page text is untrusted: only machine-readable price/availability fields are read, and only after the
SafeFetcher has applied SSRF, robots.txt and size restrictions.
"""

import json
import logging
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

from app.connectors.base import ConnectorKind, ConnectorQuery, SupplierConnector
from app.connectors.url_safety import FetchBlockedError, FetchError, SafeFetcher, UnsafeURLError
from app.schemas.offers import Availability, Evidence, EvidenceType, RawOffer

log = logging.getLogger("pharmasource.connectors.page")

_AVAIL = {
    "instock": Availability.IN_STOCK,
    "onlineonly": Availability.IN_STOCK,
    "limitedavailability": Availability.LIMITED,
    "outofstock": Availability.OUT_OF_STOCK,
    "soldout": Availability.OUT_OF_STOCK,
    "discontinued": Availability.OUT_OF_STOCK,
}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.jsonld: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_ld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag == "meta":
            key = a.get("property") or a.get("name") or a.get("itemprop")
            if key and "content" in a:
                self.meta.setdefault(key.lower(), a["content"])

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self.jsonld.append("".join(self._buf))
            self._in_ld = False


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def _types(node: dict) -> set[str]:
    t = node.get("@type", [])
    return {x.lower() for x in ([t] if isinstance(t, str) else t) if isinstance(x, str)}


def _price(v) -> Decimal | None:
    try:
        d = Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


def _availability(v) -> Availability:
    if not isinstance(v, str):
        return Availability.UNKNOWN
    return _AVAIL.get(v.rsplit("/", 1)[-1].lower(), Availability.UNKNOWN)


def parse_product_page(html: str) -> dict | None:
    """Return {name, sku, gtin, brand, price, currency, availability, valid_until} or None."""
    col = _Collector()
    col.feed(html)
    for raw in col.jsonld:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for node in _walk(data):
            if "product" not in _types(node):
                continue
            offers = node.get("offers")
            offer = (
                next((o for o in _walk(offers) if isinstance(o, dict)), None) if offers else None
            )
            if not offer:
                continue
            price = _price(offer.get("price") or offer.get("lowPrice"))
            currency = offer.get("priceCurrency")
            if price is None or not isinstance(currency, str) or not currency.strip():
                continue
            brand = node.get("brand")
            return {
                "name": str(node.get("name") or "")[:300],
                "sku": str(node.get("sku") or node.get("mpn") or "")[:100] or None,
                "gtin": next(
                    (
                        str(node[k])
                        for k in ("gtin", "gtin13", "gtin12", "gtin14", "gtin8")
                        if node.get(k)
                    ),
                    None,
                ),
                "brand": (brand.get("name") if isinstance(brand, dict) else brand) or None,
                "price": price,
                "currency": currency.strip().upper()[:8],
                "availability": _availability(offer.get("availability")),
                "valid_until": offer.get("priceValidUntil"),
            }
    price = _price(col.meta.get("product:price:amount") or col.meta.get("og:price:amount"))
    currency = col.meta.get("product:price:currency") or col.meta.get("og:price:currency")
    if price is not None and currency:
        return {
            "name": col.meta.get("og:title", "")[:300],
            "sku": None,
            "gtin": None,
            "brand": None,
            "price": price,
            "currency": currency.strip().upper()[:8],
            "availability": _availability(col.meta.get("product:availability")),
            "valid_until": None,
        }
    return None


_PACK = re.compile(
    r"(\d{1,5})\s*(?:'?s\b|tablets?|tabs?|capsules?|caps?|pcs|pieces|count|ct)", re.I
)


def pack_units_from_title(title: str) -> int | None:
    m = _PACK.search(title)
    return int(m.group(1)) if m else None


class PageExtractionConnector(SupplierConnector):
    """Enriches discovery candidates. It discovers nothing itself."""

    id = "page_extraction"
    name = "Direct product-page extraction (JSON-LD)"
    kind = ConnectorKind.PAGE_EXTRACTION
    capabilities = frozenset({"get_offer_details"})

    def __init__(self, fetcher: SafeFetcher):
        self._fetcher = fetcher

    async def search_products(self, query: ConnectorQuery) -> list[RawOffer]:
        return []

    async def get_offer_details(self, offer: RawOffer) -> RawOffer | None:
        """Return an enriched copy, or None when the page yields no usable structured price."""
        if not offer.product_url:
            return None
        try:
            result = await self._fetcher.fetch(offer.product_url)
        except (FetchBlockedError, FetchError, UnsafeURLError) as exc:
            log.info("page extraction skipped: %s", type(exc).__name__)
            return None
        if result.status != 200 or result.truncated and not result.body:
            return None
        parsed = parse_product_page(result.body.decode("utf-8", "replace"))
        if not parsed:
            return None
        now = datetime.now(UTC)
        title = parsed["name"] or offer.title
        declared = dict(offer.declared)
        declared.update(
            {
                "product_name": parsed["name"] or None,
                "model_sku": parsed["sku"],
                "brand_name": parsed["brand"],
                "barcode": parsed["gtin"],
            }
        )
        evidence = Evidence(
            type=EvidenceType.PAGE_EXTRACTION,
            source_url=result.url,
            excerpt=f"Structured data: {title}"[:600],
            observed={
                "price": str(parsed["price"]),
                "currency": parsed["currency"],
                "availability": parsed["availability"].value,
                **({"valid_until": str(parsed["valid_until"])} if parsed["valid_until"] else {}),
            },
            retrieved_at=now,
        )
        return offer.model_copy(
            update={
                "title": title,
                "declared": declared,
                "pack_units": offer.pack_units or pack_units_from_title(title),
                "price": parsed["price"],
                "currency": parsed["currency"],
                "availability": parsed["availability"],
                "availability_source": "product page structured data"
                if parsed["availability"] != Availability.UNKNOWN
                else None,
                "needs_page_extraction": False,
                "evidence": [*offer.evidence, evidence],
            }
        )
