import asyncio
from decimal import Decimal

import pytest

from app.connectors.base import ConnectorError, ConnectorTemporaryError
from app.connectors.demo_fixture import DemoFixtureConnector
from app.connectors.registry import ConnectorSet
from app.pricing.fx import StaticFx
from app.providers.base import ProviderNotConfiguredError
from app.providers.registry import ProviderRegistry
from app.repositories.searches import SearchRepository
from app.schemas.common import ProviderName
from app.schemas.identity import FieldStatus
from app.schemas.offers import VerificationStatus as S
from app.schemas.search import SearchOptions, WorkflowState
from app.workflow.service import InProcessTaskRunner, WorkflowService
from tests.conftest import FakeConnector, FakeProvider
from tests.factories import api_evidence, cf, extraction, medicine, png_bytes, raw_offer


def make_service(settings, db, connectors, providers=None, **fx):
    registry = ProviderRegistry(settings, overrides=providers or {})
    cs = ConnectorSet(discovery=connectors, extractor=None, reference=None, unavailable=[])
    repo = SearchRepository(db)
    return WorkflowService(
        settings, registry, cs, StaticFx(settings.fx_static_rates), repo, InProcessTaskRunner()
    )


def good_offer(name="a", price="24"):
    return raw_offer(
        supplier_name=name,
        supplier_domain=f"{name}.example",
        price=Decimal(price),
        product_url=f"https://{name}.example/p",
        evidence=[api_evidence(price=price, url=f"https://{name}.example/p")],
    )


async def run(svc, identity=None, options=None):
    """Run a full search and return (detail, progress)."""
    options = options or SearchOptions()
    sid = svc.repo.create("owner1", identity or medicine(), options)
    await svc._run_search(sid, identity or medicine(), options)
    return svc.repo.get_detail(sid, "owner1")


# ---- identify mode ---------------------------------------------------------------------
async def test_identify_routes_to_selected_provider_only(settings, db):
    providers = {
        ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI),
        ProviderName.GEMINI: FakeProvider(ProviderName.GEMINI),
    }
    svc = make_service(settings, db, [], providers)
    res = await svc.identify(png_bytes(), "image/png", SearchOptions(provider=ProviderName.GEMINI))
    assert res.provider == "gemini" and res.model == "fake-gemini"
    assert providers[ProviderName.GEMINI].calls == 1 and providers[ProviderName.OPENAI].calls == 0
    assert res.identity.extracted_by == "gemini:fake-gemini"


async def test_identify_selected_provider_unconfigured_raises_without_fallback(settings, db):
    only_openai = {ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI)}
    svc = make_service(settings, db, [], only_openai)
    with pytest.raises(ProviderNotConfiguredError):
        await svc.identify(png_bytes(), "image/png", SearchOptions(provider=ProviderName.GEMINI))
    assert only_openai[ProviderName.OPENAI].calls == 0


async def test_identify_flags_ambiguity_instead_of_guessing(settings, db):
    out = extraction(strength=extraction().strength.model_copy(update={"value": None}))
    svc = make_service(
        settings, db, [], {ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI, out)}
    )
    res = await svc.identify(png_bytes(), "image/png", SearchOptions())
    assert res.state == WorkflowState.NEEDS_CLARIFICATION.value
    assert "strength" in res.ambiguity.missing_essentials and res.identity.strength.value is None


async def test_identify_ready_when_confirmed(settings, db):
    svc = make_service(settings, db, [], {ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI)})
    assert (await svc.identify(png_bytes(), "image/png", SearchOptions())).state == "IDENTITY_READY"


async def test_identify_invalid_image_raises_before_calling_provider(settings, db):
    from app.errors import UnsupportedImageError

    p = FakeProvider(ProviderName.OPENAI)
    svc = make_service(settings, db, [], {ProviderName.OPENAI: p})
    with pytest.raises(UnsupportedImageError):
        await svc.identify(b"hello world", "image/png", SearchOptions())
    assert p.calls == 0


# ---- full search ------------------------------------------------------------------------
async def test_full_search_results_ready_and_persisted(settings, db):
    svc = make_service(
        settings, db, [FakeConnector("c1", [good_offer("a", "24"), good_offer("b", "20")])]
    )
    d = await run(svc)
    assert d.progress.state == WorkflowState.RESULTS_READY and d.is_terminal
    assert [o.supplier_name for o in d.offers] == ["b", "a"]
    assert all(o.tier == S.VERIFIED for o in d.offers)
    assert d.progress.offers_discovered == 2 and d.progress.offers_verified == 2
    assert d.progress.sources[0].status == "ok" and d.progress.sources[0].offers == 2
    assert d.progress.completed_nodes[-1] == "finalize_results"
    assert "verify_offer_evidence" in d.progress.completed_nodes


