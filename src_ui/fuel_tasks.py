from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from src_sim.fuel.progress import fuel_progress_sink


class FuelTaskBusyError(RuntimeError):
    """Raised when a mutating Fuel operation is requested while another is active."""


@dataclass
class FuelTaskState:
    task_id: str
    label: str
    status: str = "running"  # "running" | "done" | "error"
    logs: list[str] = field(default_factory=list)
    done: int | None = None
    total: int | None = None
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


_TASKS_LOCK = threading.Lock()
_TASKS: dict[str, FuelTaskState] = {}
_TERMINAL_LOGS: list[str] = []
_ACTIVE_OPERATION_LABEL: str | None = None
_ACTIVE_TASK_ID: str | None = None
_MAX_RETAINED_TASKS = 40
_MAX_LOG_LINES = 400


def _append_terminal_log_locked(line: str) -> None:
    _TERMINAL_LOGS.append(line)
    if len(_TERMINAL_LOGS) > _MAX_LOG_LINES:
        del _TERMINAL_LOGS[: len(_TERMINAL_LOGS) - _MAX_LOG_LINES]


def _prune_old_tasks_locked() -> None:
    if len(_TASKS) <= _MAX_RETAINED_TASKS:
        return
    finished = [
        (tid, st.finished_at or st.created_at)
        for tid, st in _TASKS.items()
        if st.status != "running"
    ]
    finished.sort(key=lambda item: item[1])
    for tid, _ in finished[: max(0, len(_TASKS) - _MAX_RETAINED_TASKS)]:
        _TASKS.pop(tid, None)


@contextmanager
def acquire_fuel_operation(label: str) -> Iterator[None]:
    """Ensure only one Fuel download/patch/delete runs at a time across models & worlds."""
    global _ACTIVE_OPERATION_LABEL
    with _TASKS_LOCK:
        if _ACTIVE_OPERATION_LABEL is not None:
            raise FuelTaskBusyError(
                f"Another Fuel operation is already in progress: {_ACTIVE_OPERATION_LABEL}"
            )
        _ACTIVE_OPERATION_LABEL = label
        _append_terminal_log_locked(f"Started: {label}")
    try:
        yield
    except Exception as exc:
        with _TASKS_LOCK:
            _append_terminal_log_locked(f"Error: {exc}")
        raise
    else:
        with _TASKS_LOCK:
            _append_terminal_log_locked(f"Completed: {label}")
    finally:
        with _TASKS_LOCK:
            if _ACTIVE_OPERATION_LABEL == label:
                _ACTIVE_OPERATION_LABEL = None


def start_fuel_task(label: str, fn: Callable[[], Any]) -> str:
    global _ACTIVE_OPERATION_LABEL, _ACTIVE_TASK_ID
    task_id = uuid4().hex[:12]
    start_line = f"Started: {label}"
    state = FuelTaskState(task_id=task_id, label=label, logs=[start_line])
    with _TASKS_LOCK:
        if _ACTIVE_OPERATION_LABEL is not None:
            raise FuelTaskBusyError(
                f"Another Fuel operation is already in progress: {_ACTIVE_OPERATION_LABEL}"
            )
        _ACTIVE_OPERATION_LABEL = label
        _ACTIVE_TASK_ID = task_id
        _TASKS[task_id] = state
        _append_terminal_log_locked(start_line)
        _prune_old_tasks_locked()

    def _sink(message: str, meta: dict[str, Any]) -> None:
        with _TASKS_LOCK:
            _append_terminal_log_locked(message)
            st = _TASKS.get(task_id)
            if st is None:
                return
            st.logs.append(message)
            if len(st.logs) > _MAX_LOG_LINES:
                st.logs = st.logs[-_MAX_LOG_LINES:]
            if "done" in meta and "total" in meta:
                st.done = int(meta["done"])
                st.total = int(meta["total"])

    def _worker() -> None:
        global _ACTIVE_OPERATION_LABEL, _ACTIVE_TASK_ID
        try:
            with fuel_progress_sink(_sink):
                res = fn()
            with _TASKS_LOCK:
                st = _TASKS[task_id]
                st.status = "done"
                st.result = res
                st.finished_at = time.time()
                done_line = f"Completed: {label}"
                st.logs.append(done_line)
                _append_terminal_log_locked(done_line)
        except Exception as exc:
            with _TASKS_LOCK:
                st = _TASKS[task_id]
                st.status = "error"
                st.error = str(exc)
                st.finished_at = time.time()
                err_line = f"Error: {exc}"
                st.logs.append(err_line)
                _append_terminal_log_locked(err_line)
        finally:
            with _TASKS_LOCK:
                if _ACTIVE_TASK_ID == task_id:
                    _ACTIVE_TASK_ID = None
                    _ACTIVE_OPERATION_LABEL = None

    thread = threading.Thread(target=_worker, name=f"fuel-task-{task_id}", daemon=True)
    thread.start()
    return task_id


def _task_to_dict(st: FuelTaskState) -> dict[str, Any]:
    return {
        "task_id": st.task_id,
        "label": st.label,
        "status": st.status,
        "logs": list(st.logs),
        "done": st.done,
        "total": st.total,
        "result": st.result,
        "error": st.error,
    }


def get_fuel_task(task_id: str) -> dict[str, Any] | None:
    with _TASKS_LOCK:
        st = _TASKS.get(task_id)
        return _task_to_dict(st) if st is not None else None


def get_fuel_terminal_state() -> dict[str, Any]:
    with _TASKS_LOCK:
        active_task = (
            _task_to_dict(_TASKS[_ACTIVE_TASK_ID])
            if _ACTIVE_TASK_ID and _ACTIVE_TASK_ID in _TASKS
            else None
        )
        return {
            "busy": _ACTIVE_OPERATION_LABEL is not None,
            "active_label": _ACTIVE_OPERATION_LABEL,
            "active_task": active_task,
            "logs": list(_TERMINAL_LOGS),
        }


__all__ = [
    "FuelTaskBusyError",
    "acquire_fuel_operation",
    "get_fuel_task",
    "get_fuel_terminal_state",
    "start_fuel_task",
]
