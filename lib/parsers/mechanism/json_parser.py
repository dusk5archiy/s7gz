from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lib.coercers.models import CoerceResult
from lib.datacls_assigners.protocol import DataclsAssignerProtocol
from lib.json_coercers.mechanism import (
    DataclassCoercer,
    DictCoercer,
    ListCoercer,
    TupleCoercer,
)
from lib.json_coercers.protocol import (
    JsonContainerCoercerProtocol,
)

from ..models import ParseResult
from ..protocol import ParserProtocol


def _to_parser_string(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class JsonParser(ParserProtocol):
    @dataclass(kw_only=True, frozen=True)
    class Args:
        inner_converter: ParserProtocol
        datacls_assigner: DataclsAssignerProtocol

        def build(self):
            return JsonParser(self)

    def __init__(self, args: Args):
        self.args = args
        self.coercers: tuple[JsonContainerCoercerProtocol, ...] = (
            DictCoercer(),
            ListCoercer(),
            TupleCoercer(),
            DataclassCoercer(datacls_assigner=args.datacls_assigner),
        )

    def _coerce(self, *, value: Any, dtype: Any) -> CoerceResult | None:
        if dtype is Any:
            return CoerceResult(value=value)

        args = self.args
        for coercer in self.coercers:
            _result = coercer(
                value=value,
                dtype=dtype,
                coercer=self._coerce,
            )

            if _result is None:
                continue

            return _result

        as_string = _to_parser_string(value)
        _parse_result = args.inner_converter(string=as_string, dtype=dtype)
        if _parse_result is not None:
            return CoerceResult(value=_parse_result.value)

        raise ValueError(f"Cannot coerce JSON value {value!r} to type '{dtype}'")

    def __call__(self, *, string: str, dtype: Any) -> ParseResult | None:
        _rejects = []
        for coercer in self.coercers:
            _dtype_checking_result = coercer(value=None, dtype=dtype, coercer=None)
            _is_rejected = _dtype_checking_result is None
            _rejects.append(_is_rejected)

        if all(_rejects):
            return None

        try:
            parsed = json.loads(string)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Unsupported JSON value '{string}' for type '{dtype}': {e}"
            ) from e

        _result = self._coerce(value=parsed, dtype=dtype)
        if _result is None:
            raise TypeError

        return ParseResult(value=_result.value)