async def test_unclear_details_do_not_block_the_search_but_are_reported(settings, db):
    conn = FakeConnector("c1", [good_offer()])
    svc = make_service(settings, db, [conn])
    d = await run(svc, identity=medicine(strength=cf("500 mg", FieldStatus.INFERRED)))
    assert conn.calls == 1 and d.progress.state == WorkflowState.RESULTS_READY
    assert any("strength" in w for w in d.progress.warnings)


async def test_missing_details_search_proceeds_but_offers_cannot_be_fully_verified(settings, db):
    ident = medicine(strength=cf(None), pack_quantity=cf(None))
    svc = make_service(settings, db, [FakeConnector("c1", [good_offer()])])
    d = await run(svc, identity=ident)
    assert d.progress.state == WorkflowState.RESULTS_READY and d.offers
    assert all(o.tier != S.VERIFIED for o in d.offers)
    assert d.progress.warnings


async def test_nothing_to_search_for_stops_with_clarification(settings, db):
    from app.schemas.identity import ProductIdentity

    conn = FakeConnector("c1", [good_offer()])
    d = await run(make_service(settings, db, [conn]), identity=ProductIdentity())
    assert d.progress.state == WorkflowState.NEEDS_CLARIFICATION and conn.calls == 0
    assert "could not be identified" in d.progress.message


async def test_unknown_pack_offers_are_still_ranked_by_pack_price(settings, db):
    ident = medicine(pack_quantity=cf(None))
    svc = make_service(
        settings, db, [FakeConnector("c1", [good_offer("a", "30"), good_offer("b", "20")])]
    )
    d = await run(svc, identity=ident)
    assert [o.supplier_name for o in d.offers] == ["b", "a"] and d.offers[0].rank == 1


async def test_no_sources_configured_is_source_unavailable(settings, db):
    d = await run(make_service(settings, db, []))
    assert d.progress.state == WorkflowState.SOURCE_UNAVAILABLE
    assert d.progress.unresolved and not d.offers


async def test_all_sources_failing_is_source_unavailable_with_errors_listed(settings, db):
    svc = make_service(settings, db, [FakeConnector("bad", error=ConnectorError("auth rejected"))])
    d = await run(svc)
    assert d.progress.state == WorkflowState.SOURCE_UNAVAILABLE
    assert (
        d.progress.sources[0].status == "error" and d.progress.sources[0].error == "auth rejected"
    )
    assert d.progress.sources[0].attempts == 1  # permanent errors are not retried


async def test_empty_but_healthy_source_is_no_matches(settings, db):
    d = await run(make_service(settings, db, [FakeConnector("c1", [])]))
    assert d.progress.state == WorkflowState.NO_MATCHES


async def test_only_rejected_offers_is_no_matches_but_audit_rows_kept(settings, db):
    wrong = raw_offer(
        declared={
            "active_ingredients": "Paracetamol",
            "strength": "650 mg",
            "dosage_form": "Tablet",
        }
    )
    d = await run(make_service(settings, db, [FakeConnector("c1", [wrong])]))
    assert d.progress.state == WorkflowState.NO_MATCHES
    assert len(d.offers) == 1 and d.offers[0].tier == S.REJECTED and d.progress.offers_rejected == 1


async def test_partial_results_when_one_source_fails(settings, db):
    svc = make_service(
        settings,
        db,
        [
            FakeConnector("ok", [good_offer()]),
            FakeConnector("bad", error=ConnectorTemporaryError("503")),
        ],
    )
    d = await run(svc)
    assert d.progress.state == WorkflowState.PARTIAL_RESULTS and d.is_terminal
    statuses = {s.connector_id: s for s in d.progress.sources}
    assert statuses["ok"].status == "ok" and statuses["bad"].status == "error"
    assert statuses["bad"].attempts == 2  # one retry for temporary errors
    assert len(d.offers) == 1


