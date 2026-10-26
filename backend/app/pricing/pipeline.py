"""Pure offer pipeline: dedupe -> verify -> price -> eligibility -> rank."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.connectors.reference_data import ReferencePrice
from app.pricing.engine import price_offer
from app.pricing.fx import FxRate
from app.schemas.common import BuyingMode
from app.schemas.identity import ProductIdentity
from app.schemas.offers import (
    Audience,
    Availability,
    OfferPricing,
    OfferView,
    RawOffer,
    VerificationResult,
    VerificationStatus,
)
from app.schemas.search import SearchOptions
from app.verification.normalize import canonical_url, norm_text
from app.verification.rules import verify_offer

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_NAMESPACE = uuid.UUID("5c1b2f64-0a4e-4d52-9d52-8d1a7a0c3f11")
TIER_ORDER = {
    VerificationStatus.VERIFIED: 0,
    VerificationStatus.PARTIALLY_VERIFIED: 1,
    VerificationStatus.UNVERIFIED: 2,
    VerificationStatus.REJECTED: 3,
}


def supplier_key(o: RawOffer) -> str:
    return (o.supplier_domain or "").lower().removeprefix("www.") or norm_text(o.supplier_name)


def listing_key(o: RawOffer) -> str:
    base = canonical_url(o.product_url) or f"title:{norm_text(o.title)}"
    return f"{base}|{o.pack_units or 'unknown'}"


def offer_id_for(o: RawOffer) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{supplier_key(o)}|{listing_key(o)}"))


def deduplicate(offers: list[RawOffer]) -> list[tuple[RawOffer, int]]:
    """Merge repeated listings of the same supplier + listing + pack size. Returns (offer, merged_count).

    Different suppliers or different pack sizes are never merged. Evidence is unioned so conflicting
    observations remain visible to verification.
    """
    groups: dict[str, list[RawOffer]] = {}
    for o in offers:
        groups.setdefault(offer_id_for(o), []).append(o)
    merged: list[tuple[RawOffer, int]] = []
    for group in groups.values():

        def newest(x: RawOffer) -> datetime:
            return max((e.retrieved_at for e in x.evidence), default=_EPOCH)

        group.sort(key=lambda x: (x.price is not None, newest(x)), reverse=True)
        base = group[0].model_copy(deep=True)
        for extra in group[1:]:
            seen = {(e.type, e.source_url, e.retrieved_at) for e in base.evidence}
            base.evidence.extend(
                e for e in extra.evidence if (e.type, e.source_url, e.retrieved_at) not in seen
            )
            if base.price is None and extra.price is not None:
                base = base.model_copy(update={"price": extra.price, "currency": extra.currency})
        merged.append((base, len(group) - 1))
    return merged


def _eligibility(view: OfferView, options: SearchOptions) -> list[str]:
    reasons: list[str] = []
    pr = view.pricing
    if view.tier == VerificationStatus.REJECTED:
        reasons.append("Rejected: does not match the identified product or has invalid data")
    if options.mode == BuyingMode.RETAIL and view.audience == Audience.BUSINESS:
        reasons.append("Business-only listing (not available in retail mode)")
    if view.availability == Availability.OUT_OF_STOCK:
        reasons.append("Listed as out of stock")
    if pr.pack_price is None and pr.pack_price_original is not None:
        reasons.append(
            f"Price in {pr.currency_original or 'unknown currency'} could not be converted"
        )
    if pr.pack_price_original is None:
        reasons.append("No price stated")
    if pr.requested_cost is None and pr.pack_price is not None:
        reasons.append("No comparable cost (pack size unknown)")
    if options.min_price is not None or options.max_price is not None:
        if pr.pack_price is None:
            reasons.append("Price filter cannot be evaluated without a converted price")
        else:
            if options.min_price is not None and pr.pack_price < options.min_price:
                reasons.append("Below the minimum price filter")
            if options.max_price is not None and pr.pack_price > options.max_price:
                reasons.append("Above the maximum price filter")
    return reasons


def verify_all(
    identity: ProductIdentity,
    deduped: list[tuple[RawOffer, int]],
    now: datetime,
    max_age_hours: float,
) -> dict[str, VerificationResult]:
    return {
        offer_id_for(o): verify_offer(identity, o, now=now, max_age_hours=max_age_hours)
        for o, _ in deduped
    }


def price_all(
    identity: ProductIdentity,
    options: SearchOptions,
    deduped: list[tuple[RawOffer, int]],
    *,
    target_currency: str,
    rates: dict[str, FxRate],
    reference: ReferencePrice | None = None,
) -> dict[str, OfferPricing]:
    return {
        offer_id_for(o): price_offer(
            o,
            identity,
            quantity=options.quantity,
            target_currency=target_currency,
            rates=rates,
            reference=reference,
        )
        for o, _ in deduped
    }


def assemble_views(
    deduped: list[tuple[RawOffer, int]],
    verifications: dict[str, VerificationResult],
    pricings: dict[str, OfferPricing],
    options: SearchOptions,
) -> list[OfferView]:
    views: list[OfferView] = []
    for offer, merged in deduped:
        oid = offer_id_for(offer)
        verification, pricing = verifications[oid], pricings[oid]
        retrieved = [e.retrieved_at for e in offer.evidence]
        updated = [e.source_updated_at for e in offer.evidence if e.source_updated_at]
        business = options.mode == BuyingMode.BUSINESS
        view = OfferView(
            offer_id=oid,
            supplier_name=offer.supplier_name,
            supplier_country=offer.supplier_country,
            supplier_domain=offer.supplier_domain,
            connector_id=offer.connector_id,
            is_demo=offer.is_demo,
            title=offer.title,
            declared=offer.declared,
            product_url=offer.product_url,
            enquiry_url=offer.enquiry_url,
            availability=offer.availability,
            availability_source=offer.availability_source,
            delivery_estimate=offer.delivery_estimate,
            audience=offer.audience,
            prescription_required=offer.prescription_required,
            lead_time=offer.lead_time if business else None,
            credit_terms=offer.credit_terms if business else None,
            verification=verification,
            pricing=pricing,
            tier=verification.status,
            eligible=True,
            source_retrieved_at=max(retrieved, default=None),
            source_updated_at=max(updated, default=None),
            evidence=offer.evidence,
            duplicates_merged=merged,
        )
        view.ineligible_reasons = _eligibility(view, options)
        view.eligible = not view.ineligible_reasons
        views.append(view)
    return rank(views)


def build_views(
    identity: ProductIdentity,
    options: SearchOptions,
    raw_offers: list[RawOffer],
    *,
    target_currency: str,
    rates: dict[str, FxRate],
    now: datetime,
    max_age_hours: float,
    reference: ReferencePrice | None = None,
) -> list[OfferView]:
    """Convenience composition of the individual pipeline steps (used for partial results/tests)."""
    deduped = deduplicate(raw_offers)
    return assemble_views(
        deduped,
        verify_all(identity, deduped, now, max_age_hours),
        price_all(
            identity,
            options,
            deduped,
            target_currency=target_currency,
            rates=rates,
            reference=reference,
        ),
        options,
    )


def rank(views: list[OfferView]) -> list[OfferView]:
    """Eligible offers first: verification tier, then requested cost, unit price, supplier name."""

    def key(v: OfferView):
        p = v.pricing
        return (
            0 if v.eligible else 1,
            TIER_ORDER[v.tier],
            p.requested_cost if p.requested_cost is not None else Decimal("Infinity"),
            p.unit_price if p.unit_price is not None else Decimal("Infinity"),
            v.supplier_name.lower(),
        )

    ordered = sorted(views, key=key)
    n = 0
    for v in ordered:
        if v.eligible:
            n += 1
            v.rank = n
        else:
            v.rank = None
    return ordered
