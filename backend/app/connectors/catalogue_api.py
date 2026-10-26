"""Base class for real supplier API / catalogue integrations (none are bundled).

Subclass, implement `search_products` (and optionally the other capability methods), and register it
in `connectors/registry.py`. Return RawOffer with `Evidence(type=API_RESPONSE, api_ref=...)` holding the
fields the API actually returned. Leave unknown fields as None / Availability.UNKNOWN.
"""

from abc import ABC

from app.connectors.base import ConnectorKind, SupplierConnector


class CatalogueApiConnector(SupplierConnector, ABC):
    kind = ConnectorKind.CATALOGUE_API
