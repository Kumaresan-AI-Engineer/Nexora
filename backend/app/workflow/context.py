"""Runtime dependencies and progress reporting for one workflow run (no global state)."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.config import Settings
from app.connectors.registry import ConnectorSet
from app.pricing.fx import FxProvider
from app.providers.registry import ProviderRegistry
from app.repositories.searches import SearchRepository
from app.schemas.offers import OfferView
from app.schemas.search import ActivityEvent, Progress

log = logging.getLogger("pharmasource.workflow")


@dataclass
class WorkflowContext:
    settings: Settings
    providers: ProviderRegistry
    connectors: ConnectorSet
    fx: FxProvider
    repo: SearchRepository | None = None
    search_id: uuid.UUID | None = None
    progress: Progress = field(default_factory=Progress)
    latest_views: list[OfferView] = field(default_factory=list)
    clock: type[datetime] = datetime
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def now(self) -> datetime:
        return self.clock.now(UTC)

    async def event(self, phase: str, level: str, message: str) -> None:
        """Record a real workflow step and persist it so the live feed shows it."""
        self.progress.activity.append(
            ActivityEvent(at=self.now(), phase=phase, level=level, message=message[:300])  # type: ignore[arg-type]
        )
        del self.progress.activity[:-200]
        await self.push()

    def elapsed(self) -> float:
        return (self.now() - self.started_at).total_seconds()

    async def push(self) -> None:
        """Persist the checkpoint (progress) so status/SSE readers see real state only."""
        if self.repo and self.search_id:
            await asyncio.to_thread(self.repo.save_progress, self.search_id, self.progress)

    async def save_views(self, views: list[OfferView]) -> None:
        self.latest_views = views
        p = self.progress
        count = lambda t: sum(1 for v in views if v.tier.value == t)  # noqa: E731
        p.offers_verified = count("VERIFIED")
        p.offers_partially_verified = count("PARTIALLY_VERIFIED")
        p.offers_unverified = count("UNVERIFIED")
        p.offers_rejected = count("REJECTED")
        if self.repo and self.search_id:
            await asyncio.to_thread(self.repo.save_results, self.search_id, views, p)
