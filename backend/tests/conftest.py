import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.connectors.base import ConnectorKind, SupplierConnector
from app.connectors.registry import ConnectorSet
from app.db import Database
from app.main import create_app
from app.pricing.fx import StaticFx
from app.providers.base import VisionProvider
from app.providers.registry import ProviderRegistry
from app.schemas.common import ProviderName
from tests.factories import extraction


class FakeProvider(VisionProvider):
    def __init__(self, name: ProviderName, output=None, error: Exception | None = None):
        self.name = name
        self.model = f"fake-{name.value}"
        self.output = output or extraction()
        self.error = error
        self.calls = 0

    async def analyze(self, image):
        self.calls += 1
        if self.error:
            raise self.error
        return self.output


class FakeConnector(SupplierConnector):
    kind = ConnectorKind.CATALOGUE_API

    def __init__(self, cid, offers=None, error: Exception | None = None, delay: float = 0.0):
        self.id = cid
        self.name = f"Fake {cid}"
        self._offers = offers or []
        self._error = error
        self._delay = delay
        self.calls = 0

    async def search_products(self, query):
        import asyncio

        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return list(self._offers)


def make_settings(tmp_path, **over) -> Settings:
    base = dict(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        environment="test",
        openai_api_key="",
        gemini_api_key="",
        tavily_api_key="",
        source_timeout_seconds=0.5,
        source_max_retries=1,
        rate_limit_per_minute=1000,
        identify_rate_limit_per_minute=1000,
        fx_provider="static",
        fx_static_rates="USD>INR=80",
        search_timeout_seconds=10,
    )
    base.update(over)
    return Settings(_env_file=None, **base)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def db(settings):
    d = Database(settings.database_url)
    d.create_all()
    return d


@pytest.fixture
def fake_providers():
    return {
        ProviderName.OPENAI: FakeProvider(ProviderName.OPENAI),
        ProviderName.GEMINI: FakeProvider(ProviderName.GEMINI),
    }


@pytest.fixture
def make_client(settings, db, fake_providers):
    clients = []

    def _make(connectors=None, providers=None, settings_override=None):
        s = settings_override or settings
        registry = ProviderRegistry(s, overrides=fake_providers if providers is None else providers)
        cs = ConnectorSet(
            discovery=connectors or [], extractor=None, reference=None, unavailable=[]
        )
        app = create_app(
            s, db=db, providers=registry, connectors=cs, fx=StaticFx(s.fx_static_rates)
        )
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)
