from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class EmitterProtocol[T](Protocol):
    def __call__(self) -> T: ...


class DataclassEmitterProtocol[T: DataclassInstance](Protocol):
    def __call__(self) -> T: ...


class FunctionProtocol[X, Y](Protocol):
    def __call__(self, x: X) -> Y: ...


class TransformProtocol[T](Protocol):
    def __call__(self, x: T) -> T: ...


class SwallowerProtocol[T](Protocol):
    def __call__(self, x: T) -> None: ...
