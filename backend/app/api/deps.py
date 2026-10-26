import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request, Response

from app.config import Settings
from app.connectors.registry import ConnectorSet
from app.db import Database
from app.errors import RateLimitedError
from app.pricing.fx import FxProvider
from app.providers.registry import ProviderRegistry
from app.repositories.searches import SearchRepository
from app.workflow.service import TaskRunner, WorkflowService

COOKIE = "ps_session"
_SESSION_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class Services:
    settings: Settings
    db: Database
    providers: ProviderRegistry
    connectors: ConnectorSet
    fx: FxProvider
    repo: SearchRepository
    runner: TaskRunner
    workflow: WorkflowService
    limiter: "RateLimiter"


class RateLimiter:
    """In-memory sliding window. Single-process only; use a shared store when scaling out."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, key: str, bucket: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self._hits[(key, bucket)]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise RateLimitedError(
                "Too many requests. Please slow down.", details={"retry_after_seconds": int(window)}
            )
        q.append(now)


def services(request: Request) -> Services:
    return request.app.state.services


def owner_id(request: Request, response: Response) -> str:
    """Anonymous browser session: server-issued random id in an httpOnly cookie (no accounts in the MVP)."""
    cur = request.cookies.get(COOKIE, "")
    if _SESSION_RE.match(cur):
        return cur
    new = secrets.token_hex(16)
    s: Settings = request.app.state.services.settings
    response.set_cookie(
        COOKIE,
        new,
        httponly=True,
        samesite="lax",
        secure=s.cookie_secure,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return new
