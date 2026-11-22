from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class StringDictDataclassHydratorProtocol(Protocol):
    def __call__[T: DataclassInstance](
        self,
        *,
        datacls: type[T],
        data: dict[str, str],
    ) -> T: ...
