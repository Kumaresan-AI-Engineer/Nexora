"""Exchange-rate providers. Rates are never invented: unavailable means no conversion."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

log = logging.getLogger("pharmasource.fx")


@dataclass(frozen=True)
class FxRate:
    rate: Decimal
    observed_at: datetime
    source: str


class FxProvider(ABC):
    @abstractmethod
    async def get_rate(self, base: str, quote: str) -> FxRate | None: ...


class NoFx(FxProvider):
    async def get_rate(self, base: str, quote: str) -> FxRate | None:
        return None


class StaticFx(FxProvider):
    """Operator-configured rates, e.g. FX_STATIC_RATES="USD>INR=83.10,EUR>INR=90.2"."""

    def __init__(self, spec: str):
        self._rates: dict[tuple[str, str], Decimal] = {}
        self._loaded_at = datetime.now(UTC)
        for item in filter(None, (s.strip() for s in spec.split(","))):
            try:
                pair, value = item.split("=")
                base, quote = pair.split(">")
                self._rates[(base.strip().upper(), quote.strip().upper())] = Decimal(value)
            except (ValueError, InvalidOperation):
                log.warning("ignoring malformed FX_STATIC_RATES entry")

    async def get_rate(self, base: str, quote: str) -> FxRate | None:
        rate = self._rates.get((base.upper(), quote.upper()))
        return FxRate(rate, self._loaded_at, "static-config") if rate else None


class FrankfurterFx(FxProvider):
    """Frankfurter (ECB reference rates), no API key. Cached for an hour."""

    URL = "https://api.frankfurter.dev/v1/latest"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, ttl: float = 3600.0):
        self._transport = transport
        self._ttl = ttl
        self._cache: dict[tuple[str, str], tuple[float, FxRate]] = {}

    async def get_rate(self, base: str, quote: str) -> FxRate | None:
        key = (base.upper(), quote.upper())
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        try:
            async with httpx.AsyncClient(timeout=8.0, transport=self._transport) as client:
                resp = await client.get(self.URL, params={"base": key[0], "symbols": key[1]})
            resp.raise_for_status()
            data = resp.json()
            rate = FxRate(
                Decimal(str(data["rates"][key[1]])), datetime.now(UTC), "frankfurter (ECB)"
            )
        except (httpx.HTTPError, KeyError, ValueError, InvalidOperation):
            return None
        self._cache[key] = (time.monotonic(), rate)
        return rate


def make_fx_provider(kind: str, static_spec: str) -> FxProvider:
    if kind == "static":
        return StaticFx(static_spec)
    if kind == "frankfurter":
        return FrankfurterFx()
    return NoFx()
