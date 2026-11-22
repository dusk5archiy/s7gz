from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lib.dataclass_hydrators.protocol import DataclassHydratorProtocol
from lib.dataclass_hydrators.scaffold import ScaffoldDataclassHydrator
from lib.parsers.standard import StandardParser
from lib.string_dict_dataclass_hydrators.protocol import (
    StringDictDataclassHydratorProtocol,
)

from .scaffold import ScaffoldStringDictDataclassHydrator

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


class StandardStringDictDataclassHydrator(StringDictDataclassHydratorProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        dataclass_hydrator: DataclassHydratorProtocol | None = None
        extra_keys_allowed: bool = False

        def build(self):
            return StandardStringDictDataclassHydrator(self)

    def __init__(self, args: Args):
        self.args = args
        dataclass_hydrator = args.dataclass_hydrator or ScaffoldDataclassHydrator()
        self.parent = ScaffoldStringDictDataclassHydrator(
            parser=StandardParser.Args(dataclass_hydrator=dataclass_hydrator).build(),
            dataclass_hydrator=dataclass_hydrator,
            extra_keys_allowed=args.extra_keys_allowed,
        )

    def __call__[T: DataclassInstance](self, *, datacls: type[T], data):
        return self.parent(datacls=datacls, data=data)
