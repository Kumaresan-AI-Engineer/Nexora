"""Workflow nodes. Each is a small async function over typed state; only analyze_image calls an LLM."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from langchain_core.runnables import RunnableConfig

from app.connectors.base import (
    ConnectorError,
    ConnectorQuery,
    ConnectorTemporaryError,
    SupplierConnector,
)
from app.errors import AppError
from app.identification.image_validation import prepare_image
from app.identification.rules import check_ambiguity, identity_from_extraction, is_searchable
from app.pricing.fx import FxRate
from app.pricing.pipeline import (
    assemble_views,
    deduplicate,
    price_all,
    verify_all,
)
from app.schemas.common import Market
from app.schemas.offers import RawOffer, VerificationStatus
from app.schemas.search import SourceStatus, WorkflowState
from app.workflow.context import WorkflowContext
from app.workflow.state import GraphState

log = logging.getLogger("pharmasource.workflow")
NodeFn = Callable[[GraphState, WorkflowContext], Awaitable[dict]]


def node(name: str, label: WorkflowState | None = None, message: str = ""):
    """Wrap a node: record real progress before/after it runs and persist the checkpoint."""

    def deco(fn: NodeFn):
        async def wrapper(state: GraphState, config: RunnableConfig) -> dict:
            ctx: WorkflowContext = config["configurable"]["ctx"]
            p = ctx.progress
            p.current_node = name
            if label:
                p.state = label
            if message:
                p.message = message
            await ctx.push()
            result = await fn(state, ctx)
            if name not in p.completed_nodes:
                p.completed_nodes.append(name)
            return result

        wrapper.__name__ = name
        return wrapper

    return deco


def target_currency(ctx: WorkflowContext, market: Market) -> str:
    s = ctx.settings
    return s.india_currency if market == Market.INDIA else s.global_currency


async def fetch_rates(
    ctx: WorkflowContext, offers: list[RawOffer], target: str
) -> dict[str, FxRate]:
    currencies = {
        o.currency.upper() for o in offers if o.currency and o.currency.upper() != target.upper()
    }
    results = await asyncio.gather(*(ctx.fx.get_rate(c, target) for c in currencies))
    return {c: r for c, r in zip(currencies, results, strict=True) if r is not None}


# --------------------------------------------------------------------------------------
@node("validate_request", WorkflowState.REQUEST_RECEIVED, "Validating request.")
async def validate_request(state: GraphState, ctx: WorkflowContext) -> dict:
    s = ctx.settings
    if state["run_mode"] == "identify_only":
        try:
            image = await asyncio.to_thread(
                prepare_image,
                state.get("image_bytes") or b"",
                state.get("image_mime"),
                max_bytes=s.max_upload_bytes,
                max_pixels=s.max_image_pixels,
                max_side=s.image_max_side,
            )
        except AppError as exc:
            return {"exception": exc, "failure_message": exc.message}
        return {"image": image, "image_bytes": None}
    if state.get("identity") is None:
        exc = AppError("A product identity is required to start a search.")
        return {"exception": exc, "failure_message": exc.message}
    return {}


def route_after_validate(state: GraphState) -> str:
    if state.get("exception"):
        return "finalize_results"
    return "check_identity_ambiguity" if state.get("identity") else "analyze_image"


@node("analyze_image", WorkflowState.IDENTIFYING_PRODUCT, "Reading the product image.")
async def analyze_image(state: GraphState, ctx: WorkflowContext) -> dict:
    options = state["options"]
    try:
        provider = ctx.providers.get(options.provider)
        started = time.perf_counter()
        extraction = await provider.analyze(state["image"])
    except AppError as exc:
        log.warning(
            "image analysis failed",
            extra={"ctx": {"provider": options.provider.value, "code": exc.code}},
        )
        return {"exception": exc, "failure_message": exc.message}
    ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "image analyzed",
        extra={
            "ctx": {"provider": provider.name.value, "model": provider.model, "duration_ms": ms}
        },
    )
    return {
        "extraction": extraction,
        "provider_info": {
            "provider": provider.name.value,
            "model": provider.model,
            "duration_ms": ms,
        },
    }


def route_after_analyze(state: GraphState) -> str:
    return "finalize_results" if state.get("exception") else "resolve_product_identity"


@node("resolve_product_identity", message="Resolving product identity.")
async def resolve_product_identity(state: GraphState, ctx: WorkflowContext) -> dict:
    info = state["provider_info"]
    identity = identity_from_extraction(state["extraction"], f"{info['provider']}:{info['model']}")
    return {"identity": identity}


@node("check_identity_ambiguity", message="Checking which details are clear.")
async def check_identity_ambiguity(state: GraphState, ctx: WorkflowContext) -> dict:
    amb = check_ambiguity(state["identity"])
    if state["run_mode"] == "full":
        # Unclear details do not block a search; they limit verification and are shown to the user.
        ctx.progress.warnings = list(amb.messages)
        searchable = is_searchable(state["identity"])
        if searchable:
            await ctx.event("plan", "info", f"Searching for {state['identity'].display_name()}")
            if amb.messages:
                await ctx.event(
                    "plan",
                    "warn",
                    "Some details were unclear on the pack: " + " ".join(amb.messages),
                )
            else:
                await ctx.event("plan", "success", "All essential product details were readable")
    return {"ambiguity": amb, "searchable": is_searchable(state["identity"])}


def route_after_ambiguity(state: GraphState) -> str:
    if state["run_mode"] == "identify_only" or not state["searchable"]:
        return "finalize_results"
    return "discover_supplier_sources"


@node("discover_supplier_sources", WorkflowState.SEARCHING_SUPPLIERS, "Selecting supplier sources.")
async def discover_supplier_sources(state: GraphState, ctx: WorkflowContext) -> dict:
    market = state["options"].market
    active = [c for c in ctx.connectors.discovery if market in c.markets]
    ctx.progress.sources = [
        SourceStatus(
            connector_id=c.id, name=c.name, kind=c.kind.value, is_demo=c.is_demo, status="pending"
        )
        for c in active
    ]
    for name, hint in ctx.connectors.unavailable:
        ctx.progress.sources.append(
            SourceStatus(
                connector_id=name,
                name=name,
                kind="unconfigured",
                status="skipped",
                error=hint or "Not configured.",
            )
        )
    if active:
        await ctx.event(
            "plan",
            "info",
            f"Querying {len(active)} source(s): " + ", ".join(c.name for c in active),
        )
    for name, hint in ctx.connectors.unavailable:
        await ctx.event("plan", "warn", f"Skipped {name}: {hint or 'not configured'}")
    if not active:
        await ctx.event("plan", "error", "No supplier source is available")
        ctx.progress.unresolved.append(
            "No supplier source is available. "
            + " ".join(h for _, h in ctx.connectors.unavailable if h)
        )
    return {}


async def _run_connector(
    conn: SupplierConnector,
    status: SourceStatus,
    query: ConnectorQuery,
    ctx: WorkflowContext,
    sem: asyncio.Semaphore,
) -> list[RawOffer]:
    s = ctx.settings
    async with sem:
        started = time.perf_counter()
        await ctx.event("search", "info", f"Searching {conn.name}")
        for _attempt in range(1 + s.source_max_retries):
            status.attempts += 1
            try:
                offers = await asyncio.wait_for(
                    conn.search_products(query), s.source_timeout_seconds
                )
                status.status, status.offers, status.error = "ok", len(offers), None
                break
            except TimeoutError:
                status.status, status.error = (
                    "timeout",
                    f"No response within {s.source_timeout_seconds:g}s.",
                )
            except ConnectorTemporaryError as exc:
                status.status, status.error = "error", str(exc)
            except ConnectorError as exc:
                status.status, status.error = "error", str(exc)
                break
            except Exception as exc:  # noqa: BLE001 - a broken connector must not sink the search
                log.exception("connector crashed: %s", conn.id)
                status.status, status.error = "error", f"Unexpected {type(exc).__name__}."
                break
        else:
            offers = []
        status.duration_ms = int((time.perf_counter() - started) * 1000)
        secs = (status.duration_ms or 0) / 1000
        if status.status == "ok":
            await ctx.event(
                "search", "success", f"{conn.name}: {len(offers)} candidate(s) in {secs:.1f} s"
            )
        else:
            level = "warn" if status.status == "timeout" else "error"
            await ctx.event(
                "search",
                level,
                f"{conn.name}: {status.error or status.status} ({status.attempts} attempt(s))",
            )
        return offers if status.status == "ok" else []


@node("search_supplier_connectors", message="Searching supplier sources.")
async def search_supplier_connectors(state: GraphState, ctx: WorkflowContext) -> dict:
    options, identity = state["options"], state["identity"]
    active = {c.id: c for c in ctx.connectors.discovery if options.market in c.markets}
    pending = {s.connector_id: s for s in ctx.progress.sources if s.connector_id in active}
    query = ConnectorQuery(identity, options.market, options.mode, options.quantity)
    sem = asyncio.Semaphore(max(1, ctx.settings.source_max_concurrency))
    raw: list[RawOffer] = []
    target = target_currency(ctx, options.market)
    tasks = [
        asyncio.create_task(_run_connector(active[cid], st, query, ctx, sem))
        for cid, st in pending.items()
    ]
    for fut in asyncio.as_completed(tasks):
        offers = await fut
        if offers:
            raw.extend(offers)
            ctx.progress.offers_discovered = len(raw)
            deduped = deduplicate(raw)
            rates = await fetch_rates(ctx, raw, target)
            views = assemble_views(
                deduped,
                verify_all(identity, deduped, ctx.now(), ctx.settings.offer_max_age_hours),
                price_all(identity, options, deduped, target_currency=target, rates=rates),
                options,
            )
            done = sum(1 for s in pending.values() if s.status != "pending")
            ctx.progress.state = WorkflowState.PARTIAL_RESULTS
            ctx.progress.message = (
                f"{len(raw)} candidate offers from {done} of {len(pending)} sources so far."
            )
            await ctx.save_views(views)
        await ctx.push()
    return {"raw_offers": raw}


def route_after_search(state: GraphState) -> str:
    return "extract_and_normalize_offers" if state.get("raw_offers") else "finalize_results"


@node(
    "extract_and_normalize_offers",
    WorkflowState.VERIFYING_OFFERS,
    "Reading supplier pages and normalising offers.",
)
async def extract_and_normalize_offers(state: GraphState, ctx: WorkflowContext) -> dict:
    extractor = ctx.connectors.extractor
    sem = asyncio.Semaphore(max(1, ctx.settings.source_max_concurrency))
    timeout = ctx.settings.page_fetch_timeout_seconds * 2

    to_read = sum(1 for o in state["raw_offers"] if o.needs_page_extraction)
    if to_read and extractor is not None:
        await ctx.event("read", "info", f"Reading {to_read} supplier page(s) for prices")

    async def enrich(o: RawOffer) -> RawOffer:
        if not o.needs_page_extraction or extractor is None:
            return o
        host = (urlsplit(o.product_url or "").hostname or "a result").removeprefix("www.")
        async with sem:
            try:
                better = await asyncio.wait_for(extractor.get_offer_details(o), timeout)
            except Exception:  # noqa: BLE001 - extraction is best effort
                better = None
        if better is None:
            ctx.progress.unresolved.append(f"No verifiable price could be read from {host}.")
            await ctx.event("read", "warn", f"{host}: no readable price on the page")
            return o
        await ctx.event(
            "read", "success", f"{host}: found {better.currency} {better.price:.2f} on the page"
        )
        return better

    offers = list(await asyncio.gather(*(enrich(o) for o in state["raw_offers"])))
    for o in offers:
        if o.currency:
            o.currency = o.currency.strip().upper()
    ctx.progress.offers_discovered = len(offers)
    return {"raw_offers": offers}


@node("deduplicate_offers", message="Merging duplicate listings.")
async def deduplicate_offers(state: GraphState, ctx: WorkflowContext) -> dict:
    deduped = deduplicate(state["raw_offers"])
    merged = sum(n for _, n in deduped)
    if merged:
        await ctx.event("verify", "info", f"Merged {merged} duplicate listing(s)")
    return {"deduped": deduped}


@node("verify_offer_evidence", WorkflowState.VERIFYING_OFFERS, "Verifying offer evidence.")
async def verify_offer_evidence(state: GraphState, ctx: WorkflowContext) -> dict:
    verifications = verify_all(
        state["identity"], state["deduped"], ctx.now(), ctx.settings.offer_max_age_hours
    )
    counts = {st: 0 for st in VerificationStatus}
    for v in verifications.values():
        counts[v.status] += 1
    await ctx.event(
        "verify",
        "success",
        f"Checked evidence for {len(verifications)} offer(s): {counts[VerificationStatus.VERIFIED]} "
        f"source-verified, {counts[VerificationStatus.PARTIALLY_VERIFIED]} partially verified, "
        f"{counts[VerificationStatus.UNVERIFIED]} unverified, {counts[VerificationStatus.REJECTED]} rejected",
    )
    return {"verifications": verifications}


@node("calculate_comparable_costs", message="Calculating comparable costs.")
async def calculate_comparable_costs(state: GraphState, ctx: WorkflowContext) -> dict:
    options, identity = state["options"], state["identity"]
    target = target_currency(ctx, options.market)
    rates = await fetch_rates(ctx, [o for o, _ in state["deduped"]], target)
    reference = ctx.connectors.reference.lookup(identity) if ctx.connectors.reference else None
    await ctx.event(
        "verify", "info", f"Comparing prices in {target} for {options.quantity} pack(s)"
    )
    return {
        "pricings": price_all(
            identity,
            options,
            state["deduped"],
            target_currency=target,
            rates=rates,
            reference=reference,
        )
    }


@node("rank_eligible_offers", message="Ranking eligible offers.")
async def rank_eligible_offers(state: GraphState, ctx: WorkflowContext) -> dict:
    views = assemble_views(
        state["deduped"], state["verifications"], state["pricings"], state["options"]
    )
    await ctx.save_views(views)
    ranked = sum(1 for v in views if v.rank is not None)
    await ctx.event("rank", "success", f"Ranked {ranked} comparable offer(s) by cost")
    return {"views": views}


def decide_final(state: GraphState, ctx: WorkflowContext) -> tuple[WorkflowState, str]:
    if state.get("exception"):
        return WorkflowState.FAILED, state.get("failure_message") or "The request failed."
    amb = state.get("ambiguity")
    if state["run_mode"] == "identify_only":
        if amb and amb.needs_clarification:
            return WorkflowState.NEEDS_CLARIFICATION, " ".join(amb.messages)
        return WorkflowState.IDENTITY_READY, "Product identity ready."
    if not state.get("searchable", True):
        return (
            WorkflowState.NEEDS_CLARIFICATION,
            "The product could not be identified from the image. Try a clearer photo of the front of the pack, "
            "or type the product name under the identified details.",
        )
    sources = [s for s in ctx.progress.sources if s.kind != "unconfigured"]
    ok = [s for s in sources if s.status == "ok"]
    failed = [s for s in sources if s.status in ("error", "timeout")]
    if not sources or not ok:
        return WorkflowState.SOURCE_UNAVAILABLE, "No supplier source returned results."
    usable = [v for v in state.get("views", []) if v.tier != VerificationStatus.REJECTED]
    if not usable:
        extra = f" {len(failed)} source(s) failed." if failed else ""
        return WorkflowState.NO_MATCHES, "No offers matched the identified product." + extra
    if failed:
        return (
            WorkflowState.PARTIAL_RESULTS,
            f"{len(failed)} of {len(sources)} sources failed; results may be incomplete.",
        )
    return WorkflowState.RESULTS_READY, f"{len(usable)} offers found."


@node("finalize_results")
async def finalize_results(state: GraphState, ctx: WorkflowContext) -> dict:
    final, message = decide_final(state, ctx)
    p = ctx.progress
    p.state, p.message, p.finished = final, message, True
    p.current_node = None
    level = (
        "error"
        if final in (WorkflowState.FAILED, WorkflowState.SOURCE_UNAVAILABLE)
        else "warn"
        if final
        in (
            WorkflowState.PARTIAL_RESULTS,
            WorkflowState.NEEDS_CLARIFICATION,
            WorkflowState.NO_MATCHES,
        )
        else "success"
    )
    if state.get("run_mode") == "full":
        await ctx.event("done", level, f"{message} ({ctx.elapsed():.1f} s)")
    p.completed_nodes.append("finalize_results")
    if final == WorkflowState.FAILED:
        p.error = message
    await ctx.push()
    return {"final_state": final}
