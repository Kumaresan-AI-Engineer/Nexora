import json
import time

from app.connectors.base import ConnectorError
from app.providers.base import ProviderQuotaError
from app.schemas.common import ProviderName
from tests.conftest import FakeConnector, FakeProvider, make_settings
from tests.factories import api_evidence, medicine, noisy_png, png_bytes, raw_offer


def good_offer(name="a", price="24"):
    from decimal import Decimal

    return raw_offer(
        supplier_name=name,
        supplier_domain=f"{name}.example",
        price=Decimal(price),
        product_url=f"https://{name}.example/p",
        evidence=[api_evidence(price=price, url=f"https://{name}.example/p")],
    )


def wait_done(client, sid, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        d = client.get(f"/api/searches/{sid}").json()
        if d["is_terminal"]:
            return d
        time.sleep(0.05)
    raise AssertionError("search did not finish")


def start(client, **opts):
    body = {"identity": medicine().model_dump(mode="json"), "options": opts}
    r = client.post("/api/searches", json=body)
    assert r.status_code == 202, r.text
    return r.json()["id"]


def test_health_ready_and_config_without_secrets(make_client):
    c = make_client()
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/ready").json() == {"status": "ready"}
    cfg = c.get("/api/config").json()
    assert {p["provider"] for p in cfg["providers"]} == {"openai", "gemini"}
    assert cfg["limits"]["allowed_mime"] == ["image/jpeg", "image/png", "image/webp"]
    text = json.dumps(cfg)
    assert "api_key" not in text.lower().replace("_api_key", "x") or "sk-" not in text


def test_config_reports_missing_provider_settings(tmp_path, make_client):
    c = make_client(providers={})
    cfg = c.get("/api/config").json()
    openai = next(p for p in cfg["providers"] if p["provider"] == "openai")
    assert not openai["configured"] and openai["missing"] == [
        "OPENAI_API_KEY",
        "OPENAI_VISION_MODEL",
    ]


def test_identify_happy_path_and_selected_provider(make_client, fake_providers):
    c = make_client()
    r = c.post(
        "/api/identify",
        files={"image": ("pack.png", png_bytes(), "image/png")},
        data={"provider": "gemini"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (
        body["provider"] == "gemini"
        and body["identity"]["active_ingredients"]["status"] == "confirmed"
    )
    assert (
        fake_providers[ProviderName.GEMINI].calls == 1
        and fake_providers[ProviderName.OPENAI].calls == 0
    )


def test_identify_unconfigured_provider_returns_clear_error(make_client):
    c = make_client(providers={ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI)})
    r = c.post(
        "/api/identify",
        files={"image": ("p.png", png_bytes(), "image/png")},
        data={"provider": "gemini"},
    )
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "provider_not_configured" and "GEMINI_API_KEY" in err["message"]


def test_identify_rejects_bad_uploads(make_client):
    c = make_client()
    r = c.post("/api/identify", files={"image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_image"
    r = c.post("/api/identify", files={"image": ("x.png", png_bytes(), "image/jpeg")})
    assert r.status_code == 415
    r = c.post("/api/identify", files={"image": ("x.png", b"", "image/png")})
    assert r.status_code == 422
    assert c.post("/api/identify", data={"provider": "openai"}).status_code == 422
    r = c.post(
        "/api/identify",
        files={"image": ("x.png", png_bytes(), "image/png")},
        data={"provider": "claude"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_identify_oversize_rejected(tmp_path, make_client):
    c = make_client(settings_override=make_settings(tmp_path, max_upload_mb=0.001))
    r = c.post("/api/identify", files={"image": ("x.png", noisy_png(), "image/png")})
    assert r.status_code == 413


def test_provider_quota_error_surfaces_as_429(make_client):
    p = {
        ProviderName.OPENAI: FakeProvider(
            ProviderName.OPENAI, error=ProviderQuotaError("quota hit")
        ),
        ProviderName.GEMINI: FakeProvider(ProviderName.GEMINI),
    }
    c = make_client(providers=p)
    r = c.post(
        "/api/identify",
        files={"image": ("x.png", png_bytes(), "image/png")},
        data={"provider": "openai"},
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "provider_quota_exceeded"


def test_search_lifecycle_and_offer_detail(make_client):
    c = make_client(
        connectors=[FakeConnector("c1", [good_offer("a", "24"), good_offer("b", "20")])]
    )
    sid = start(c, mode="retail", market="india", quantity=2)
    d = wait_done(c, sid)
    assert d["progress"]["state"] == "RESULTS_READY"
    assert [o["supplier_name"] for o in d["offers"]] == ["b", "a"]
    assert d["offers"][0]["pricing"]["requested_cost"] == 40.0
    assert d["offers"][0]["verification"]["status"] == "VERIFIED"
    oid = d["offers"][0]["offer_id"]
    o = c.get(f"/api/searches/{sid}/offers/{oid}").json()
    assert o["evidence"][0]["type"] == "api_response"
    assert c.get(f"/api/searches/{sid}/offers/nope").status_code == 404
    hist = c.get("/api/searches").json()
    assert hist["total"] == 1 and hist["items"][0]["state"] == "RESULTS_READY"


def test_search_ownership_enforced(make_client):
    owner = make_client(connectors=[FakeConnector("c1", [good_offer()])])
    sid = start(owner)
    wait_done(owner, sid)
    oid = owner.get(f"/api/searches/{sid}").json()["offers"][0]["offer_id"]
    # same app, different browser session
    other = type(owner)(owner.app)
    other.__enter__()
    try:
        assert other.get(f"/api/searches/{sid}").status_code == 404
        assert other.get(f"/api/searches/{sid}/offers/{oid}").status_code == 404
        assert other.delete(f"/api/searches/{sid}").status_code == 404
        assert other.get(f"/api/searches/{sid}/events").status_code == 404
        assert other.get("/api/searches").json()["total"] == 0
    finally:
        other.__exit__(None, None, None)
    assert owner.get(f"/api/searches/{sid}").status_code == 200


def test_forged_or_malformed_session_cookie_gets_new_identity(make_client):
    owner = make_client(connectors=[FakeConnector("c1", [good_offer()])])
    sid = start(owner)
    wait_done(owner, sid)
    owner.cookies.clear()
    owner.cookies.set("ps_session", "../../etc/passwd")
    assert owner.get(f"/api/searches/{sid}").status_code == 404


def test_session_cookie_is_httponly(make_client):
    c = make_client()
    r = c.get("/api/searches")
    assert (
        "httponly" in r.headers["set-cookie"].lower()
        and "samesite=lax" in r.headers["set-cookie"].lower()
    )


def test_invalid_search_id_and_validation(make_client):
    c = make_client()
    assert c.get("/api/searches/not-a-uuid").status_code == 404
    bad = {"identity": medicine().model_dump(mode="json"), "options": {"quantity": 0}}
    assert c.post("/api/searches", json=bad).status_code == 422
    bad = {
        "identity": medicine().model_dump(mode="json"),
        "options": {"min_price": 10, "max_price": 5},
    }
    assert c.post("/api/searches", json=bad).status_code == 422
    bad = {"identity": medicine().model_dump(mode="json"), "options": {"provider": "x"}}
    assert c.post("/api/searches", json=bad).status_code == 422


def test_concurrent_search_limit(tmp_path, make_client):
    s = make_settings(tmp_path, max_concurrent_searches_per_session=1)
    c = make_client(connectors=[FakeConnector("slow", [], delay=1.0)], settings_override=s)
    start(c)
    r = c.post("/api/searches", json={"identity": medicine().model_dump(mode="json")})
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_rate_limit(tmp_path, make_client):
    s = make_settings(tmp_path, identify_rate_limit_per_minute=2)
    c = make_client(settings_override=s)
    codes = [
        c.post("/api/identify", files={"image": ("x.png", png_bytes(), "image/png")}).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_failed_source_visible_in_api(make_client):
    c = make_client(connectors=[FakeConnector("bad", error=ConnectorError("nope"))])
    d = wait_done(c, start(c))
    assert d["progress"]["state"] == "SOURCE_UNAVAILABLE"
    assert d["progress"]["sources"][0]["error"] == "nope"


def test_delete_search(make_client):
    c = make_client(connectors=[FakeConnector("c1", [good_offer()])])
    sid = start(c)
    wait_done(c, sid)
    assert c.delete(f"/api/searches/{sid}").status_code == 204
    assert c.get(f"/api/searches/{sid}").status_code == 404


def test_sse_streams_updates_and_completes(make_client):
    c = make_client(connectors=[FakeConnector("c1", [good_offer()], delay=0.2)])
    sid = start(c)
    events = []
    with c.stream("GET", f"/api/searches/{sid}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((name, json.loads(line.split(":", 1)[1])))
    assert events[-1][0] == "done" and events[-1][1]["state"] == "RESULTS_READY"
    updates = [e for e in events if e[0] == "update"]
    assert updates and updates[-1][1]["progress"]["state"] == "RESULTS_READY"
    assert updates[-1][1]["offers"][0]["supplier_name"] == "a"


def test_identity_check_endpoint_is_deterministic(make_client):
    c = make_client()
    ok = c.post("/api/identity/check", json=medicine().model_dump(mode="json")).json()
    assert ok["needs_clarification"] is False
    bad = medicine().model_dump(mode="json")
    bad["strength"] = {"value": None, "status": "unknown", "evidence": None}
    r = c.post("/api/identity/check", json=bad).json()
    assert r["needs_clarification"] and "strength" in r["missing_essentials"]


def test_security_headers_and_oversized_identity_rejected(make_client):
    c = make_client()
    r = c.get("/api/health")
    assert (
        r.headers["x-content-type-options"] == "nosniff"
        and r.headers["cache-control"] == "no-store"
    )
    big = medicine().model_dump(mode="json")
    big["strength"]["value"] = "x" * 5000
    assert c.post("/api/identity/check", json=big).status_code == 422
    big = medicine().model_dump(mode="json")
    big["notes"] = ["n"] * 100
    assert c.post("/api/identity/check", json=big).status_code == 422


def test_ready_reports_unmigrated_database_clearly(tmp_path):
    from fastapi.testclient import TestClient

    from app.connectors.registry import ConnectorSet
    from app.db import Database
    from app.main import create_app
    from app.providers.registry import ProviderRegistry

    s = make_settings(tmp_path)
    empty = Database(s.database_url)  # tables deliberately not created
    app = create_app(
        s,
        db=empty,
        providers=ProviderRegistry(s),
        connectors=ConnectorSet(discovery=[], extractor=None, reference=None, unavailable=[]),
    )
    with TestClient(app) as c:  # startup must not crash without tables
        r = c.get("/api/ready")
        assert r.status_code == 503 and "alembic upgrade head" in r.json()["error"]["message"]
        assert c.get("/api/health").status_code == 200
