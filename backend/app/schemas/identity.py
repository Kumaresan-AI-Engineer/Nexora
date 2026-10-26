"""Product identity models. `ExtractedField.status` separates confirmed / inferred / unknown values."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"  # read directly from packaging text or supplied by the user
    INFERRED = "inferred"  # deduced, not directly visible: never proof of identity
    UNKNOWN = "unknown"


class ProductCategory(StrEnum):
    MEDICINE = "medicine"
    SUPPLY = "supply"
    EQUIPMENT = "equipment"
    UNKNOWN = "unknown"


FIELD_NAMES = (
    "brand_name",
    "generic_name",
    "active_ingredients",
    "strength",
    "dosage_form",
    "route",
    "pack_quantity",
    "pack_configuration",
    "manufacturer",
    "barcode",
    "product_name",
    "model_sku",
    "size_dimensions",
    "material",
    "sterile",
    "certifications",
)


ShortText = Annotated[str, StringConstraints(max_length=300)]


class ExtractedField(BaseModel):
    value: Annotated[str, StringConstraints(max_length=300)] | None = None
    status: FieldStatus = FieldStatus.UNKNOWN
    evidence: str | None = Field(default=None, max_length=300)

    def known(self) -> bool:
        return self.status != FieldStatus.UNKNOWN and bool(self.value and self.value.strip())


def _f() -> ExtractedField:
    return ExtractedField()


class ProductIdentity(BaseModel):
    category: ProductCategory = ProductCategory.UNKNOWN
    brand_name: ExtractedField = Field(default_factory=_f)
    generic_name: ExtractedField = Field(default_factory=_f)
    active_ingredients: ExtractedField = Field(default_factory=_f)
    strength: ExtractedField = Field(default_factory=_f)
    dosage_form: ExtractedField = Field(default_factory=_f)
    route: ExtractedField = Field(default_factory=_f)
    pack_quantity: ExtractedField = Field(default_factory=_f)  # units per pack, e.g. "10"
    pack_configuration: ExtractedField = Field(default_factory=_f)
    manufacturer: ExtractedField = Field(default_factory=_f)
    barcode: ExtractedField = Field(default_factory=_f)
    product_name: ExtractedField = Field(default_factory=_f)
    model_sku: ExtractedField = Field(default_factory=_f)
    size_dimensions: ExtractedField = Field(default_factory=_f)
    material: ExtractedField = Field(default_factory=_f)
    sterile: ExtractedField = Field(default_factory=_f)
    certifications: ExtractedField = Field(default_factory=_f)
    contradictions: list[ShortText] = Field(default_factory=list, max_length=20)
    notes: list[ShortText] = Field(default_factory=list, max_length=20)
    extracted_by: str | None = Field(
        default=None, max_length=100
    )  # "provider:model" that produced the extraction

    def field(self, name: str) -> ExtractedField:
        return getattr(self, name)

    def value(self, name: str) -> str | None:
        f = self.field(name)
        return f.value.strip() if f.known() and f.value else None

    @property
    def pack_units(self) -> int | None:
        """Units per pack, only when the value is a plain positive integer."""
        raw = self.value("pack_quantity")
        if raw and raw.replace(" ", "").isdigit():
            n = int(raw.replace(" ", ""))
            return n if n > 0 else None
        return None

    def display_name(self) -> str:
        return (
            self.value("brand_name")
            or self.value("product_name")
            or self.value("generic_name")
            or self.value("active_ingredients")
            or "Unidentified product"
        )


class ProviderField(BaseModel):
    """Provider output field: all keys required (needed for strict structured-output modes)."""

    value: str | None
    status: FieldStatus
    evidence: str | None


class ExtractionOutput(BaseModel):
    """Schema the vision model must fill. Validated again by Pydantic after every call."""

    category: ProductCategory
    readable: bool
    brand_name: ProviderField
    generic_name: ProviderField
    active_ingredients: ProviderField
    strength: ProviderField
    dosage_form: ProviderField
    route: ProviderField
    pack_quantity: ProviderField
    pack_configuration: ProviderField
    manufacturer: ProviderField
    barcode: ProviderField
    product_name: ProviderField
    model_sku: ProviderField
    size_dimensions: ProviderField
    material: ProviderField
    sterile: ProviderField
    certifications: ProviderField
    contradictions: list[str]
    notes: list[str]


class Ambiguity(BaseModel):
    needs_clarification: bool
    missing_essentials: list[str] = Field(default_factory=list)
    unconfirmed_essentials: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class IdentifyResponse(BaseModel):
    identity: ProductIdentity
    ambiguity: Ambiguity
    provider: str
    model: str
    duration_ms: int
    state: str
