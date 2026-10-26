"""Deterministic identity handling: normalise provider output, validate GTINs, detect ambiguity."""

from app.schemas.identity import (
    FIELD_NAMES,
    Ambiguity,
    ExtractedField,
    ExtractionOutput,
    FieldStatus,
    ProductCategory,
    ProductIdentity,
)


def gtin_valid(code: str) -> bool:
    """GS1 check-digit validation for GTIN-8/12/13/14."""
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def _clean(field_value: str | None, status: FieldStatus, evidence: str | None) -> ExtractedField:
    value = (field_value or "").strip() or None
    if value is None or status == FieldStatus.UNKNOWN:
        return ExtractedField(value=None, status=FieldStatus.UNKNOWN, evidence=None)
    return ExtractedField(value=value, status=status, evidence=(evidence or "")[:300] or None)


def identity_from_extraction(out: ExtractionOutput, extracted_by: str) -> ProductIdentity:
    fields = {
        n: _clean(getattr(out, n).value, getattr(out, n).status, getattr(out, n).evidence)
        for n in FIELD_NAMES
    }
    notes = [n.strip() for n in out.notes if n.strip()][:10]

    barcode = fields["barcode"]
    if barcode.value:
        digits = "".join(c for c in barcode.value if c.isdigit())
        if gtin_valid(digits):
            fields["barcode"] = ExtractedField(
                value=digits, status=barcode.status, evidence=barcode.evidence
            )
        else:
            fields["barcode"] = ExtractedField()
            notes.append(
                "A barcode was read but failed GTIN check-digit validation; it was discarded."
            )

    category = out.category if out.readable else ProductCategory.UNKNOWN
    if not out.readable:
        notes.append("The image could not be read as a recognisable product.")
    return ProductIdentity(
        category=category,
        contradictions=[c.strip() for c in out.contradictions if c.strip()][:10],
        notes=notes,
        extracted_by=extracted_by,
        **fields,
    )


def _essentials(identity: ProductIdentity) -> list[tuple[str, tuple[str, ...]]]:
    """(label, alternative fields): satisfied when any listed field is known."""
    if identity.category == ProductCategory.MEDICINE:
        return [
            ("brand or generic name", ("brand_name", "generic_name")),
            ("active ingredient(s)", ("active_ingredients",)),
            ("strength", ("strength",)),
            ("dosage form", ("dosage_form",)),
            ("pack quantity", ("pack_quantity",)),
        ]
    if identity.category in (ProductCategory.SUPPLY, ProductCategory.EQUIPMENT):
        return [
            ("product name", ("product_name",)),
            ("model/SKU, size or material", ("model_sku", "size_dimensions", "material")),
            ("pack quantity", ("pack_quantity",)),
        ]
    return []


def check_ambiguity(identity: ProductIdentity) -> Ambiguity:
    messages: list[str] = []
    missing: list[str] = []
    unconfirmed: list[str] = []

    if identity.category == ProductCategory.UNKNOWN:
        messages.append(
            "The product category could not be determined. Choose a category or upload another image."
        )

    for label, alternatives in _essentials(identity):
        fields = [identity.field(a) for a in alternatives]
        if not any(f.known() for f in fields):
            missing.append(label)
        elif not any(f.status == FieldStatus.CONFIRMED and f.known() for f in fields):
            unconfirmed.append(label)

    if missing:
        messages.append("Missing essential details: " + ", ".join(missing) + ".")
    if unconfirmed:
        messages.append(
            "These details were inferred, not read from the pack, and need your confirmation: "
            + ", ".join(unconfirmed)
            + "."
        )
    if identity.contradictions:
        messages.append("The pack shows contradictory information; please resolve it.")

    needs = bool(messages)
    return Ambiguity(
        needs_clarification=needs,
        missing_essentials=missing,
        unconfirmed_essentials=unconfirmed,
        contradictions=list(identity.contradictions),
        messages=messages,
    )


def is_searchable(identity: ProductIdentity) -> bool:
    """A search needs at least something to search for. Missing details only limit verification."""
    return any(
        identity.value(n)
        for n in ("brand_name", "product_name", "generic_name", "active_ingredients")
    )