async def test_connector_timeout_is_reported_and_does_not_block_others(settings, db):
    slow = FakeConnector("slow", [good_offer("s")], delay=5)
    svc = make_service(settings, db, [slow, FakeConnector("fast", [good_offer("f")])])
    d = await run(svc)
    by_id = {s.connector_id: s for s in d.progress.sources}
    assert by_id["slow"].status == "timeout" and by_id["fast"].status == "ok"
    assert d.progress.state == WorkflowState.PARTIAL_RESULTS
    assert [o.supplier_name for o in d.offers] == ["f"]


async def test_crashing_connector_is_isolated(settings, db):
    svc = make_service(
        settings,
        db,
        [
            FakeConnector("boom", error=RuntimeError("secret internal detail")),
            FakeConnector("ok", [good_offer()]),
        ],
    )
    d = await run(svc)
    boom = next(s for s in d.progress.sources if s.connector_id == "boom")
    assert boom.status == "error" and "secret" not in (boom.error or "")
    assert d.offers


async def test_concurrency_is_bounded(settings, db):
    running, peak = 0, 0

    class Probe(FakeConnector):
        async def search_products(self, query):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return []

    s = settings.model_copy(update={"source_max_concurrency": 2})
    svc = make_service(s, db, [Probe(f"p{i}") for i in range(6)])
    await run(svc)
    assert peak == 2


async def test_sources_run_concurrently_not_serially(settings, db):
    import time

    svc = make_service(settings, db, [FakeConnector(f"c{i}", [], delay=0.2) for i in range(4)])
    t = time.perf_counter()
    await run(svc)
    assert time.perf_counter() - t < 0.6


async def test_partial_results_are_persisted_before_search_finishes(settings, db):
    seen = []
    svc = make_service(
        settings,
        db,
        [
            FakeConnector("fast", [good_offer("f")]),
            FakeConnector("slow", [good_offer("s")], delay=0.3),
        ],
    )
    options = SearchOptions()
    sid = svc.repo.create("owner1", medicine(), options)
    task = asyncio.create_task(svc._run_search(sid, medicine(), options))
    for _ in range(40):
        await asyncio.sleep(0.05)
        d = svc.repo.get_detail(sid, "owner1")
        if d.offers and not d.is_terminal:
            seen.append((d.progress.state, len(d.offers)))
            break
    await task
    assert seen and seen[0][0] == WorkflowState.PARTIAL_RESULTS and seen[0][1] == 1
    final = svc.repo.get_detail(sid, "owner1")
    assert len(final.offers) == 2 and final.progress.state == WorkflowState.RESULTS_READY


async def test_final_ranking_includes_late_cheaper_offer(settings, db):
    svc = make_service(
        settings,
        db,
        [
            FakeConnector("fast", [good_offer("f", "30")]),
            FakeConnector("slow", [good_offer("s", "10")], delay=0.2),
        ],
    )
    d = await run(svc)
    assert [o.supplier_name for o in d.offers] == ["s", "f"] and d.offers[0].rank == 1


async def test_overall_timeout_keeps_partial_results(settings, db):
    s = settings.model_copy(update={"search_timeout_seconds": 0.3, "source_timeout_seconds": 5})
    svc = make_service(
        s, db, [FakeConnector("fast", [good_offer("f")]), FakeConnector("slow", [], delay=3)]
    )
    d = await run(svc)
    assert d.progress.state == WorkflowState.PARTIAL_RESULTS and d.is_terminal
    assert "timed out" in d.progress.message and len(d.offers) == 1


async def test_overall_timeout_without_results_fails(settings, db):
    s = settings.model_copy(update={"search_timeout_seconds": 0.2, "source_timeout_seconds": 5})
    d = await run(make_service(s, db, [FakeConnector("slow", [], delay=3)]))
    assert d.progress.state == WorkflowState.FAILED and d.progress.error


async def test_connector_cannot_pre_verify_its_offers(settings, db):
    assert (
        "status" not in raw_offer().model_dump() and "verification" not in raw_offer().model_dump()
    )
    # a connector claiming evidence-free price still ends up unverified
    claim = raw_offer(evidence=[])
    d = await run(make_service(settings, db, [FakeConnector("liar", [claim])]))
    assert d.offers[0].tier == S.UNVERIFIED


async def test_demo_connector_end_to_end_is_flagged_and_never_verified(settings, db):
    d = await run(make_service(settings, db, [DemoFixtureConnector()]))
    assert d.is_demo_data_present and d.offers
    assert all(o.is_demo and o.tier != S.VERIFIED for o in d.offers)
    assert not any(o.eligible and o.tier == S.VERIFIED for o in d.offers)


