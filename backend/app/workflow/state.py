from typing import Literal, TypedDict

from app.errors import AppError
from app.providers.base import PreparedImage
from app.schemas.identity import Ambiguity, ExtractionOutput, ProductIdentity
from app.schemas.offers import OfferPricing, OfferView, RawOffer, VerificationResult
from app.schemas.search import SearchOptions, WorkflowState


class GraphState(TypedDict, total=False):
    run_mode: Literal["identify_only", "full"]
    options: SearchOptions
    image_bytes: bytes | None
    image_mime: str | None
    image: PreparedImage | None
    extraction: ExtractionOutput | None
    identity: ProductIdentity | None
    ambiguity: Ambiguity | None
    searchable: bool
    provider_info: dict
    raw_offers: list[RawOffer]
    deduped: list[tuple[RawOffer, int]]
    verifications: dict[str, VerificationResult]
    pricings: dict[str, OfferPricing]
    views: list[OfferView]
    exception: AppError | None  # terminal error captured by a node
    failure_message: str | None
    final_state: WorkflowState | None
