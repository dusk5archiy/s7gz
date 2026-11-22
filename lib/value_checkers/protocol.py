from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ValueCheckerProtocol(Protocol):
    def __call__(self, value: Any) -> None: ...