async def test_interrupted_searches_marked_failed_on_restart(settings, db):
    repo = SearchRepository(db)
    sid = repo.create("o", medicine(), SearchOptions())
    assert repo.mark_interrupted() == 1
    d = repo.get_detail(sid, "o")
    assert d.progress.state == WorkflowState.FAILED and d.is_terminal


# ---- live activity feed: real events only ------------------------------------------------
def msgs(d, phase=None):
    return [e.message for e in d.progress.activity if phase is None or e.phase == phase]


async def test_activity_feed_records_what_actually_happened(settings, db):
    svc = make_service(
        settings, db, [FakeConnector("c1", [good_offer("a", "24"), good_offer("b", "20")])]
    )
    d = await run(svc)
    phases = [e.phase for e in d.progress.activity]
    assert phases[0] == "plan" and phases[-1] == "done"
    assert phases == sorted(phases, key=["plan", "search", "read", "verify", "rank", "done"].index)
    assert any("Searching for" in m for m in msgs(d, "plan"))
    assert any("Fake c1: 2 candidate(s)" in m for m in msgs(d, "search"))
    assert any("2 source-verified" in m for m in msgs(d, "verify"))
    assert any("Ranked 2 comparable offer(s)" in m for m in msgs(d, "rank"))
    assert (
        d.progress.activity[-1].level == "success"
        and "2 offers found" in d.progress.activity[-1].message
    )
    assert all(e.at.tzinfo is not None for e in d.progress.activity)


async def test_activity_feed_reports_failures_honestly(settings, db):
    svc = make_service(
        settings,
        db,
        [
            FakeConnector("ok", [good_offer()]),
            FakeConnector("bad", error=ConnectorError("auth rejected")),
        ],
    )
    d = await run(svc)
    by_msg = {e.message: e for e in d.progress.activity}
    bad = next(e for m, e in by_msg.items() if m.startswith("Fake bad:"))
    assert bad.level == "error" and "auth rejected" in bad.message
    assert d.progress.activity[-1].level == "warn"  # partial results


async def test_activity_feed_logs_each_page_read(settings, db):
    from app.connectors.registry import ConnectorSet

    class StubExtractor:
        async def get_offer_details(self, offer):
            if "good" in (offer.product_url or ""):
                return offer.model_copy(
                    update={
                        "price": Decimal("9.5"),
                        "currency": "INR",
                        "needs_page_extraction": False,
                        "evidence": [api_evidence(price="9.5", url=offer.product_url)],
                    }
                )
            return None

    def cand(host):
        return raw_offer(
            supplier_name=host,
            supplier_domain=host,
            price=None,
            currency=None,
            product_url=f"https://{host}/good" if host.startswith("g") else f"https://{host}/x",
            needs_page_extraction=True,
            evidence=[],
        )

    cs = ConnectorSet(
        discovery=[FakeConnector("web", [cand("good.example"), cand("bad.example")])],
        extractor=StubExtractor(),
        reference=None,
        unavailable=[],
    )
    svc = WorkflowService(
        settings,
        ProviderRegistry(settings),
        cs,
        StaticFx(""),
        SearchRepository(db),
        InProcessTaskRunner(),
    )
    d = await run(svc)
    read = msgs(d, "read")
    assert any("Reading 2 supplier page(s)" in m for m in read)
    assert any("good.example: found INR 9.50" in m for m in read)
    assert any("bad.example: no readable price" in m for m in read)
    assert any(
        "No verifiable price could be read from bad.example" in u for u in d.progress.unresolved
    )


async def test_skipped_unconfigured_source_is_visible_in_the_feed(settings, db):
    from app.connectors.registry import ConnectorSet

    cs = ConnectorSet(
        discovery=[FakeConnector("c1", [good_offer()])],
        extractor=None,
        reference=None,
        unavailable=[
            ("Public web discovery (Tavily)", "Set TAVILY_API_KEY to enable public-web discovery.")
        ],
    )
    svc = WorkflowService(
        settings,
        ProviderRegistry(settings),
        cs,
        StaticFx(""),
        SearchRepository(db),
        InProcessTaskRunner(),
    )
    d = await run(svc)
    assert any(
        "Skipped Public web discovery (Tavily): Set TAVILY_API_KEY" in m for m in msgs(d, "plan")
    )
