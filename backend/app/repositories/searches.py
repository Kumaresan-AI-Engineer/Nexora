import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import Database
from app.models import (
    Offer,
    OfferEvidence,
    OfferObservation,
    Product,
    ProductIdentifier,
    SearchResult,
    SearchSession,
    Supplier,
)
from app.schemas.identity import FIELD_NAMES, ProductIdentity
from app.schemas.offers import OfferView
from app.schemas.search import (
    Progress,
    SearchDetail,
    SearchOptions,
    SearchSummary,
    WorkflowState,
)
from app.verification.normalize import norm_text


def identity_key(identity: ProductIdentity) -> str:
    payload = {"category": identity.category.value}
    payload.update({n: norm_text(identity.value(n)) for n in FIELD_NAMES if identity.value(n)})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


class SearchRepository:
    def __init__(self, db: Database):
        self._db = db

    # ----- creation / lifecycle -------------------------------------------------------
    def create(self, owner: str, identity: ProductIdentity, options: SearchOptions) -> uuid.UUID:
        progress = Progress(
            state=WorkflowState.REQUEST_RECEIVED, message="Search received.", updated_at=_now()
        )
        with self._db.session() as s:
            product = self._upsert_product(s, identity)
            row = SearchSession(
                owner=owner,
                product_id=product.id,
                identity=identity.model_dump(mode="json"),
                options=options.model_dump(mode="json"),
                state=progress.state.value,
                progress=progress.model_dump(mode="json"),
            )
            s.add(row)
            s.flush()
            return row.id

    def count_active(self, owner: str) -> int:
        with self._db.session() as s:
            return (
                s.scalar(
                    select(func.count())
                    .select_from(SearchSession)
                    .where(SearchSession.owner == owner, SearchSession.finished_at.is_(None))
                )
                or 0
            )

    def save_progress(self, search_id: uuid.UUID, progress: Progress) -> None:
        progress.updated_at = _now()
        with self._db.session() as s:
            row = s.get(SearchSession, search_id)
            if row is None:
                return
            row.progress = progress.model_dump(mode="json")
            row.state = progress.state.value
            row.updated_at = progress.updated_at
            if progress.finished:
                row.finished_at = progress.updated_at

    def mark_interrupted(self) -> int:
        """On startup: searches left non-terminal by a previous process cannot continue."""
        with self._db.session() as s:
            rows = s.scalars(select(SearchSession).where(SearchSession.finished_at.is_(None))).all()
            for row in rows:
                p = Progress.model_validate(row.progress)
                p.state, p.error, p.finished = (
                    WorkflowState.FAILED,
                    "Search interrupted by a server restart.",
                    True,
                )
                p.message = p.error
                row.progress, row.state, row.finished_at = (
                    p.model_dump(mode="json"),
                    p.state.value,
                    _now(),
                )
            return len(rows)

    # ----- reads ----------------------------------------------------------------------
    def get_detail(self, search_id: uuid.UUID, owner: str) -> SearchDetail | None:
        with self._db.session() as s:
            row = s.get(SearchSession, search_id)
            if row is None or row.owner != owner:
                return None
            results = s.scalars(
                select(SearchResult).where(SearchResult.search_id == search_id)
            ).all()
            views = [OfferView.model_validate(r.view) for r in results]
            views.sort(key=lambda v: (v.rank is None, v.rank or 0))
            progress = Progress.model_validate(row.progress)
            options = SearchOptions.model_validate(row.options)
            return SearchDetail(
                id=str(row.id),
                created_at=row.created_at,
                identity=ProductIdentity.model_validate(row.identity),
                options=options,
                progress=progress,
                is_terminal=progress.finished,
                is_demo_data_present=any(v.is_demo for v in views),
                offers=views,
                target_currency=views[0].pricing.target_currency if views else None,
            )

    def list_for_owner(
        self, owner: str, limit: int, offset: int
    ) -> tuple[list[SearchSummary], int]:
        with self._db.session() as s:
            total = (
                s.scalar(
                    select(func.count())
                    .select_from(SearchSession)
                    .where(SearchSession.owner == owner)
                )
                or 0
            )
            rows = s.scalars(
                select(SearchSession)
                .where(SearchSession.owner == owner)
                .order_by(SearchSession.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            out = []
            for r in rows:
                p = Progress.model_validate(r.progress)
                ident = ProductIdentity.model_validate(r.identity)
                out.append(
                    SearchSummary(
                        id=str(r.id),
                        created_at=r.created_at,
                        product_label=ident.display_name(),
                        options=SearchOptions.model_validate(r.options),
                        state=p.state,
                        is_terminal=p.finished,
                        offers_discovered=p.offers_discovered,
                    )
                )
            return out, total

    def get_offer(self, search_id: uuid.UUID, offer_id: str, owner: str) -> OfferView | None:
        with self._db.session() as s:
            row = s.get(SearchSession, search_id)
            if row is None or row.owner != owner:
                return None
            for r in s.scalars(select(SearchResult).where(SearchResult.search_id == search_id)):
                if r.view.get("offer_id") == offer_id:
                    return OfferView.model_validate(r.view)
            return None

    def delete(self, search_id: uuid.UUID, owner: str) -> bool:
        """Deletes the search and its result rows. Offers/observations stay as shared price history."""
        with self._db.session() as s:
            row = s.get(SearchSession, search_id)
            if row is None or row.owner != owner:
                return False
            s.execute(delete(SearchResult).where(SearchResult.search_id == search_id))
            for obs in s.scalars(
                select(OfferObservation).where(OfferObservation.search_id == search_id)
            ):
                obs.search_id = None
            s.delete(row)
            return True

    # ----- results --------------------------------------------------------------------
    def save_results(
        self, search_id: uuid.UUID, views: list[OfferView], progress: Progress | None = None
    ) -> None:
        """Replace the search's result rows; keep one observation (with evidence) per offer per search."""
        with self._db.session() as s:
            row = s.get(SearchSession, search_id)
            if row is None:
                return
            if (
                progress is not None
            ):  # same transaction: readers never see results without their state
                progress.updated_at = _now()
                row.progress = progress.model_dump(mode="json")
                row.state = progress.state.value
                row.updated_at = progress.updated_at
            product_id = row.product_id
            s.execute(delete(SearchResult).where(SearchResult.search_id == search_id))
            for v in views:
                supplier = self._upsert_supplier(s, v)
                offer = s.scalar(
                    select(Offer).where(
                        Offer.supplier_id == supplier.id,
                        Offer.product_id == product_id,
                        Offer.canonical_key == v.offer_id,
                    )
                )
                if offer is None:
                    offer = Offer(
                        supplier_id=supplier.id,
                        product_id=product_id,
                        canonical_key=v.offer_id,
                        title=v.title,
                        product_url=v.product_url,
                        pack_units=v.pricing.offer_pack_units,
                        is_demo=v.is_demo,
                    )
                    s.add(offer)
                    s.flush()
                obs = s.scalar(
                    select(OfferObservation).where(
                        OfferObservation.offer_id == offer.id,
                        OfferObservation.search_id == search_id,
                    )
                )
                if obs is None:
                    obs = OfferObservation(offer_id=offer.id, search_id=search_id)
                    s.add(obs)
                obs.observed_at = v.source_retrieved_at or _now()
                obs.price = v.pricing.pack_price_original
                obs.currency = v.pricing.currency_original
                obs.mrp = v.pricing.mrp_original
                obs.availability = v.availability.value
                obs.verification_status = v.verification.status.value
                obs.verification = v.verification.model_dump(mode="json")
                obs.raw = v.model_dump(mode="json", exclude={"evidence"})
                s.flush()
                s.execute(delete(OfferEvidence).where(OfferEvidence.observation_id == obs.id))
                for e in v.evidence:
                    s.add(
                        OfferEvidence(
                            observation_id=obs.id,
                            type=e.type.value,
                            source_url=e.source_url,
                            api_ref=e.api_ref,
                            excerpt=e.excerpt,
                            observed=e.observed,
                            retrieved_at=e.retrieved_at,
                            source_updated_at=e.source_updated_at,
                        )
                    )
                s.add(
                    SearchResult(
                        search_id=search_id,
                        offer_id=offer.id,
                        observation_id=obs.id,
                        tier=v.tier.value,
                        rank=v.rank,
                        eligible=v.eligible,
                        view=v.model_dump(mode="json"),
                    )
                )

    # ----- helpers --------------------------------------------------------------------
    @staticmethod
    def _upsert_product(s: Session, identity: ProductIdentity) -> Product:
        key = identity_key(identity)
        product = s.scalar(select(Product).where(Product.identity_key == key))
        if product:
            return product
        product = Product(
            identity_key=key,
            category=identity.category.value,
            display_name=identity.display_name()[:300],
            identity=identity.model_dump(mode="json"),
        )
        s.add(product)
        s.flush()
        for kind, field in (("gtin", "barcode"), ("model_sku", "model_sku")):
            if identity.value(field):
                s.add(
                    ProductIdentifier(
                        product_id=product.id, kind=kind, value=identity.value(field)[:100]
                    )
                )
        return product

    @staticmethod
    def _upsert_supplier(s: Session, v: OfferView) -> Supplier:
        key = (
            (v.supplier_domain or "").lower().removeprefix("www.") or norm_text(v.supplier_name)
        )[:200]
        supplier = s.scalar(select(Supplier).where(Supplier.key == key))
        if supplier is None:
            supplier = Supplier(
                key=key,
                name=v.supplier_name[:300],
                country=v.supplier_country,
                domain=v.supplier_domain,
                is_demo=v.is_demo,
            )
            s.add(supplier)
            s.flush()
        return supplier
