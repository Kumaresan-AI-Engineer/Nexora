"""Test factories. Everything here is synthetic test data, not market data."""

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from PIL import Image

from app.schemas.identity import (
    ExtractedField,
    ExtractionOutput,
    FieldStatus,
    ProductCategory,
    ProductIdentity,
    ProviderField,
)
from app.schemas.offers import Evidence, EvidenceType, RawOffer

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def cf(value: str | None, status: FieldStatus = FieldStatus.CONFIRMED) -> ExtractedField:
    if value is None:
        return ExtractedField()
    return ExtractedField(value=value, status=status, evidence="test")


def medicine(**over) -> ProductIdentity:
    base = dict(
        category=ProductCategory.MEDICINE,
        generic_name=cf("Paracetamol"),
        active_ingredients=cf("Paracetamol"),
        strength=cf("500 mg"),
        dosage_form=cf("Tablet"),
        pack_quantity=cf("10"),
    )
    base.update(over)
    return ProductIdentity(**base)


def gloves(**over) -> ProductIdentity:
    base = dict(
        category=ProductCategory.SUPPLY,
        product_name=cf("Nitrile examination gloves"),
        material=cf("Nitrile"),
        size_dimensions=cf("M"),
        pack_quantity=cf("100"),
    )
    base.update(over)
    return ProductIdentity(**base)


def api_evidence(
    price="24", currency="INR", at=NOW, url="https://shop.example/p", **extra
) -> Evidence:
    return Evidence(
        type=EvidenceType.API_RESPONSE,
        source_url=url,
        api_ref="api/v1/item/1",
        observed={"price": price, "currency": currency, **extra},
        retrieved_at=at,
    )


def page_evidence(price="24", currency="INR", at=NOW, url="https://shop.example/p") -> Evidence:
    return Evidence(
        type=EvidenceType.PAGE_EXTRACTION,
        source_url=url,
        observed={"price": price, "currency": currency},
        retrieved_at=at,
    )


def snippet_evidence(at=NOW, url="https://shop.example/p") -> Evidence:
    return Evidence(
        type=EvidenceType.SEARCH_SNIPPET,
        source_url=url,
        excerpt="Paracetamol 500 mg ₹24",
        retrieved_at=at,
    )


def raw_offer(**over) -> RawOffer:
    base = dict(
        connector_id="test_api",
        connector_kind="catalogue_api",
        supplier_name="Test Supplier",
        supplier_domain="shop.example",
        title="Paracetamol 500 mg Tablets x 10",
        declared={
            "active_ingredients": "Paracetamol",
            "strength": "500mg",
            "dosage_form": "Tablets",
        },
        pack_units=10,
        price=Decimal("24"),
        currency="INR",
        product_url="https://shop.example/p",
        evidence=[api_evidence()],
    )
    base.update(over)
    return RawOffer(**base)


def aged(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)


def png_bytes(size=(64, 48), color=(200, 30, 30), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=fmt)
    return buf.getvalue()


def extraction(**over) -> ExtractionOutput:
    def pf(v, st=FieldStatus.CONFIRMED):
        return ProviderField(
            value=v, status=st if v else FieldStatus.UNKNOWN, evidence="seen" if v else None
        )

    base = dict(
        category=ProductCategory.MEDICINE,
        readable=True,
        brand_name=pf("Calpol"),
        generic_name=pf("Paracetamol"),
        active_ingredients=pf("Paracetamol"),
        strength=pf("500 mg"),
        dosage_form=pf("Tablet"),
        route=pf("Oral"),
        pack_quantity=pf("10"),
        pack_configuration=pf("10 tablets"),
        manufacturer=pf(None),
        barcode=pf(None),
        product_name=pf(None),
        model_sku=pf(None),
        size_dimensions=pf(None),
        material=pf(None),
        sterile=pf(None),
        certifications=pf(None),
        contradictions=[],
        notes=[],
    )
    base.update(over)
    return ExtractionOutput(**base)


def noisy_png(size=(300, 300)) -> bytes:
    import os

    buf = io.BytesIO()
    Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)).save(buf, format="PNG")
    return buf.getvalue()
