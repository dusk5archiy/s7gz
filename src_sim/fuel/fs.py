from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


@contextmanager
def atomic_path(dest: Path) -> Iterator[Path]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_name(f".tmp.{dest.name}.{uuid4().hex[:8]}")
    try:
        yield tmp_path
        tmp_path.replace(dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
