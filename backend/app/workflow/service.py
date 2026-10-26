"""Entry points around the graph, plus the background task abstraction.

`TaskRunner` is deliberately tiny: swap InProcessTaskRunner for a Redis/worker-backed one without
touching the workflow.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any

from app.config import Settings
from app.connectors.registry import ConnectorSet
from app.errors import AppError
from app.pricing.fx import FxProvider
from app.providers.registry import ProviderRegistry
from app.repositories.searches import SearchRepository
from app.schemas.identity import IdentifyResponse, ProductIdentity
from app.schemas.search import Progress, SearchOptions, WorkflowState
from app.workflow.context import WorkflowContext
from app.workflow.graph import build_graph

log = logging.getLogger("pharmasource.workflow")


class TaskRunner(ABC):
    @abstractmethod
    def submit(self, name: str, coro: Coroutine[Any, Any, None]) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...


class InProcessTaskRunner(TaskRunner):
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def submit(self, name: str, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


class WorkflowService:
    def __init__(
        self,
        settings: Settings,
        providers: ProviderRegistry,
        connectors: ConnectorSet,
        fx: FxProvider,
        repo: SearchRepository,
        runner: TaskRunner,
    ):
        self.settings, self.providers, self.connectors = settings, providers, connectors
        self.fx, self.repo, self.runner = fx, repo, runner
        self._graph = build_graph()

    def _ctx(self, **kw) -> WorkflowContext:
        return WorkflowContext(self.settings, self.providers, self.connectors, self.fx, **kw)

    async def identify(
        self, image_bytes: bytes, mime: str | None, options: SearchOptions
    ) -> IdentifyResponse:
        ctx = self._ctx()
        state = await self._graph.ainvoke(
            {
                "run_mode": "identify_only",
                "options": options,
                "image_bytes": image_bytes,
                "image_mime": mime,
            },
            config={"configurable": {"ctx": ctx}},
        )
        exc: AppError | None = state.get("exception")
        if exc:
            raise exc
        info = state["provider_info"]
        return IdentifyResponse(
            identity=state["identity"],
            ambiguity=state["ambiguity"],
            provider=info["provider"],
            model=info["model"],
            duration_ms=info["duration_ms"],
            state=state["final_state"].value,
        )

    async def start_search(
        self, owner: str, identity: ProductIdentity, options: SearchOptions
    ) -> uuid.UUID:
        search_id = await asyncio.to_thread(self.repo.create, owner, identity, options)
        self.runner.submit(f"search-{search_id}", self._run_search(search_id, identity, options))
        return search_id

    async def _run_search(
        self, search_id: uuid.UUID, identity: ProductIdentity, options: SearchOptions
    ) -> None:
        ctx = self._ctx(repo=self.repo, search_id=search_id)
        try:
            await asyncio.wait_for(
                self._graph.ainvoke(
                    {"run_mode": "full", "options": options, "identity": identity},
                    config={"configurable": {"ctx": ctx}},
                ),
                self.settings.search_timeout_seconds,
            )
        except asyncio.CancelledError:
            await self._finish(ctx, WorkflowState.FAILED, "Search cancelled by server shutdown.")
            raise
        except TimeoutError:
            has = bool(ctx.latest_views)
            await self._finish(
                ctx,
                WorkflowState.PARTIAL_RESULTS if has else WorkflowState.FAILED,
                f"Search timed out after {self.settings.search_timeout_seconds:g}s."
                + (" Showing results found so far." if has else ""),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("search workflow crashed: %s", type(exc).__name__)
            await self._finish(ctx, WorkflowState.FAILED, "The search failed unexpectedly.")

    @staticmethod
    async def _finish(ctx: WorkflowContext, state: WorkflowState, message: str) -> None:
        p: Progress = ctx.progress
        p.state, p.message, p.finished, p.current_node = state, message, True, None
        if state == WorkflowState.FAILED:
            p.error = message
        try:
            await asyncio.shield(ctx.push())
        except Exception:  # noqa: BLE001
            log.exception("could not persist final progress")
