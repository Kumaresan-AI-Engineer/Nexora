import json
import logging
import re
from datetime import UTC, datetime

_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|tvly-[A-Za-z0-9_\-]{6,}|AIza[0-9A-Za-z_\-]{20,}|Bearer\s+\S+)"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": _SECRET.sub("[redacted]", record.getMessage()),
        }
        extra = getattr(record, "ctx", None)
        if extra:
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = _SECRET.sub("[redacted]", self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
