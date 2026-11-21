from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lib.datacls_assigners.standard import StandardDataclsAssigner
from lib.dict_fetchers.protocol import DictFetcherProtocol
from lib.parsers.standard import StandardParser

from .protocol import DataclassFetcherProtocol
from .scaffold import ScaffoldSourceDataclassFetcher

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class StandardDataclassFetcher[T: DataclassInstance](DataclassFetcherProtocol[T]):
    @dataclass(kw_only=True, frozen=True)
    class Args[D: DataclassInstance]:
        dtype: type[D]
        dict_fetchers: Sequence[DictFetcherProtocol]

        def build(self):
            return StandardDataclassFetcher(self)

    def __init__(self, args: Args[T]):
        datacls_assigner = StandardDataclsAssigner()
        self.parent = ScaffoldSourceDataclassFetcher(
            datacls=args.dtype,
            dict_fetchers=args.dict_fetchers,
            parser=StandardParser.Args(datacls_assigner=datacls_assigner).build(),
            datacls_assigner=datacls_assigner,
        )

    def __call__(self):
        return self.parent()
