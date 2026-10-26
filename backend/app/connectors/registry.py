from dataclasses import dataclass

from app.config import Settings
from app.connectors.base import SupplierConnector
from app.connectors.demo_fixture import DemoFixtureConnector
from app.connectors.page_extraction import PageExtractionConnector
from app.connectors.reference_data import CsvReferenceData, ReferenceDataAdapter
from app.connectors.url_safety import SafeFetcher
from app.connectors.web_discovery import TavilyDiscoveryConnector


@dataclass
class ConnectorSet:
    discovery: list[SupplierConnector]  # sources queried by search_supplier_connectors
    extractor: PageExtractionConnector | None
    reference: ReferenceDataAdapter | None
    unavailable: list[tuple[str, str]]  # (connector name, config hint) for disabled sources


def build_connectors(settings: Settings, fetcher: SafeFetcher | None = None) -> ConnectorSet:
    fetcher = fetcher or SafeFetcher(
        timeout=settings.page_fetch_timeout_seconds,
        max_bytes=settings.page_fetch_max_bytes,
        user_agent=settings.http_user_agent,
        respect_robots=settings.respect_robots,
    )
    candidates: list[SupplierConnector] = [
        TavilyDiscoveryConnector(settings.tavily_api_key, settings.tavily_max_results)
    ]
    if settings.demo_mode:
        candidates.append(DemoFixtureConnector())
    active = [c for c in candidates if c.is_configured()]
    unavailable = [(c.name, c.config_hint()) for c in candidates if not c.is_configured()]
    reference = (
        CsvReferenceData(settings.reference_data_csv) if settings.reference_data_csv else None
    )
    return ConnectorSet(active, PageExtractionConnector(fetcher), reference, unavailable)
