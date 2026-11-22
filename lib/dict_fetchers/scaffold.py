from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lib.type_emitters.protocol import FunctionProtocol

from .protocol import DictFetcherProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldDictFetcher(DictFetcherProtocol):
    dict_fetcher: DictFetcherProtocol
    key_gate: FunctionProtocol[str, str | None]

    def __call__(self):
        data = self.dict_fetcher()
        result: dict[str, str] = {}
        for data_key, data_value in data.items():
            _gated = self.key_gate(data_key)
            if _gated is not None:
                result[_gated] = data_value
        return result


@dataclass(kw_only=True, frozen=True)
class SequenceDictFetcher(DictFetcherProtocol):
    dict_fetchers: Sequence[DictFetcherProtocol]

    def __call__(self):
        data: dict[str, str] = {}
        for dict_fetcher in self.dict_fetchers:
            for k, v in dict_fetcher().items():
                data[k] = v
        return data


__all__ = ["ScaffoldDictFetcher"]
