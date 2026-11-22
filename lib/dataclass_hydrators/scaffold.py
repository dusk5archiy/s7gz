from __future__ import annotations

from dataclasses import Field, dataclass, fields
from typing import TYPE_CHECKING, Any, get_type_hints

from lib.type_emitters.protocol import TransformProtocol

from .protocol import DataclassHydratorProtocol

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass(kw_only=True, frozen=True)
class ScaffoldDataclassHydrator(DataclassHydratorProtocol):
    class_key_projection: TransformProtocol[str] | None = None
    data_key_projection: TransformProtocol[str] | None = None

    def __call__[T: DataclassInstance](
        self, *, datacls, data, coercer, extra_keys_allowed
    ):
        projected_key_to_definition: dict[str, Field[Any]] = {}

        for definition in fields(datacls):
            if not definition.init:
                continue

            _class_key = definition.name
            _projected_key = _class_key

            if self.class_key_projection is not None:
                _projected_key = self.class_key_projection(_class_key)

            projected_key_to_definition[_projected_key] = definition

        type_hints = get_type_hints(datacls, include_extras=True)

        # ----------------------------------------------------------------------
        _projected_key_to_data_value: dict[str, Any] = {}

        for data_key, data_value in data.items():
            _projected_key = data_key
            if self.data_key_projection is not None:
                _projected_key = self.data_key_projection(data_key)

            _projected_key_to_data_value[_projected_key] = data_value

        if not extra_keys_allowed:
            unknown = sorted(
                set(_projected_key_to_data_value) - set(projected_key_to_definition)
            )

            if unknown:
                raise ValueError({"expected_type": str(datacls), "unknown": unknown})

        kwargs: dict[str, Any] = {}

        for projected_key, data_value in _projected_key_to_data_value.items():
            _definition = projected_key_to_definition.get(projected_key)
            if _definition is None:
                continue

            _dtype = type_hints.get(_definition.name, _definition.type)
            _result = coercer(value=data_value, dtype=_dtype)
            if _result is None:
                raise TypeError({"value": data_value, "expected_type": str(_dtype)})

            kwargs[_definition.name] = _result.value

        return datacls(**kwargs)
