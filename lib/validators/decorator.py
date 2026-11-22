from __future__ import annotations

from dataclasses import fields, is_dataclass
from functools import wraps
from typing import Any, get_type_hints

from .protocol import StrictValidatorProtocol
from .standard import StandardValidator


def validate[T](
    cls: type[T],
    *,
    validator: StrictValidatorProtocol | None = None,
) -> type[T]:
    """Dataclass decorator that validates init fields after __init__."""
    if not is_dataclass(cls):
        raise TypeError({"cls": cls, "reason": "must be a dataclass"})

    active_validator = validator or StandardValidator()
    type_hints = get_type_hints(cls, include_extras=True)
    field_specs = tuple(
        (definition.name, type_hints.get(definition.name, definition.type))
        for definition in fields(cls)
        if definition.init
    )

    orig_init = cls.__init__

    @wraps(orig_init)
    def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
        orig_init(self, *args, **kwargs)
        for field_name, field_dtype in field_specs:
            field_value = getattr(self, field_name)
            active_validator(value=field_value, dtype=field_dtype)

    cls.__init__ = __init__  # type: ignore[method-assign]
    return cls


__all__ = ["validate"]
