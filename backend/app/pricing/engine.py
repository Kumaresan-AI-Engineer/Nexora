"""Deterministic price normalisation. Known costs, estimates and exclusions stay separate."""

import math
from decimal import Decimal

from app.connectors.reference_data import ReferencePrice
from app.pricing.fx import FxRate
from app.schemas.identity import ProductIdentity
from app.schemas.offers import Comparability, OfferPricing, RawOffer

Q = Decimal("0.0001")


def _q(v: Decimal) -> Decimal:
    return v.quantize(Q)


def price_offer(
    offer: RawOffer,
    identity: ProductIdentity,
    *,
    quantity: int,
    target_currency: str,
    rates: dict[str, FxRate],
    reference: ReferencePrice | None = None,
) -> OfferPricing:
    p = OfferPricing(
        currency_original=offer.currency,
        target_currency=target_currency,
        pack_price_original=offer.price,
        mrp_original=offer.mrp,
        offer_pack_units=offer.pack_units,
        moq_packs=offer.moq_packs,
    )

    # --- currency -----------------------------------------------------------------
    cur = (offer.currency or "").upper()
    rate: Decimal | None = None
    if not cur:
        p.notes.append("No currency stated; price cannot be compared.")
    elif cur == target_currency.upper():
        rate = Decimal(1)
        p.fx_rate, p.fx_source = 1.0, "same currency"
    elif cur in rates:
        fx = rates[cur]
        rate = fx.rate
        p.fx_rate, p.fx_observed_at, p.fx_source = float(fx.rate), fx.observed_at, fx.source
        p.notes.append(f"Converted {cur} to {target_currency} at {fx.rate} ({fx.source}).")
    else:
        p.notes.append(
            f"No exchange rate available for {cur}->{target_currency}; original currency retained, "
            "not comparable."
        )

    def conv(v: Decimal | None) -> Decimal | None:
        return _q(v * rate) if v is not None and rate is not None else None

    p.pack_price = conv(offer.price)
    p.mrp = conv(offer.mrp)
    if p.pack_price is not None and p.mrp is not None and p.pack_price > p.mrp:
        p.notes.append("Selling price is above the stated MRP/list price.")

    # --- pack comparability and unit price ----------------------------------------
    iu, ou = identity.pack_units, offer.pack_units
    if iu and ou:
        p.comparability = Comparability.SAME_PACK if iu == ou else Comparability.PACK_DIFFERS
    else:
        p.comparability = Comparability.UNKNOWN_PACK
        p.notes.append(
            "Pack size unknown on the offer or the identified product; no comparable cost."
        )
    if p.pack_price is not None and ou:
        p.unit_price = _q(p.pack_price / ou)

    # --- requested quantity, MOQ and quantity breaks -------------------------------
    if p.pack_price is not None and iu and ou:
        p.requested_units = quantity * iu
        needed = math.ceil(p.requested_units / ou)
        p.packs_needed = needed
        billed = needed
        if offer.moq_packs and offer.moq_packs > needed:
            billed = offer.moq_packs
            p.moq_applied = True
            p.notes.append(f"Minimum order is {offer.moq_packs} packs, above the {needed} needed.")
        pack_price = p.pack_price
        applicable = [b for b in offer.price_breaks if b.min_packs <= billed]
        if applicable and rate is not None:
            best = max(applicable, key=lambda b: b.min_packs)
            pack_price = _q(best.pack_price * rate)
            p.price_break_applied = True
            p.notes.append(f"Source quantity break applied from {best.min_packs} packs.")
        p.requested_cost = _q(pack_price * billed)
        if billed * ou > p.requested_units:
            p.notes.append(f"Buys {billed * ou} units for the {p.requested_units} requested.")

    elif p.pack_price is not None and not iu:
        # The identified product's pack size is unknown: compare the supplier's listed packs as they are.
        p.requested_cost = _q(p.pack_price * quantity)
        p.notes.append(
            "Pack size of the identified product is unknown, so this is ranked by listed pack price "
            f"x {quantity}, not by unit price."
        )

    # --- shipping, tax, totals -----------------------------------------------------
    if offer.shipping_cost is not None and rate is not None:
        p.shipping_cost, p.shipping_status = conv(offer.shipping_cost), "known"
    else:
        p.exclusions.append("Shipping/delivery charge not stated by the source")

    if offer.tax_included is True:
        p.tax_status = "included"
    elif offer.tax_included is False and offer.tax_amount is not None and rate is not None:
        p.tax_status, p.tax_amount = "added", conv(offer.tax_amount)
    elif offer.tax_included is False:
        p.exclusions.append("Tax is not included and the amount is not stated")
    else:
        p.exclusions.append("Tax treatment not stated by the source")

    if p.requested_cost is not None:
        p.estimated_known_total = p.requested_cost + (p.shipping_cost or 0) + (p.tax_amount or 0)
        p.total_is_complete = p.shipping_status == "known" and p.tax_status in ("included", "added")
    if offer.checkout_total is not None and rate is not None:
        p.final_payable = conv(offer.checkout_total)  # only when the source states it

    if (
        reference
        and p.unit_price is not None
        and reference.currency.upper() == target_currency.upper()
    ):
        if p.unit_price > reference.ceiling_price_per_unit:
            p.notes.append(
                f"Unit price exceeds the reference ceiling {reference.ceiling_price_per_unit} "
                f"({reference.source}, as of {reference.as_of or 'unknown date'})."
            )
    return p
