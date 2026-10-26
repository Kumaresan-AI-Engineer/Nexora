"""Deterministic offer verification. No AI confidence scores; every status has explicit reasons.

Status criteria (see docs/VERIFICATION_AND_PRICING.md):
  REJECTED            a critical product attribute explicitly contradicts the identity, a strong
                      identifier (barcode) differs, or the price is not a positive number.
  UNVERIFIED          no direct (API/page) price evidence, price/currency missing, direct evidence
                      conflicts, price validity has expired, or the offer is demonstration data.
  PARTIALLY_VERIFIED  direct price evidence exists and nothing contradicts the product, but some
                      required attribute is not stated, evidence is stale, or the manufacturer differs.
  VERIFIED            direct price evidence, fresh, a source link/reference, and every required
                      attribute explicitly matches. This means "source-verified", not "supplier is safe".
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.schemas.identity import ProductCategory, ProductIdentity
from app.schemas.offers import (
    DIRECT_EVIDENCE,
    Check,
    Evidence,
    EvidenceType,
    RawOffer,
    VerificationResult,
    VerificationStatus,
)
from app.verification.normalize import (
    norm_boolean_text,
    norm_form,
    norm_ingredients,
    norm_strength,
    norm_text,
)

MATCH, MISMATCH, NOT_STATED = "match", "mismatch", "not_stated"
PRICE_TOLERANCE = Decimal("0.005")
FORM_NOUNS = {
    "tablet",
    "capsule",
    "injection",
    "syrup",
    "suspension",
    "ointment",
    "cream",
    "gel",
    "drops",
    "solution",
    "powder",
    "lotion",
    "spray",
    "inhaler",
    "patch",
    "suppository",
}


@dataclass
class AttrResult:
    state: str
    detail: str


def _contains_words(haystack: str, needle: str) -> bool:
    return f" {needle} " in f" {haystack} " if needle else False


def _declared(offer: RawOffer, *keys: str) -> str | None:
    for k in keys:
        v = offer.declared.get(k)
        if v and v.strip():
            return v.strip()
    return None


def _ingredients(identity: ProductIdentity, offer: RawOffer) -> AttrResult:
    want = norm_ingredients(identity.value("active_ingredients") or identity.value("generic_name"))
    declared = _declared(offer, "active_ingredients", "generic_name")
    if declared:
        have = norm_ingredients(declared)
        return AttrResult(
            MATCH if have == want else MISMATCH,
            f"offer states '{declared}', identity '{', '.join(sorted(want))}'",
        )
    title = norm_text(offer.title)
    if want and all(_contains_words(title, w) for w in want):
        return AttrResult(MATCH, "ingredient name found in listing title")
    return AttrResult(NOT_STATED, "active ingredient not stated by the source")


def _strength(identity: ProductIdentity, offer: RawOffer) -> AttrResult:
    want = norm_strength(identity.value("strength"))
    if want is None:
        return AttrResult(NOT_STATED, "identity strength could not be parsed")
    declared = _declared(offer, "strength")
    if declared:
        have = norm_strength(declared)
        if have is None:
            return AttrResult(NOT_STATED, f"offer strength '{declared}' could not be parsed")
        return AttrResult(
            MATCH if have == want else MISMATCH,
            f"offer '{declared}' vs identity '{identity.value('strength')}'",
        )
    in_title = norm_strength(offer.title)
    if in_title is None:
        return AttrResult(NOT_STATED, "strength not stated by the source")
    if set(want) <= set(in_title):
        return AttrResult(MATCH, "strength found in listing title")
    return AttrResult(
        MISMATCH, f"title shows a different strength than '{identity.value('strength')}'"
    )


def _title_form(title: str) -> tuple[str, frozenset[str]] | None:
    parsed = norm_form(title)
    if not parsed:
        return None
    nouns = [w for w in parsed[0].split() if w in FORM_NOUNS]
    return (nouns[0], parsed[1]) if nouns else None


def _form_text(form: tuple[str, frozenset[str]]) -> str:
    return " ".join([*sorted(form[1]), form[0]]).strip()


def _dosage_form(identity: ProductIdentity, offer: RawOffer) -> AttrResult:
    want = norm_form(identity.value("dosage_form"))
    declared = _declared(offer, "dosage_form")
    have = norm_form(declared) if declared else _title_form(offer.title)
    if want is None or have is None:
        return AttrResult(NOT_STATED, "dosage form not stated by the source")
    if (
        declared is None
    ):  # title text also contains unrelated words: compare noun + release type only
        want = (next((w for w in want[0].split() if w in FORM_NOUNS), want[0]), want[1])
    return AttrResult(
        MATCH if have == want else MISMATCH,
        f"offer form '{_form_text(have)}' vs identity '{_form_text(want)}'",
    )


def _text_attr(identity_value: str, declared: str | None, title: str, label: str) -> AttrResult:
    want = norm_text(identity_value)
    if declared:
        have = norm_text(declared)
        ok = have == want or set(want.split()) <= set(have.split())
        return AttrResult(
            MATCH if ok else MISMATCH, f"{label}: offer '{declared}' vs identity '{identity_value}'"
        )
    if _contains_words(norm_text(title), want):
        return AttrResult(MATCH, f"{label} found in listing title")
    return AttrResult(NOT_STATED, f"{label} not stated by the source")


def _product_name(identity: ProductIdentity, offer: RawOffer) -> AttrResult:
    want = set(norm_text(identity.value("product_name")).split())
    declared = _declared(offer, "product_name")
    pool = set(norm_text(declared or offer.title).split())
    if want and want <= pool:
        return AttrResult(MATCH, "product name matches")
    if declared:
        return AttrResult(
            MISMATCH, f"offer product '{declared}' vs identity '{identity.value('product_name')}'"
        )
    return AttrResult(NOT_STATED, "product name not confirmed by the source")


def _pack(identity: ProductIdentity, offer: RawOffer) -> tuple[AttrResult, bool]:
    """Returns (result, acceptable_for_verified). A different but known pack size is comparable."""
    want, have = identity.pack_units, offer.pack_units
    if want is None or have is None:
        return AttrResult(NOT_STATED, "pack quantity unknown on one side"), False
    if want == have:
        return AttrResult(MATCH, f"pack of {have}"), True
    return AttrResult(
        "pack_differs", f"offer pack {have} vs identity pack {want}; compared by unit price"
    ), True


def _barcode(identity: ProductIdentity, offer: RawOffer) -> AttrResult | None:
    want = identity.value("barcode")
    have = _declared(offer, "barcode")
    if not want or not have:
        return None
    return AttrResult(
        MATCH if "".join(filter(str.isdigit, have)) == want else MISMATCH,
        f"barcode offer {have} vs identity {want}",
    )


def _manufacturer(identity: ProductIdentity, offer: RawOffer) -> AttrResult | None:
    want, have = identity.value("manufacturer"), _declared(offer, "manufacturer")
    if not want or not have:
        return None
    overlap = set(norm_text(want).split()) & set(norm_text(have).split())
    return AttrResult(
        MATCH if overlap else MISMATCH, f"manufacturer offer '{have}' vs identity '{want}'"
    )


def _price_evidence(
    offer: RawOffer, now: datetime, max_age: timedelta
) -> tuple[list[Check], list[str], list[str], bool, bool]:
    """Returns (checks, missing, conflicts, has_direct_support, is_fresh)."""
    checks: list[Check] = []
    missing: list[str] = []
    conflicts: list[str] = []
    direct = [e for e in offer.evidence if e.type in DIRECT_EVIDENCE]
    if not direct:
        snippets = any(e.type == EvidenceType.SEARCH_SNIPPET for e in offer.evidence)
        detail = (
            "a search snippet alone is not price evidence"
            if snippets
            else "no direct source (API or product page) evidence of the price"
        )
        checks.append(Check(name="price_evidence", result="fail", detail=detail))
        missing.append("direct price evidence")
        return checks, missing, conflicts, False, False

    observed: list[tuple[Decimal, str, Evidence]] = []
    for e in direct:
        try:
            p = Decimal(e.observed.get("price", ""))
        except InvalidOperation:  # non-numeric observation counts as no support
            continue
        observed.append((p, e.observed.get("currency", "").upper(), e))
    supporting = []
    for p, cur, e in observed:
        same_cur = offer.currency and cur == offer.currency.upper()
        close = offer.price and abs(p - offer.price) <= offer.price * PRICE_TOLERANCE
        if same_cur and close:
            supporting.append(e)
        else:
            conflicts.append(
                f"evidence from {e.source_url or e.api_ref or e.type.value} shows {p} {cur}, offer states {offer.price} {offer.currency}"
            )
    if not supporting:
        checks.append(
            Check(
                name="price_evidence",
                result="conflict" if conflicts else "fail",
                detail="direct evidence does not support the stated price",
            )
        )
        missing.append("direct evidence supporting the stated price")
        return checks, missing, conflicts, False, False
    if conflicts:
        checks.append(Check(name="price_evidence", result="conflict", detail="; ".join(conflicts)))
        return checks, missing, conflicts, False, False

    checks.append(
        Check(
            name="price_evidence",
            result="pass",
            detail=f"{len(supporting)} direct source observation(s) support {offer.price} {offer.currency}",
        )
    )
    newest = max(e.retrieved_at for e in supporting)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    fresh = now - newest <= max_age
    checks.append(
        Check(
            name="freshness",
            result="pass" if fresh else "fail",
            detail=f"observed {newest.isoformat()}",
        )
    )
    for e in supporting:
        vu = e.observed.get("valid_until")
        if vu:
            try:
                until = datetime.fromisoformat(vu)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=UTC)
                if until < now:
                    conflicts.append(f"price validity ended {vu}")
                    checks.append(
                        Check(
                            name="price_validity",
                            result="fail",
                            detail=f"priceValidUntil {vu} has passed",
                        )
                    )
                    return checks, missing, conflicts, False, fresh
            except ValueError:
                pass
    return checks, missing, conflicts, True, fresh


def verify_offer(
    identity: ProductIdentity,
    offer: RawOffer,
    now: datetime | None = None,
    max_age_hours: float = 24.0,
) -> VerificationResult:
    now = now or datetime.now(UTC)
    checks: list[Check] = []
    reasons: list[str] = []
    rejected = False
    required_ok = True  # all required attributes explicitly matched
    manufacturer_differs = False

    def record(name: str, r: AttrResult, required: bool = True) -> None:
        nonlocal rejected, required_ok
        result = {MATCH: "pass", MISMATCH: "fail", NOT_STATED: "missing", "pack_differs": "info"}[
            r.state
        ]
        checks.append(Check(name=f"match:{name}", result=result, detail=r.detail))
        if r.state == MISMATCH:
            rejected = True
            reasons.append(f"{name} does not match ({r.detail})")
        elif r.state == NOT_STATED and required:
            required_ok = False

    if identity.category == ProductCategory.MEDICINE:
        record("active_ingredients", _ingredients(identity, offer))
        if identity.value("strength"):
            record("strength", _strength(identity, offer))
        if identity.value("dosage_form"):
            record("dosage_form", _dosage_form(identity, offer))
        if identity.value("brand_name"):
            record(
                "brand_name",
                _text_attr(
                    identity.value("brand_name") or "",
                    _declared(offer, "brand_name"),
                    offer.title,
                    "brand",
                ),
            )
    else:
        if identity.value("product_name"):
            record("product_name", _product_name(identity, offer))
        for key in ("model_sku", "size_dimensions", "material"):
            if identity.value(key):
                record(
                    key,
                    _text_attr(identity.value(key) or "", _declared(offer, key), offer.title, key),
                )
        if identity.value("sterile"):
            want = norm_boolean_text(identity.value("sterile"))
            have = norm_boolean_text(_declared(offer, "sterile"))
            if want is None or have is None:
                record("sterile", AttrResult(NOT_STATED, "sterility not stated by the source"))
            else:
                record(
                    "sterile",
                    AttrResult(
                        MATCH if want == have else MISMATCH,
                        f"sterile offer {have} vs identity {want}",
                    ),
                )

    pack_result, pack_ok = _pack(identity, offer)
    record("pack_quantity", pack_result, required=False)
    if not pack_ok:
        required_ok = False

    for name, fn in (("barcode", _barcode), ("manufacturer", _manufacturer)):
        r = fn(identity, offer)
        if r is None:
            continue
        if name == "manufacturer":
            checks.append(
                Check(
                    name="match:manufacturer",
                    result="pass" if r.state == MATCH else "fail",
                    detail=r.detail,
                )
            )
            manufacturer_differs = r.state == MISMATCH
            if manufacturer_differs:
                reasons.append(f"manufacturer differs ({r.detail})")
        else:
            record(name, r, required=False)

    if offer.price is not None and offer.price <= 0:
        rejected = True
        reasons.append("stated price is not a positive number")
        checks.append(Check(name="price_valid", result="fail", detail=f"price {offer.price}"))

    price_checks, missing, conflicts, supported, fresh = _price_evidence(
        offer, now, timedelta(hours=max_age_hours)
    )
    checks.extend(price_checks)
    has_price = offer.price is not None and offer.price > 0 and bool(offer.currency)
    if not has_price:
        missing.append("price or currency")
        checks.append(
            Check(
                name="price_stated", result="missing", detail="offer has no usable price/currency"
            )
        )
    has_link = bool(offer.product_url or any(e.api_ref for e in offer.evidence))
    checks.append(
        Check(
            name="source_reference",
            result="pass" if has_link else "missing",
            detail=offer.product_url or "no product URL or API reference",
        )
    )
    checks.append(
        Check(
            name="supplier_verification",
            result="info",
            detail="Supplier legitimacy is not independently verified; supplier-provided claims are not proof.",
        )
    )

    if rejected:
        status = VerificationStatus.REJECTED
    elif offer.is_demo:
        status = VerificationStatus.UNVERIFIED
        reasons.append("Demonstration fixture data: never treated as a verified market offer.")
    elif not has_price or not supported or conflicts:
        status = VerificationStatus.UNVERIFIED
        reasons.extend(f"Missing: {m}" for m in missing)
        reasons.extend(f"Conflict: {c}" for c in conflicts)
    elif required_ok and fresh and has_link and not manufacturer_differs:
        status = VerificationStatus.VERIFIED
        reasons.append(
            "Direct source evidence supports the price and all required attributes match."
        )
    else:
        status = VerificationStatus.PARTIALLY_VERIFIED
        if not required_ok:
            reasons.append("Some required product attributes are not stated by the source.")
        if not fresh:
            reasons.append("Price evidence is older than the allowed freshness window.")
        if not has_link:
            reasons.append("No product URL or API reference to re-check the price.")

    unresolved = [
        c.name.removeprefix("match:")
        for c in checks
        if c.name.startswith("match:") and c.result == "missing"
    ]
    return VerificationResult(
        status=status,
        reasons=reasons,
        checks=checks,
        missing=sorted(set(missing + unresolved)),
        conflicts=conflicts,
    )
