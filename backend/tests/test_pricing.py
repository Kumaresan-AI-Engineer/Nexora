from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.pricing.engine import price_offer
from app.pricing.fx import FrankfurterFx, FxRate, NoFx, StaticFx
from app.schemas.identity import ExtractedField
from app.schemas.offers import Comparability, PriceBreak
from tests.factories import medicine, raw_offer

D = Decimal
USD = FxRate(D("80"), datetime(2026, 10, 1, tzinfo=UTC), "test")


def price(offer, qty=1, rates=None, ident=None, target="INR"):
    return price_offer(
        offer, ident or medicine(), quantity=qty, target_currency=target, rates=rates or {}
    )


def test_same_pack_unit_and_requested_cost():
    p = price(raw_offer(price=D("24")), qty=3)
    assert p.comparability == Comparability.SAME_PACK
    assert p.unit_price == D("2.4")
    assert p.packs_needed == 3 and p.requested_cost == D("72")


def test_different_pack_compared_via_unit_price_and_overbuy_noted():
    # qty 3 x identity pack 10 = 30 units; offer pack 20 -> 2 packs (40 units)
    p = price(raw_offer(pack_units=20, price=D("40")), qty=3)
    assert p.comparability == Comparability.PACK_DIFFERS
    assert p.unit_price == D("2") and p.packs_needed == 2 and p.requested_cost == D("80")
    assert any("Buys 40 units" in n for n in p.notes)


def test_unknown_pack_gives_no_requested_cost():
    p = price(raw_offer(pack_units=None))
    assert p.comparability == Comparability.UNKNOWN_PACK
    assert p.requested_cost is None and p.unit_price is None


def test_unknown_identity_pack_ranks_by_listed_pack_price_and_says_so():
    p = price(raw_offer(price=D("24")), qty=3, ident=medicine(pack_quantity=ExtractedField()))
    assert p.requested_cost == D("72") and p.comparability == Comparability.UNKNOWN_PACK
    assert any("Pack size of the identified product is unknown" in n for n in p.notes)


def test_moq_raises_billed_quantity():
    p = price(raw_offer(moq_packs=5, price=D("20")), qty=2)
    assert p.moq_applied and p.packs_needed == 2 and p.requested_cost == D("100")


def test_quantity_break_only_when_source_provides_and_threshold_met():
    o = raw_offer(price=D("20"), price_breaks=[PriceBreak(min_packs=10, pack_price=D("15"))])
    below = price(o, qty=9)
    assert below.requested_cost == D("180") and not below.price_break_applied
    at = price(o, qty=10)
    assert at.price_break_applied and at.requested_cost == D("150")


def test_no_discount_invented_for_large_quantity():
    assert price(raw_offer(price=D("20")), qty=1000).requested_cost == D("20000")


def test_missing_shipping_and_tax_are_exclusions_and_total_incomplete():
    p = price(raw_offer())
    assert not p.total_is_complete and p.final_payable is None
    assert any("Shipping" in e for e in p.exclusions) and any("Tax" in e for e in p.exclusions)
    assert p.estimated_known_total == p.requested_cost


def test_known_shipping_and_tax_included_completes_total():
    p = price(raw_offer(price=D("24"), shipping_cost=D("40"), tax_included=True))
    assert p.total_is_complete and p.estimated_known_total == D("64")


def test_tax_added_amount_included_in_known_total():
    p = price(
        raw_offer(price=D("100"), shipping_cost=D("0"), tax_included=False, tax_amount=D("5"))
    )
    assert p.tax_status == "added" and p.estimated_known_total == D("105") and p.total_is_complete


def test_tax_excluded_without_amount_is_flagged():
    p = price(raw_offer(tax_included=False, shipping_cost=D("0")))
    assert not p.total_is_complete and any("amount is not stated" in e for e in p.exclusions)


def test_final_payable_only_from_source_checkout_total():
    assert price(raw_offer(checkout_total=D("77"))).final_payable == D("77")
    assert price(raw_offer()).final_payable is None


def test_currency_conversion_records_rate():
    p = price(raw_offer(price=D("1"), currency="USD"), rates={"USD": USD})
    assert p.pack_price == D("80") and p.fx_rate == 80.0 and p.fx_source == "test"
    assert p.fx_observed_at is not None


def test_missing_rate_keeps_original_and_flags():
    p = price(raw_offer(price=D("1"), currency="USD"))
    assert p.pack_price is None and p.pack_price_original == D("1")
    assert p.requested_cost is None and any("No exchange rate" in n for n in p.notes)


def test_mrp_kept_separate_and_over_mrp_flagged():
    p = price(raw_offer(price=D("30"), mrp=D("25")))
    assert p.mrp == D("25") and p.pack_price == D("30")
    assert any("above the stated MRP" in n for n in p.notes)


async def test_static_fx_parsing_and_no_fx():
    fx = StaticFx("USD>INR=83.1, bad, EUR>INR=x")
    assert (await fx.get_rate("usd", "inr")).rate == D("83.1")
    assert await fx.get_rate("EUR", "INR") is None
    assert await NoFx().get_rate("USD", "INR") is None


async def test_frankfurter_parses_caches_and_handles_failure():
    calls = []

    def handler(req: httpx.Request):
        calls.append(req)
        return httpx.Response(200, json={"base": "USD", "rates": {"INR": 83.5}})

    fx = FrankfurterFx(transport=httpx.MockTransport(handler))
    r = await fx.get_rate("USD", "INR")
    assert r.rate == D("83.5") and r.source.startswith("frankfurter")
    await fx.get_rate("USD", "INR")
    assert len(calls) == 1

    bad = FrankfurterFx(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await bad.get_rate("USD", "INR") is None
