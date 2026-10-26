"""Stable supplier-connector interface.

Optional capabilities have safe defaults that return "unknown"/None rather than fabricated values.
Connectors return *candidates* (RawOffer). Only the verification module assigns a status.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.schemas.common import BuyingMode, Market
from app.schemas.identity import ProductIdentity
from app.schemas.offers import Availability, RawOffer


class ConnectorKind(StrEnum):
    CATALOGUE_API = "catalogue_api"
    WEB_DISCOVERY = "web_discovery"
    PAGE_EXTRACTION = "page_extraction"
    REFERENCE_DATA = "reference_data"
    DEMO_FIXTURE = "demo_fixture"


class ConnectorError(Exception):
    """Permanent failure for this source."""


class ConnectorTemporaryError(ConnectorError):
    """Retryable failure (network blip, 5xx, rate limit)."""


@dataclass(frozen=True)
class ConnectorQuery:
    identity: ProductIdentity
    market: Market
    mode: BuyingMode
    quantity: int


class SupplierConnector(ABC):
    id: str
    name: str
    kind: ConnectorKind
    is_demo: bool = False
    markets: frozenset[Market] = frozenset({Market.INDIA, Market.GLOBAL})
    capabilities: frozenset[str] = frozenset({"search_products"})

    def is_configured(self) -> bool:
        return True

    def config_hint(self) -> str:
        return ""

    @abstractmethod
    async def search_products(self, query: ConnectorQuery) -> list[RawOffer]: ...

    async def get_offer_details(self, offer: RawOffer) -> RawOffer | None:
        return None

    async def get_supplier_details(self, supplier_name: str) -> dict | None:
        return None

    async def check_availability(self, offer: RawOffer) -> Availability:
        return Availability.UNKNOWN
