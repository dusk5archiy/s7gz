from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

from lib.string_manipulations.string_gates.mechanism import NoCasePrefixGate

from .protocol import DictFetcherProtocol
from .scaffold import ScaffoldDictFetcher


def is_dict_str_str(obj: Any) -> TypeGuard[dict[str, str]]:
    return isinstance(obj, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in obj.items()
    )


@dataclass(kw_only=True, frozen=True)
class RawShellDictFetcher(DictFetcherProtocol):
    def __call__(self):
        return dict(os.environ.items())


@dataclass(kw_only=True, frozen=True)
class RawJsonDictFetcher(DictFetcherProtocol):
    file: Path

    def __call__(self):
        if not self.file.is_file():
            _json_object = {}
        else:
            _json_object = json.loads(self.file.read_text())
        if not is_dict_str_str(_json_object):
            raise ValueError({"file": self.file, "expected_type": str(dict[str, str])})
        return _json_object


@dataclass(kw_only=True, frozen=True)
class StandardShellDictFetcher(DictFetcherProtocol):
    prefix: str = ""

    def __call__(self):
        return ScaffoldDictFetcher(
            dict_fetcher=RawShellDictFetcher(),
            key_gate=NoCasePrefixGate(prefix=self.prefix),
        )()


@dataclass(kw_only=True, frozen=True)
class StandardJsonDictFetcher(DictFetcherProtocol):
    prefix: str = ""
    file: Path

    def __call__(self):
        return ScaffoldDictFetcher(
            dict_fetcher=RawJsonDictFetcher(file=self.file),
            key_gate=NoCasePrefixGate(prefix=self.prefix),
        )()
