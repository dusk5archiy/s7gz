from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lib.string_dict_dataclass_hydrators.protocol import (
    StringDictDataclassHydratorProtocol,
)
from lib.type_emitters.protocol import DataclassEmitterProtocol, EmitterProtocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass(kw_only=True, frozen=True)
class ScaffoldSourceDataclassFetcher[T: DataclassInstance](DataclassEmitterProtocol[T]):
    datacls: type[T]
    dict_emitter: EmitterProtocol[dict[str, str]]
    string_dict_dataclass_hydrator: StringDictDataclassHydratorProtocol

    def __call__(self):
        data = self.dict_emitter()
        return self.string_dict_dataclass_hydrator(datacls=self.datacls, data=data)
