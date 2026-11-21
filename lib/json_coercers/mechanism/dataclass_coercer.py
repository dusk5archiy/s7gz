from __future__ import annotations

from dataclasses import dataclass, is_dataclass

from lib.coercers.models import CoerceResult
from lib.datacls_assigners.protocol import DataclsAssignerProtocol

from ..protocol import JsonContainerCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class DataclassCoercer(JsonContainerCoercerProtocol):
    datacls_assigner: DataclsAssignerProtocol

    def __call__(self, *, value, dtype, coercer):
        if not isinstance(dtype, type) or not is_dataclass(dtype):
            return None

        if coercer is None:
            return CoerceResult(value=None)

        if not isinstance(value, dict):
            raise TypeError(
                f"Expected JSON object for {dtype.__name__}, got {type(value).__name__}"
            )

        return CoerceResult(
            value=self.datacls_assigner(
                dtype=dtype, data=value, coercer=coercer, extra_keys_allowed=False
            )
        )


__all__ = ["DataclassCoercer"]
