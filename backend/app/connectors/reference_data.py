"""Government / regulatory reference-price interface (e.g. ceiling prices).

Reference prices are context, not supplier offers. No official source is bundled: operators supply
a CSV with columns active_ingredients,strength,dosage_form,ceiling_price_per_unit,currency,source,as_of,source_url
via REFERENCE_DATA_CSV. Without it this adapter is disabled.
"""

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.schemas.identity import ProductIdentity
from app.verification.normalize import norm_form, norm_ingredients, norm_strength


@dataclass(frozen=True)
class ReferencePrice:
    ceiling_price_per_unit: Decimal
    currency: str
    source: str
    as_of: str
    source_url: str | None


class ReferenceDataAdapter(ABC):
    @abstractmethod
    def lookup(self, identity: ProductIdentity) -> ReferencePrice | None: ...


class CsvReferenceData(ReferenceDataAdapter):
    def __init__(self, path: str):
        self._rows: list[dict] = []
        if path and Path(path).is_file():
            with open(path, newline="", encoding="utf-8") as fh:
                self._rows = list(csv.DictReader(fh))

    def lookup(self, identity: ProductIdentity) -> ReferencePrice | None:
        ing = norm_ingredients(identity.value("active_ingredients"))
        strength = norm_strength(identity.value("strength"))
        form = norm_form(identity.value("dosage_form"))
        if not (ing and strength and form):
            return None
        for row in self._rows:
            if (
                norm_ingredients(row.get("active_ingredients")) == ing
                and norm_strength(row.get("strength")) == strength
                and norm_form(row.get("dosage_form")) == form
            ):
                try:
                    price = Decimal(row["ceiling_price_per_unit"])
                except (InvalidOperation, KeyError):
                    continue
                return ReferencePrice(
                    price,
                    row.get("currency", ""),
                    row.get("source", "reference data"),
                    row.get("as_of", ""),
                    row.get("source_url") or None,
                )
        return None
