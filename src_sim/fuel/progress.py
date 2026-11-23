from __future__ import annotations

import contextvars
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

ProgressSink = Callable[[str, dict[str, Any]], None]

_PROGRESS_SINK: contextvars.ContextVar[ProgressSink | None] = contextvars.ContextVar(
    "fuel_progress_sink", default=None
)


def emit_fuel_progress(message: str, **meta: Any) -> None:
    sink = _PROGRESS_SINK.get()
    if sink is not None:
        sink(message, meta)


@contextmanager
def fuel_progress_sink(sink: ProgressSink) -> Iterator[None]:
    token = _PROGRESS_SINK.set(sink)
    try:
        yield
    finally:
        _PROGRESS_SINK.reset(token)


def run_with_current_context(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    ctx = contextvars.copy_context()
    return ctx.run(fn, *args, **kwargs)


__all__ = [
    "ProgressSink",
    "emit_fuel_progress",
    "fuel_progress_sink",
    "run_with_current_context",
]
