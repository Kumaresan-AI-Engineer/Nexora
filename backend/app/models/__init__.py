"""SQLAlchemy models. Product identity, offers, and time-stamped observations are kept separate."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> uuid.UUID:
    return uuid.uuid4()


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    identity_key: Mapped[str] = mapped_column(
        String(64), unique=True
    )  # hash of identity attributes
    category: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str] = mapped_column(String(300))
    identity: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    identifiers: Mapped[list["ProductIdentifier"]] = relationship(back_populates="product")


class ProductIdentifier(Base):
    __tablename__ = "product_identifiers"
    __table_args__ = (UniqueConstraint("product_id", "kind", "value"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # gtin | model_sku
    value: Mapped[str] = mapped_column(String(100))

    product: Mapped[Product] = relationship(back_populates="identifiers")


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    key: Mapped[str] = mapped_column(String(200), unique=True)  # domain, else normalised name
    name: Mapped[str] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(80))
    domain: Mapped[str | None] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SupplierSource(Base):
    __tablename__ = "supplier_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    connector_id: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Offer(Base):
    """One supplier's listing of one product; prices live in OfferObservation history."""

    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("supplier_id", "product_id", "canonical_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    canonical_key: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(Text, default="")
    product_url: Mapped[str | None] = mapped_column(Text)
    pack_units: Mapped[int | None] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    observations: Mapped[list["OfferObservation"]] = relationship(back_populates="offer")


class OfferObservation(Base):
    __tablename__ = "offer_observations"
    __table_args__ = (Index("ix_obs_offer_time", "offer_id", "observed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    search_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("search_sessions.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(8))
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    availability: Mapped[str] = mapped_column(String(20), default="unknown")
    verification_status: Mapped[str] = mapped_column(String(24))
    verification: Mapped[dict] = mapped_column(JSON)
    raw: Mapped[dict] = mapped_column(JSON)

    offer: Mapped[Offer] = relationship(back_populates="observations")
    evidence: Mapped[list["OfferEvidence"]] = relationship(back_populates="observation")


class OfferEvidence(Base):
    __tablename__ = "offer_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offer_observations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)
    api_ref: Mapped[str | None] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(Text, default="")
    observed: Mapped[dict] = mapped_column(JSON)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    observation: Mapped[OfferObservation] = relationship(back_populates="evidence")


class SearchSession(Base):
    __tablename__ = "search_sessions"
    __table_args__ = (Index("ix_search_owner_created", "owner", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    owner: Mapped[str] = mapped_column(String(64))  # anonymous browser-session id
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    identity: Mapped[dict] = mapped_column(JSON)
    options: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), default="REQUEST_RECEIVED")
    progress: Mapped[dict] = mapped_column(JSON)  # workflow checkpoint
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    results: Mapped[list["SearchResult"]] = relationship(back_populates="search")


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (UniqueConstraint("search_id", "offer_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_id)
    search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_sessions.id", ondelete="CASCADE"), index=True
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offers.id"))
    observation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offer_observations.id"))
    tier: Mapped[str] = mapped_column(String(24))
    rank: Mapped[int | None] = mapped_column(Integer)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    view: Mapped[dict] = mapped_column(JSON)  # serialised OfferView for this search

    search: Mapped[SearchSession] = relationship(back_populates="results")
