from app.identification.rules import check_ambiguity, gtin_valid, identity_from_extraction
from app.schemas.identity import FieldStatus, ProductCategory, ProviderField
from tests.factories import cf, extraction, gloves, medicine


def test_gtin_checksums():
    assert gtin_valid("4006381333931")
    assert gtin_valid("036000291452")
    assert not gtin_valid("4006381333932")
    assert not gtin_valid("12345")
    assert not gtin_valid("40063813339ab")


def test_invalid_barcode_is_discarded_not_guessed():
    bad = ProviderField(value="4006381333932", status=FieldStatus.CONFIRMED, evidence="barcode")
    ident = identity_from_extraction(extraction(barcode=bad), "openai:m")
    assert ident.barcode.status == FieldStatus.UNKNOWN and ident.barcode.value is None
    assert any("check-digit" in n for n in ident.notes)


def test_valid_barcode_kept():
    good = ProviderField(value="4006381333931", status=FieldStatus.CONFIRMED, evidence="barcode")
    ident = identity_from_extraction(extraction(barcode=good), "openai:m")
    assert ident.value("barcode") == "4006381333931"


def test_unknown_status_drops_value_and_value_less_field_becomes_unknown():
    out = extraction(
        strength=ProviderField(value="500 mg", status=FieldStatus.UNKNOWN, evidence=None),
        dosage_form=ProviderField(value=None, status=FieldStatus.CONFIRMED, evidence="x"),
    )
    ident = identity_from_extraction(out, "g:m")
    assert ident.strength.value is None and ident.dosage_form.status == FieldStatus.UNKNOWN


def test_unreadable_image_gives_unknown_category_and_clarification():
    ident = identity_from_extraction(extraction(readable=False), "g:m")
    assert ident.category == ProductCategory.UNKNOWN
    assert check_ambiguity(ident).needs_clarification


def test_complete_confirmed_medicine_needs_no_clarification():
    assert not check_ambiguity(medicine()).needs_clarification


def test_missing_strength_requires_clarification():
    amb = check_ambiguity(medicine(strength=cf(None)))
    assert amb.needs_clarification and "strength" in amb.missing_essentials


def test_inferred_essential_needs_user_confirmation():
    amb = check_ambiguity(medicine(strength=cf("500 mg", FieldStatus.INFERRED)))
    assert amb.needs_clarification and amb.unconfirmed_essentials == ["strength"]


def test_contradictions_block_search():
    assert check_ambiguity(
        medicine(contradictions=["label says 500 mg and 650 mg"])
    ).needs_clarification


def test_supply_requires_specific_attribute_and_pack():
    assert not check_ambiguity(gloves()).needs_clarification
    amb = check_ambiguity(gloves(material=cf(None), size_dimensions=cf(None)))
    assert "model/SKU, size or material" in amb.missing_essentials


def test_pack_units_only_for_plain_integers():
    assert medicine().pack_units == 10
    assert medicine(pack_quantity=cf("10 x 10")).pack_units is None
    assert medicine(pack_quantity=cf("0")).pack_units is None
