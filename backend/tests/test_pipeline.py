from datetime import UTC, datetime
from decimal import Decimal

from app.pricing.fx import FxRate
from app.pricing.pipeline import build_views, deduplicate
from app.schemas.common import BuyingMode
from app.schemas.offers import Audience, Availability
from app.schemas.offers import VerificationStatus as S
from app.schemas.search import SearchOptions
from tests.factories import NOW, aged, api_evidence, medicine, raw_offer, snippet_evidence

D = Decimal


def views(offers, options=None, rates=None, ident=None):
    return build_views(
        ident or medicine(),
        options or SearchOptions(),
        offers,
        target_currency="INR",
        rates=rates or {},
        now=NOW,
        max_age_hours=24,
    )


def sup(name, price, **kw):
    url = f"https://{name}.example/p"
    return raw_offer(
        supplier_name=name,
        supplier_domain=f"{name}.example",
        price=D(price),
        product_url=url,
        evidence=[api_evidence(price=str(price), url=url)],
        **kw,
    )


def test_dedupe_merges_same_listing_and_unions_evidence():
    a = raw_offer(product_url="https://shop.example/p?utm_source=x")
    b = raw_offer(
        product_url="https://shop.example/p/",
        evidence=[api_evidence(url="https://shop.example/p", at=aged(1))],
    )
    merged = deduplicate([a, b])
    assert len(merged) == 1 and merged[0][1] == 1
    assert len(merged[0][0].evidence) == 2


def test_dedupe_never_merges_different_suppliers_or_pack_sizes():
    a = raw_offer(supplier_domain="a.example", product_url=None)
    b = raw_offer(supplier_domain="b.example", product_url=None)
    c = raw_offer(supplier_domain="a.example", product_url=None, pack_units=20)
    assert len(deduplicate([a, b, c])) == 3


def test_duplicate_conflicting_prices_surface_as_conflict():
    a = raw_offer(price=D("24"), evidence=[api_evidence(price="24")])
    b = raw_offer(price=D("30"), evidence=[api_evidence(price="30", at=aged(2))])
    v = views([a, b])[0]
    assert v.tier == S.UNVERIFIED and v.verification.conflicts


def test_ranking_orders_by_tier_then_requested_cost():
    unverified_cheapest = raw_offer(
        supplier_name="snip",
        supplier_domain="snip.example",
        price=D("5"),
        product_url="https://snip.example/p",
        evidence=[snippet_evidence()],
    )
    out = views([sup("exp", "30"), unverified_cheapest, sup("cheap", "20")])
    assert [v.supplier_name for v in out] == ["cheap", "exp", "snip"]
    assert [v.rank for v in out] == [1, 2, 3]
    assert out[2].tier == S.UNVERIFIED


def test_rejected_offers_are_kept_but_ineligible_and_unranked():
    wrong = raw_offer(
        declared={
            "active_ingredients": "Paracetamol",
            "strength": "650 mg",
            "dosage_form": "Tablet",
        }
    )
    v = views([wrong])[0]
    assert v.tier == S.REJECTED and not v.eligible and v.rank is None


def test_price_filters_only_apply_when_set():
    offers = [sup("a", "10"), sup("b", "20"), sup("c", "30")]
    assert all(v.eligible for v in views(offers))
    got = views(offers, SearchOptions(min_price=D("15"), max_price=D("25")))
    assert {v.supplier_name: v.eligible for v in got} == {"a": False, "b": True, "c": False}


def test_price_filter_cannot_evaluate_unconverted_currency():
    o = raw_offer(currency="USD", price=D("1"), evidence=[api_evidence(price="1", currency="USD")])
    v = views([o], SearchOptions(max_price=D("100")))[0]
    assert not v.eligible and any("could not be converted" in r for r in v.ineligible_reasons)


def test_converted_currency_is_ranked_with_rate():
    rates = {"USD": FxRate(D("80"), datetime(2026, 10, 1, tzinfo=UTC), "t")}
    o = raw_offer(currency="USD", price=D("1"), evidence=[api_evidence(price="1", currency="USD")])
    v = views([o], rates=rates)[0]
    assert v.eligible and v.pricing.pack_price == D("80")


def test_retail_mode_excludes_business_only_but_business_mode_keeps_it():
    o = sup("w", "20", audience=Audience.BUSINESS)
    assert not views([o], SearchOptions(mode=BuyingMode.RETAIL))[0].eligible
    assert views([o], SearchOptions(mode=BuyingMode.BUSINESS))[0].eligible


def test_business_fields_hidden_in_retail_mode():
    o = sup("w", "20", lead_time="3 days", credit_terms="net 30")
    assert views([o], SearchOptions(mode=BuyingMode.RETAIL))[0].credit_terms is None
    assert views([o], SearchOptions(mode=BuyingMode.BUSINESS))[0].credit_terms == "net 30"


def test_out_of_stock_ineligible_unknown_stock_stays_unknown():
    assert not views([sup("o", "10", availability=Availability.OUT_OF_STOCK)])[0].eligible
    v = views([sup("u", "10")])[0]
    assert v.availability == Availability.UNKNOWN and v.eligible


def test_quantity_changes_ranking_via_moq():
    out = views([sup("moq", "10", moq_packs=50), sup("small", "12")], SearchOptions(quantity=2))
    assert out[0].supplier_name == "small"
