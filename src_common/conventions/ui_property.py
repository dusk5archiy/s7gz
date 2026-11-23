from __future__ import annotations

from typing import Any

UI_PROPERTY_ATTR = "__ui_property__"


def ui_property(prop: property) -> property:
    """Mark a @property as exposed in the Settings UI as a read-only computed value."""
    if prop.fget is not None:
        setattr(prop.fget, UI_PROPERTY_ATTR, True)
    return prop


def is_ui_property(member: Any) -> bool:
    return (
        isinstance(member, property)
        and member.fget is not None
        and bool(getattr(member.fget, UI_PROPERTY_ATTR, False))
    )


__all__ = ["UI_PROPERTY_ATTR", "is_ui_property", "ui_property"]
