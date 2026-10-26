import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import RateLimiter, Services
from app.api.routes import router
from app.config import Settings, get_settings
from app.connectors.registry import ConnectorSet, build_connectors
from app.db import Database
from app.errors import install_error_handlers
from app.logging_setup import configure_logging
from app.pricing.fx import FxProvider, make_fx_provider
from app.providers.registry import ProviderRegistry
from app.repositories.searches import SearchRepository
from app.workflow.service import InProcessTaskRunner, TaskRunner, WorkflowService

log = logging.getLogger("pharmasource")


def create_app(
    settings: Settings | None = None,
    *,
    db: Database | None = None,
    providers: ProviderRegistry | None = None,
    connectors: ConnectorSet | None = None,
    fx: FxProvider | None = None,
    runner: TaskRunner | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    db = db or Database(settings.database_url)
    providers = providers or ProviderRegistry(settings)
    connectors = connectors or build_connectors(settings)
    fx = fx or make_fx_provider(settings.fx_provider, settings.fx_static_rates)
    runner = runner or InProcessTaskRunner()
    repo = SearchRepository(db)
    workflow = WorkflowService(settings, providers, connectors, fx, repo, runner)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            interrupted = repo.mark_interrupted()
            if interrupted:
                log.warning("marked %d interrupted searches as failed", interrupted)
        except SQLAlchemyError:
            log.error(
                "Database is not ready (tables missing?). Run `alembic upgrade head` in backend/. "
                "The API will answer /api/ready with 503 until then."
            )
        yield
        await runner.shutdown()

    app = FastAPI(title=f"{settings.app_name} API", version="0.1.0", lifespan=lifespan)
    app.state.services = Services(
        settings, db, providers, connectors, fx, repo, runner, workflow, RateLimiter()
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router)
    return app


def app_factory() -> FastAPI:
    """uvicorn --factory app.main:app_factory"""
    return create_app()
