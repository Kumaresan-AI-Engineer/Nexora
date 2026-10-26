from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import Money


class EvidenceType(StrEnum):
    API_RESPONSE = "api_response"
    PAGE_EXTRACTION = "page_extraction"
    SEARCH_SNIPPET = "search_snippet"
    REFERENCE_DATA = "reference_data"
    FIXTURE = "fixture"


DIRECT_EVIDENCE = {EvidenceType.API_RESPONSE, EvidenceType.PAGE_EXTRACTION}


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LIMITED = "limited"
    UNKNOWN = "unknown"


class Audience(StrEnum):
    RETAIL = "retail"
    BUSINESS = "business"
    BOTH = "both"
    UNKNOWN = "unknown"


class Evidence(BaseModel):
    type: EvidenceType
    source_url: str | None = None
    api_ref: str | None = None
    excerpt: str = Field(default="", max_length=600)
    observed: dict[str, str] = Field(default_factory=dict)  # facts this evidence supports
    retrieved_at: datetime
    source_updated_at: datetime | None = None


class PriceBreak(BaseModel):
    min_packs: int = Field(ge=1)
    pack_price: Money


class RawOffer(BaseModel):
    """Connector output: a *candidate*. Connectors cannot set verification status."""

    connector_id: str
    connector_kind: str
    is_demo: bool = False
    supplier_name: str
    supplier_country: str | None = None
    supplier_domain: str | None = None
    title: str = ""
    declared: dict[str, str | None] = Field(default_factory=dict)  # attributes the source states
    pack_units: int | None = None
    price: Money | None = None
    currency: str | None = None
    mrp: Money | None = None
    moq_packs: int | None = None
    price_breaks: list[PriceBreak] = Field(default_factory=list)
    audience: Audience = Audience.UNKNOWN
    availability: Availability = Availability.UNKNOWN
    availability_source: str | None = None
    delivery_estimate: str | None = None
    shipping_cost: Money | None = None
    tax_included: bool | None = None
    tax_amount: Money | None = None
    checkout_total: Money | None = None
    lead_time: str | None = None
    credit_terms: str | None = None
    prescription_required: bool | None = None
    product_url: str | None = None
    enquiry_url: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    needs_page_extraction: bool = False


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


class Check(BaseModel):
    name: str
    result: str  # pass | fail | missing | conflict | info
    detail: str = ""


class VerificationResult(BaseModel):
    status: VerificationStatus
    reasons: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    supplier_verification: str = "not_independently_verified"


class Comparability(StrEnum):
    SAME_PACK = "same_pack"
    PACK_DIFFERS = "pack_differs"  # compared via unit price
    UNKNOWN_PACK = "unknown_pack"  # no valid unit price / requested cost


class OfferPricing(BaseModel):
    currency_original: str | None = None
    target_currency: str
    pack_price_original: Money | None = None
    pack_price: Money | None = None  # converted, supplier selling price per pack
    mrp_original: Money | None = None
    mrp: Money | None = None
    fx_rate: float | None = None
    fx_observed_at: datetime | None = None
    fx_source: str | None = None
    comparability: Comparability = Comparability.UNKNOWN_PACK
    offer_pack_units: int | None = None
    unit_price: Money | None = None
    requested_units: int | None = None
    packs_needed: int | None = None
    requested_cost: Money | None = None
    moq_packs: int | None = None
    moq_applied: bool = False
    price_break_applied: bool = False
    shipping_cost: Money | None = None
    shipping_status: str = "unknown"  # known | unknown
    tax_status: str = "unknown"  # included | added | unknown
    tax_amount: Money | None = None
    estimated_known_total: Money | None = None
    total_is_complete: bool = False
    final_payable: Money | None = None  # only when the source states a checkout total
    exclusions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OfferView(BaseModel):
    """What the API returns for each comparable row."""

    offer_id: str
    supplier_name: str
    supplier_country: str | None
    supplier_domain: str | None
    connector_id: str
    is_demo: bool
    title: str
    declared: dict[str, str | None]
    product_url: str | None
    enquiry_url: str | None
    availability: Availability
    availability_source: str | None
    delivery_estimate: str | None
    audience: Audience
    prescription_required: bool | None
    lead_time: str | None
    credit_terms: str | None
    verification: VerificationResult
    pricing: OfferPricing
    tier: VerificationStatus
    eligible: bool
    ineligible_reasons: list[str] = Field(default_factory=list)
    rank: int | None = None
    source_retrieved_at: datetime | None = None
    source_updated_at: datetime | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    duplicates_merged: int = 0
