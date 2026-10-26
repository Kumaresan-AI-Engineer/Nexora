from app.schemas.identity import FieldStatus
from app.schemas.offers import VerificationStatus as S
from app.verification.rules import verify_offer
from tests.factories import (
    NOW,
    aged,
    api_evidence,
    cf,
    gloves,
    medicine,
    page_evidence,
    raw_offer,
    snippet_evidence,
)

MED_DECL = {"active_ingredients": "Paracetamol", "strength": "500 mg", "dosage_form": "Tablet"}


def v(identity, offer, **kw):
    return verify_offer(identity, offer, now=NOW, **kw)


def decl(**over):
    return {**MED_DECL, **over}


def test_fully_matching_fresh_direct_evidence_is_verified():
    r = v(medicine(), raw_offer())
    assert r.status == S.VERIFIED, r.reasons
    assert r.supplier_verification == "not_independently_verified"


def test_search_snippet_alone_never_verifies():
    r = v(medicine(), raw_offer(evidence=[snippet_evidence()]))
    assert r.status == S.UNVERIFIED
    assert any("snippet" in c.detail for c in r.checks)


def test_no_price_is_unverified_not_rejected():
    r = v(medicine(), raw_offer(price=None, currency=None, evidence=[snippet_evidence()]))
    assert r.status == S.UNVERIFIED and "price or currency" in r.missing


def test_different_strength_is_rejected():
    r = v(medicine(), raw_offer(declared=decl(strength="650 mg")))
    assert r.status == S.REJECTED and any("strength" in x for x in r.reasons)


def test_strength_unit_normalisation_matches_grams():
    assert v(medicine(), raw_offer(declared=decl(strength="0.5 g"))).status == S.VERIFIED


def test_different_active_ingredient_rejected():
    assert (
        v(medicine(), raw_offer(declared=decl(active_ingredients="Ibuprofen"))).status == S.REJECTED
    )


def test_combination_ingredients_compared_as_sets():
    ident = medicine(active_ingredients=cf("Paracetamol + Caffeine"), strength=cf("500 mg + 65 mg"))
    ok = raw_offer(
        declared=decl(active_ingredients="Caffeine / Paracetamol", strength="65mg + 500mg")
    )
    assert v(ident, ok).status == S.VERIFIED
    assert v(ident, raw_offer(declared=decl())).status == S.REJECTED


def test_modified_release_form_is_not_plain_tablet():
    o = raw_offer(declared=decl(dosage_form="Extended release tablet"))
    assert v(medicine(), o).status == S.REJECTED


def test_film_coated_wording_is_not_a_mismatch():
    assert (
        v(medicine(), raw_offer(declared=decl(dosage_form="Film coated tablets"))).status
        == S.VERIFIED
    )


def test_different_brand_is_not_equivalent():
    ident = medicine(brand_name=cf("Calpol"))
    o = raw_offer(declared=decl(brand_name="Dolo"), title="Dolo 500 mg tablets x 10")
    assert v(ident, o).status == S.REJECTED


def test_brand_must_be_stated_to_verify():
    ident = medicine(brand_name=cf("Calpol"))
    assert v(ident, raw_offer()).status == S.PARTIALLY_VERIFIED


def test_unstated_strength_gives_partial_not_verified():
    o = raw_offer(
        declared={"active_ingredients": "Paracetamol", "dosage_form": "Tablet"},
        title="Paracetamol tablets",
    )
    r = v(medicine(), o)
    assert r.status == S.PARTIALLY_VERIFIED and "strength" in r.missing


def test_strength_taken_from_title_when_not_declared():
    base = {"active_ingredients": "Paracetamol", "dosage_form": "Tablet"}
    ok = raw_offer(declared=base, title="Paracetamol 500mg x 10")
    wrong = raw_offer(declared=base, title="Paracetamol 650mg x 10")
    assert v(medicine(), ok).status == S.VERIFIED
    assert v(medicine(), wrong).status == S.REJECTED


