from __future__ import annotations

from dataclasses import dataclass, is_dataclass
from typing import Any

from lib.coercers.models import CoerceResult
from lib.coercers.protocol import StrictCoercerProtocol
from lib.dataclass_hydrators.protocol import DataclassHydratorProtocol

from ..protocol import JsonCoercerProtocol


@dataclass(kw_only=True, frozen=True)
class DataclassCoercer(JsonCoercerProtocol):
    inner_coercer: StrictCoercerProtocol
    dataclass_hydrator: DataclassHydratorProtocol

    def can_handle(self, *, dtype: Any) -> bool:
        return isinstance(dtype, type) and is_dataclass(dtype)

    def __call__(self, *, value, dtype):
        if not isinstance(dtype, type) or not is_dataclass(dtype):
            return None

        if not isinstance(value, dict):
            raise TypeError(
                {
                    "value": value,
                    "expected_type": str(dict),
                    "got_type": str(type(value)),
                }
            )

        return CoerceResult(
            value=self.dataclass_hydrator(
                datacls=dtype,
                data=value,
                coercer=self.inner_coercer,
                extra_keys_allowed=False,
            )
        )


__all__ = ["DataclassCoercer"]
