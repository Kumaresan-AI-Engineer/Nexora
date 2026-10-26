"""Demonstration connector. Serves fictional fixture offers and only when DEMO_MODE=true.

Every offer is flagged is_demo, carries FIXTURE evidence, and verification caps it below VERIFIED.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.connectors.base import ConnectorKind, ConnectorQuery, SupplierConnector
from app.schemas.offers import Evidence, EvidenceType, RawOffer
from app.verification.normalize import norm_ingredients, norm_strength, norm_text

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "demo_offers.json"


class DemoFixtureConnector(SupplierConnector):
    id = "demo_fixture"
    name = "Demonstration fixtures (fictional data)"
    kind = ConnectorKind.DEMO_FIXTURE
    is_demo = True

    def __init__(self, path: Path = FIXTURE_PATH):
        self._entries = json.loads(path.read_text(encoding="utf-8"))["entries"]

    def _matches(self, entry_match: dict, query: ConnectorQuery) -> bool:
        ident = query.identity
        if "active_ingredients" in entry_match:
            want = norm_ingredients(entry_match["active_ingredients"])
            have = norm_ingredients(
                ident.value("active_ingredients") or ident.value("generic_name")
            )
            if want != have:
                return False
            if norm_strength(entry_match.get("strength")) != norm_strength(ident.value("strength")):
                return False
            return True
        if "product_name" in entry_match:
            return norm_text(entry_match["product_name"]) in norm_text(ident.value("product_name"))
        return False

    async def search_products(self, query: ConnectorQuery) -> list[RawOffer]:
        now = datetime.now(UTC)
        offers: list[RawOffer] = []
        for entry in self._entries:
            if not self._matches(entry["match"], query):
                continue
            for item in entry["offers"]:
                offers.append(
                    RawOffer(
                        connector_id=self.id,
                        connector_kind=self.kind.value,
                        is_demo=True,
                        evidence=[
                            Evidence(
                                type=EvidenceType.FIXTURE,
                                source_url=item.get("product_url"),
                                api_ref="demo_offers.json",
                                excerpt="DEMONSTRATION DATA - fictional supplier and price.",
                                observed={
                                    "price": str(item.get("price")),
                                    "currency": item.get("currency", ""),
                                },
                                retrieved_at=now,
                            )
                        ],
                        **item,
                    )
                )
        return offers
