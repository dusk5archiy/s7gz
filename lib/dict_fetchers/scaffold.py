from __future__ import annotations

from dataclasses import dataclass

from lib.string_manipulations.string_gates.protocol import StringGateProtocol

from .protocol import DictFetcherProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldDictFetcher(DictFetcherProtocol):
    dict_fetcher: DictFetcherProtocol
    key_gate: StringGateProtocol

    def __call__(self):
        data = self.dict_fetcher()
        result: dict[str, str] = {}
        for data_key, data_value in data.items():
            _gated = self.key_gate(string=data_key)
            if _gated is not None:
                result[_gated] = data_value
        return result


__all__ = ["ScaffoldDictFetcher"]
