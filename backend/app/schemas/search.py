from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import BuyingMode, Market, Money, ProviderName
from app.schemas.identity import ProductIdentity
from app.schemas.offers import OfferView


class WorkflowState(StrEnum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    IDENTIFYING_PRODUCT = "IDENTIFYING_PRODUCT"
    IDENTITY_READY = "IDENTITY_READY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    SEARCHING_SUPPLIERS = "SEARCHING_SUPPLIERS"
    VERIFYING_OFFERS = "VERIFYING_OFFERS"
    PARTIAL_RESULTS = "PARTIAL_RESULTS"
    RESULTS_READY = "RESULTS_READY"
    NO_MATCHES = "NO_MATCHES"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    FAILED = "FAILED"


class SearchOptions(BaseModel):
    provider: ProviderName = ProviderName.OPENAI
    mode: BuyingMode = BuyingMode.RETAIL
    market: Market = Market.INDIA
    quantity: int = Field(default=1, ge=1, le=100_000)  # number of packs of the identified pack
    min_price: Money | None = Field(default=None, ge=0)
    max_price: Money | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _range(self) -> "SearchOptions":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must not exceed max_price")
        return self


class CreateSearchRequest(BaseModel):
    identity: ProductIdentity
    options: SearchOptions = Field(default_factory=SearchOptions)


class SourceStatus(BaseModel):
    connector_id: str
    name: str
    kind: str
    is_demo: bool = False
    status: str  # pending | ok | timeout | error | skipped
    offers: int = 0
    attempts: int = 0
    duration_ms: int | None = None
    error: str | None = None


class ActivityEvent(BaseModel):
    """One real step the workflow took, for the live activity feed. Never invented by the UI."""

    at: datetime
    phase: Literal["plan", "search", "read", "verify", "rank", "done"]
    level: Literal["info", "success", "warn", "error"] = "info"
    message: str = Field(max_length=300)


class Progress(BaseModel):
    state: WorkflowState = WorkflowState.REQUEST_RECEIVED
    message: str = ""
    current_node: str | None = None
    completed_nodes: list[str] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
    offers_discovered: int = 0
    offers_verified: int = 0
    offers_partially_verified: int = 0
    offers_unverified: int = 0
    offers_rejected: int = 0
    unresolved: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)  # identity details that were unclear
    activity: list[ActivityEvent] = Field(default_factory=list)
    error: str | None = None
    finished: bool = False
    updated_at: datetime | None = None


class SearchSummary(BaseModel):
    id: str
    created_at: datetime
    product_label: str
    options: SearchOptions
    state: WorkflowState
    is_terminal: bool
    offers_discovered: int


class SearchDetail(BaseModel):
    id: str
    created_at: datetime
    identity: ProductIdentity
    options: SearchOptions
    progress: Progress
    is_terminal: bool
    is_demo_data_present: bool = False
    offers: list[OfferView] = Field(default_factory=list)
    target_currency: str | None = None
