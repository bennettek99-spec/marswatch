"""Structured logging: JSON lines to a file + human-readable console + DB sink.

Every log record may carry structured context (``job_id``, ``pair_id``...)
passed through ``extra={"ctx": {...}}`` or the :func:`get_logger` adapter.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        ctx = getattr(record, "ctx", None)
        if ctx:
            payload.update(ctx)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class DbHandler(logging.Handler):
    """Mirror INFO+ records into the SQLite ``logs`` table for the dashboard console."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from .db import get_db

            ctx = getattr(record, "ctx", None) or {}
            get_db().add_log(
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
                job_id=ctx.get("job_id"),
                context=ctx,
            )
        except Exception:  # never let logging crash the pipeline
            pass


def configure(log_dir: Path | None = None, level: int = logging.INFO, db: bool = True) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    from .config import settings

    log_dir = log_dir or settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("marswatch")
    root.setLevel(level)
    fh = logging.FileHandler(log_dir / "marswatch.jsonl")
    fh.setFormatter(JsonFormatter())
    root.addHandler(fh)
    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(ch)
    if db:
        dh = DbHandler()
        dh.setLevel(logging.INFO)
        root.addHandler(dh)
    _CONFIGURED = True


class CtxAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = kwargs.setdefault("extra", {})
        ctx = dict(self.extra or {})
        ctx.update(extra.get("ctx", {}))
        extra["ctx"] = ctx
        return msg, kwargs


def get_logger(name: str, **ctx: Any) -> CtxAdapter:
    return CtxAdapter(logging.getLogger(f"marswatch.{name}"), ctx)
