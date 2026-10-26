"""Attribute normalisation used for deterministic product matching."""

import re
from decimal import Decimal

_SEP = re.compile(r"\s*(?:\+|/|,|;|&|\band\b|\bwith\b)\s*", re.I)
_SALTS = re.compile(
    r"\b(hydrochloride|hcl|sodium|potassium|calcium|sulfate|sulphate|maleate|besylate|"
    r"phosphate|tartrate|succinate|mesylate|citrate|acetate)\b",
    re.I,
)


def norm_text(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def norm_ingredients(raw: str | None) -> frozenset[str]:
    """Set of ingredient names; salt/form words are dropped so 'X HCl' equals 'X'."""
    parts = [p for p in _SEP.split(raw or "") if p.strip()]
    names = {norm_text(_SALTS.sub("", p)) for p in parts}
    return frozenset(n for n in names if n)


_STRENGTH = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mcg|µg|μg|ug|mg|g|kg|ml|l|iu|units?|%)(?![a-z])", re.I
)
_TO_MG = {
    "g": Decimal(1000),
    "kg": Decimal(1_000_000),
    "mcg": Decimal("0.001"),
    "µg": Decimal("0.001"),
    "μg": Decimal("0.001"),
    "ug": Decimal("0.001"),
}
_TO_ML = {"l": Decimal(1000)}


def norm_strength(raw: str | None) -> tuple[tuple[str, str], ...] | None:
    """Sorted (value, unit) pairs with mass normalised to mg and volume to ml; None if unparsable."""
    if not raw:
        return None
    pairs = []
    for num, unit in _STRENGTH.findall(raw):
        value = Decimal(num.replace(",", "."))
        u = unit.lower()
        if u in _TO_MG:
            value, u = value * _TO_MG[u], "mg"
        elif u in _TO_ML:
            value, u = value * _TO_ML[u], "ml"
        elif u.startswith("unit"):
            u = "units"
        pairs.append((format(value.normalize(), "f"), u))
    return tuple(sorted(pairs)) if pairs else None


_FORM_ABBR = {
    "tab": "tablet",
    "tabs": "tablet",
    "tablets": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsules": "capsule",
    "inj": "injection",
    "injections": "injection",
    "susp": "suspension",
    "syp": "syrup",
    "oint": "ointment",
    "soln": "solution",
}
_MATERIAL_QUALIFIERS = {
    "sr",
    "er",
    "xr",
    "cr",
    "xl",
    "modified",
    "extended",
    "sustained",
    "delayed",
    "enteric",
    "chewable",
    "dispersible",
    "odt",
    "orally",
    "disintegrating",
    "effervescent",
    "sublingual",
    "release",
    "dr",
}
_IGNORABLE = {"film", "coated", "uncoated", "sugar", "oral", "for", "use", "release"}


def norm_form(raw: str | None) -> tuple[str, frozenset[str]] | None:
    """(base form, material qualifiers). Coating words are ignored; release type is not."""
    words = [_FORM_ABBR.get(w, w) for w in norm_text(raw).split()]
    if not words:
        return None
    qualifiers = frozenset(w for w in words if w in _MATERIAL_QUALIFIERS and w != "release")
    base = [w for w in words if w not in _MATERIAL_QUALIFIERS and w not in _IGNORABLE]
    return (" ".join(base), qualifiers)


def norm_boolean_text(raw: str | None) -> bool | None:
    t = norm_text(raw)
    if t in {"yes", "true", "sterile", "y"}:
        return True
    if t in {"no", "false", "non sterile", "nonsterile", "not sterile", "n"}:
        return False
    return None


def canonical_url(url: str | None) -> str | None:
    """Strip fragments and tracking parameters so duplicate listings collapse."""
    if not url:
        return None
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref", "mc_"))
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), "")
    )