def test_different_pack_size_is_comparable_but_noted():
    r = v(medicine(), raw_offer(pack_units=20))
    assert r.status == S.VERIFIED
    assert any(c.name == "match:pack_quantity" and c.result == "info" for c in r.checks)


def test_unknown_offer_pack_blocks_verified():
    assert v(medicine(), raw_offer(pack_units=None)).status == S.PARTIALLY_VERIFIED


def test_stale_evidence_downgrades_to_partial():
    r = v(medicine(), raw_offer(evidence=[api_evidence(at=aged(48))]), max_age_hours=24)
    assert r.status == S.PARTIALLY_VERIFIED and any("older" in x for x in r.reasons)


def test_conflicting_direct_evidence_is_preserved_and_unverified():
    r = v(medicine(), raw_offer(evidence=[api_evidence(price="24"), page_evidence(price="31")]))
    assert r.status == S.UNVERIFIED and r.conflicts


def test_evidence_not_supporting_price_is_unverified():
    assert v(medicine(), raw_offer(evidence=[api_evidence(price="99")])).status == S.UNVERIFIED


def test_evidence_currency_mismatch_conflicts():
    assert v(medicine(), raw_offer(evidence=[api_evidence(currency="USD")])).status == S.UNVERIFIED


def test_non_positive_price_rejected():
    assert (
        v(medicine(), raw_offer(price=0, evidence=[api_evidence(price="0")])).status == S.REJECTED
    )


def test_expired_price_validity_unverified():
    ev = api_evidence(valid_until="2026-01-01")
    assert v(medicine(), raw_offer(evidence=[ev])).status == S.UNVERIFIED


def test_barcode_mismatch_rejected():
    ident = medicine(barcode=cf("4006381333931"))
    o = raw_offer(declared=decl(barcode="036000291452"))
    assert v(ident, o).status == S.REJECTED


def test_demo_offers_can_never_be_verified_but_mismatch_still_rejects():
    assert v(medicine(), raw_offer(is_demo=True)).status == S.UNVERIFIED
    assert (
        v(medicine(), raw_offer(is_demo=True, declared=decl(strength="650 mg"))).status
        == S.REJECTED
    )


def test_missing_source_reference_cannot_be_verified():
    ev = api_evidence().model_copy(update={"api_ref": None, "source_url": None})
    o = raw_offer(product_url=None, evidence=[ev])
    assert v(medicine(), o).status == S.PARTIALLY_VERIFIED


def test_manufacturer_difference_downgrades():
    ident = medicine(manufacturer=cf("Acme Pharma"))
    o = raw_offer(declared=decl(manufacturer="Zenith Labs"))
    assert v(ident, o).status == S.PARTIALLY_VERIFIED


GLOVE_DECL = {
    "product_name": "Nitrile examination gloves",
    "material": "Nitrile",
    "size_dimensions": "M",
}


def test_supply_material_mismatch_rejected():
    o = raw_offer(
        title="Latex examination gloves M box of 100",
        pack_units=100,
        declared={**GLOVE_DECL, "product_name": "Latex examination gloves", "material": "Latex"},
    )
    assert v(gloves(), o).status == S.REJECTED


def test_supply_verified_when_all_specs_match():
    o = raw_offer(title="Nitrile examination gloves M x100", pack_units=100, declared=GLOVE_DECL)
    assert v(gloves(), o).status == S.VERIFIED


def test_supply_sterility_mismatch_rejected():
    o = raw_offer(
        title="Nitrile examination gloves M x100",
        pack_units=100,
        declared={**GLOVE_DECL, "sterile": "sterile"},
    )
    assert v(gloves(sterile=cf("no")), o).status == S.REJECTED


def test_inferred_identity_field_still_used_for_matching():
    # confirmation of inferred fields is enforced earlier, by the ambiguity check
    ident = medicine(strength=cf("500 mg", FieldStatus.INFERRED))
    assert v(ident, raw_offer()).status == S.VERIFIED
