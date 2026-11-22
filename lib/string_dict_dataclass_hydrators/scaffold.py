from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.coercers.models import CoerceResult
from lib.dataclass_hydrators.protocol import DataclassHydratorProtocol
from lib.parsers.protocol import StrictParserProtocol

from .protocol import StringDictDataclassHydratorProtocol


@dataclass(frozen=True, kw_only=True)
class ScaffoldStringDictDataclassHydrator(StringDictDataclassHydratorProtocol):
    dataclass_hydrator: DataclassHydratorProtocol
    parser: StrictParserProtocol
    extra_keys_allowed: bool

    def _coerce(self, *, value: str, dtype: Any) -> CoerceResult:
        _result = self.parser(string=value, dtype=dtype)
        return CoerceResult(value=_result.value)

    def __call__(self, *, datacls, data):
        return self.dataclass_hydrator(
            datacls=datacls,
            data=data,
            coercer=self._coerce,
            extra_keys_allowed=self.extra_keys_allowed,
        )
