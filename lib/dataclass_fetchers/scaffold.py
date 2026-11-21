from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lib.coercers.models import CoerceResult
from lib.datacls_assigners.protocol import DataclsAssignerProtocol
from lib.dict_fetchers.protocol import DictFetcherProtocol
from lib.parsers.protocol import ParserProtocol

from .protocol import DataclassFetcherProtocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass(kw_only=True, frozen=True)
class ScaffoldSourceDataclassFetcher[T: DataclassInstance](DataclassFetcherProtocol[T]):
    datacls: type[T]
    dict_fetchers: Sequence[DictFetcherProtocol]
    parser: ParserProtocol
    datacls_assigner: DataclsAssignerProtocol

    def coerce_fn(self, *, value: str, dtype: Any) -> CoerceResult:
        _result = self.parser(string=value, dtype=dtype)

        if _result is None:
            raise TypeError({"dtype": dtype, "reason": "unsupported"})

        return CoerceResult(value=_result.value)

    def __call__(self):
        data: dict[str, str] = {}
        for dict_fetcher in self.dict_fetchers:
            for k, v in dict_fetcher().items():
                data[k] = v

        return self.datacls_assigner(
            datacls=self.datacls,
            data=data,
            coercer=self.coerce_fn,
            extra_keys_allowed=True,
        )
