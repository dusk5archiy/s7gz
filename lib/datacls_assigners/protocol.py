from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from lib.coercers.protocol import CoercerProtocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class DataclsAssignerProtocol(Protocol):
    def __call__[T: DataclassInstance](
        self,
        *,
        datacls: type[T],
        data: dict[str, Any],
        coercer: CoercerProtocol,
        extra_keys_allowed: bool,
    ) -> T: ...
