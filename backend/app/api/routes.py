import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import Services, owner_id, services
from app.errors import AppError, ConflictError, ImageTooLargeError, NotFoundError
from app.identification.image_validation import ALLOWED_MIME
from app.identification.rules import check_ambiguity
from app.schemas.common import ProviderName
from app.schemas.identity import Ambiguity, IdentifyResponse, ProductIdentity
from app.schemas.offers import OfferView
from app.schemas.search import CreateSearchRequest, SearchDetail, SearchOptions, SearchSummary

router = APIRouter(prefix="/api")


class CreatedSearch(BaseModel):
    id: str
    state: str


class SearchPage(BaseModel):
    items: list[SearchSummary]
    total: int
    limit: int
    offset: int


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise NotFoundError("Search not found.") from exc


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(svc: Services = Depends(services)) -> dict:
    class NotReady(AppError):
        status_code = 503
        code = "not_ready"

    try:
        await asyncio.to_thread(svc.db.ping)
    except Exception as exc:  # noqa: BLE001
        raise NotReady("Database is not reachable.") from exc
    if not await asyncio.to_thread(svc.db.is_migrated):
        raise NotReady("Database tables are missing. Run `alembic upgrade head` in backend/.")
    return {"status": "ready"}


@router.get("/config")
async def config(svc: Services = Depends(services)) -> dict:
    """Capability report. Never includes secrets, only which settings are missing."""
    s = svc.settings
    sources = [
        {"id": c.id, "name": c.name, "kind": c.kind.value, "is_demo": c.is_demo, "configured": True}
        for c in svc.connectors.discovery
    ] + [
        {
            "id": name,
            "name": name,
            "kind": "unconfigured",
            "is_demo": False,
            "configured": False,
            "hint": hint,
        }
        for name, hint in svc.connectors.unavailable
    ]
    return {
        "app_name": s.app_name,
        "providers": svc.providers.capabilities(),
        "markets": ["india", "global"],
        "modes": ["retail", "business"],
        "demo_mode": s.demo_mode,
        "limits": {
            "max_upload_mb": s.max_upload_mb,
            "allowed_mime": sorted(ALLOWED_MIME),
            "max_quantity": 100_000,
        },
        "sources": sources,
        "currency": {
            "provider": s.fx_provider,
            "india": s.india_currency,
            "global": s.global_currency,
        },
    }


@router.post("/identify", response_model=IdentifyResponse)
async def identify(
    request: Request,
    response: Response,
    image: UploadFile = File(...),
    provider: ProviderName = Form(ProviderName.OPENAI),
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> IdentifyResponse:
    svc.limiter.check(owner, "identify", svc.settings.identify_rate_limit_per_minute)
    limit = svc.settings.max_upload_bytes
    data = await image.read(limit + 1)
    if len(data) > limit:
        raise ImageTooLargeError(
            f"Image exceeds the {svc.settings.max_upload_mb:g} MB upload limit."
        )
    return await svc.workflow.identify(data, image.content_type, SearchOptions(provider=provider))


@router.post("/identity/check", response_model=Ambiguity)
async def check_identity(
    identity: ProductIdentity,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> Ambiguity:
    """Deterministic ambiguity check for a (user-edited) identity. No LLM call."""
    svc.limiter.check(owner, "check", svc.settings.rate_limit_per_minute * 4)
    return check_ambiguity(identity)


@router.post("/searches", status_code=202, response_model=CreatedSearch)
async def create_search(
    body: CreateSearchRequest,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> CreatedSearch:
    svc.limiter.check(owner, "search", svc.settings.rate_limit_per_minute)
    active = await asyncio.to_thread(svc.repo.count_active, owner)
    if active >= svc.settings.max_concurrent_searches_per_session:
        raise ConflictError("Too many searches are still running. Wait for one to finish.")
    sid = await svc.workflow.start_search(owner, body.identity, body.options)
    return CreatedSearch(id=str(sid), state="REQUEST_RECEIVED")


@router.get("/searches", response_model=SearchPage)
async def list_searches(
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> SearchPage:
    items, total = await asyncio.to_thread(svc.repo.list_for_owner, owner, limit, offset)
    return SearchPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/searches/{search_id}", response_model=SearchDetail)
async def get_search(
    search_id: str,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> SearchDetail:
    detail = await asyncio.to_thread(svc.repo.get_detail, _uuid(search_id), owner)
    if detail is None:
        raise NotFoundError("Search not found.")
    return detail


@router.get("/searches/{search_id}/offers/{offer_id}", response_model=OfferView)
async def get_offer(
    search_id: str,
    offer_id: str,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> OfferView:
    offer = await asyncio.to_thread(svc.repo.get_offer, _uuid(search_id), offer_id, owner)
    if offer is None:
        raise NotFoundError("Offer not found.")
    return offer


@router.delete("/searches/{search_id}", status_code=204)
async def delete_search(
    search_id: str,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> Response:
    ok = await asyncio.to_thread(svc.repo.delete, _uuid(search_id), owner)
    if not ok:
        raise NotFoundError("Search not found.")
    return Response(status_code=204)


@router.get("/searches/{search_id}/events")
async def search_events(
    search_id: str,
    request: Request,
    response: Response,
    svc: Services = Depends(services),
    owner: str = Depends(owner_id),
) -> StreamingResponse:
    """Server-Sent Events: streams the persisted search state whenever it changes."""
    sid = _uuid(search_id)
    first = await asyncio.to_thread(svc.repo.get_detail, sid, owner)
    if first is None:
        raise NotFoundError("Search not found.")

    async def stream():
        last_key, idle, elapsed = None, 0.0, 0.0
        detail: SearchDetail | None = first
        while True:
            if detail is not None:
                key = (detail.progress.updated_at, len(detail.offers), detail.progress.state)
                if key != last_key:
                    last_key, idle = key, 0.0
                    yield f"event: update\ndata: {detail.model_dump_json()}\n\n"
                if detail.is_terminal:
                    yield f"event: done\ndata: {json.dumps({'state': detail.progress.state.value})}\n\n"
                    return
            if (
                await request.is_disconnected()
                or elapsed > svc.settings.search_timeout_seconds + 30
            ):
                return
            await asyncio.sleep(0.5)
            elapsed += 0.5
            idle += 0.5
            if idle >= 15:
                idle = 0.0
                yield ": keepalive\n\n"
            detail = await asyncio.to_thread(svc.repo.get_detail, sid, owner)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
