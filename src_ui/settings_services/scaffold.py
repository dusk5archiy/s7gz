from __future__ import annotations

import inspect
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from types import UnionType
from typing import Annotated, Any, Union, get_args, get_origin

from s7dcls import (
    StrictCoercerProtocol,
    StrictTypeDescriberProtocol,
    StrictUncoercerProtocol,
    StrictValidatorProtocol,
    get_cached_type_hints,
)

from src_common.conventions.env_prefix import SIM_ENV_PREFIX
from src_common.conventions.ui_property import is_ui_property

from ..override_stores.protocol import OverrideStoreProtocol
from ..settings_discoverers.protocol import SettingsDiscovererProtocol
from .protocol import SettingsServiceProtocol


def _attach_dataclass_defaults(
    schema: dict[str, Any],
    dtype: Any,
    uncoercer: StrictUncoercerProtocol,
) -> dict[str, Any]:
    origin = get_origin(dtype)
    if origin is Annotated:
        return _attach_dataclass_defaults(schema, get_args(dtype)[0], uncoercer)
    if origin in (UnionType, Union):
        non_none = [a for a in get_args(dtype) if a is not type(None)]
        if len(non_none) == 1:
            return _attach_dataclass_defaults(schema, non_none[0], uncoercer)
        if schema.get("type") == "union" and isinstance(schema.get("variants"), list):
            return {
                **schema,
                "variants": [
                    _attach_dataclass_defaults(v_schema, v_dtype, uncoercer)
                    for v_schema, v_dtype in zip(
                        schema["variants"], non_none, strict=False
                    )
                ],
            }
        return schema
    if isinstance(dtype, type) and is_dataclass(dtype) and schema.get("type") == "dataclass":
        hints = get_cached_type_hints(dtype)
        field_defs = {f.name: f for f in fields(dtype) if f.init}
        next_fields: list[dict[str, Any]] = []
        for f_entry in schema.get("fields", []):
            name = f_entry["name"]
            f_def = field_defs.get(name)
            f_dtype = hints.get(name, f_def.type) if f_def else Any
            enriched = {
                **f_entry,
                "schema": _attach_dataclass_defaults(
                    f_entry["schema"], f_dtype, uncoercer
                ),
            }
            if f_def is not None:
                if f_def.default is not MISSING:
                    enriched["default"] = uncoercer(value=f_def.default)
                elif f_def.default_factory is not MISSING:
                    enriched["default"] = uncoercer(value=f_def.default_factory())
            next_fields.append(enriched)
        return {**schema, "fields": next_fields}
    return schema


def _apply_override_values(overrides: Mapping[str, Any]) -> None:
    for key, val in overrides.items():
        if val is None:
            os.environ.pop(key, None)
        elif isinstance(val, bool):
            os.environ[key] = "true" if val else "false"
        elif isinstance(val, (list, dict)):
            os.environ[key] = json.dumps(val)
        else:
            os.environ[key] = str(val)


def _restore_base_env(base_env: Mapping[str, str]) -> None:
    for key in list(os.environ.keys()):
        if key.startswith(SIM_ENV_PREFIX) and key not in base_env:
            os.environ.pop(key, None)
    for key, val in base_env.items():
        if key.startswith(SIM_ENV_PREFIX):
            os.environ[key] = val


@contextmanager
def _temporary_env(
    *,
    base_env: Mapping[str, str],
    overrides: Mapping[str, Any] | None = None,
    extra: Mapping[str, str] | None = None,
) -> Iterator[None]:
    prev_env = dict(os.environ)
    try:
        _restore_base_env(base_env)
        if overrides:
            _apply_override_values(overrides)
        if extra:
            for k, v in extra.items():
                os.environ[k] = v
        yield
    finally:
        os.environ.clear()
        os.environ.update(prev_env)


@dataclass(kw_only=True, frozen=True)
class ScaffoldSettingsService(SettingsServiceProtocol):
    discoverer: SettingsDiscovererProtocol
    override_store: OverrideStoreProtocol
    coercer: StrictCoercerProtocol
    uncoercer: StrictUncoercerProtocol
    type_describer: StrictTypeDescriberProtocol
    validator: StrictValidatorProtocol
    base_env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def apply_overrides(self) -> None:
        _restore_base_env(self.base_env)
        _apply_override_values(self.override_store.load())

    def list_groups(
        self, *, env_overrides: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        ui_overrides = self.override_store.load()
        self.apply_overrides()

        with _temporary_env(base_env=self.base_env, extra=env_overrides):
            base_instances = {
                group.name: group.datacls.build() for group in self.discoverer()
            }

        with _temporary_env(
            base_env=self.base_env,
            overrides=ui_overrides,
            extra=env_overrides,
        ):
            return self._collect_groups(
                base_instances=base_instances,
                ui_overrides=ui_overrides,
            )

    def _collect_groups(
        self,
        *,
        base_instances: Mapping[str, Any],
        ui_overrides: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for group in self.discoverer():
            instance = group.datacls.build()
            base_instance = base_instances[group.name]
            group_schema = _attach_dataclass_defaults(
                self.type_describer(dtype=group.datacls),
                group.datacls,
                self.uncoercer,
            )
            field_meta_by_name = {
                item["name"]: item for item in group_schema.get("fields", [])
            }
            field_items: list[dict[str, Any]] = []
            for f in fields(group.datacls):
                if not f.init:
                    continue
                env_key = group.prefix + f.name.lstrip("_").upper()
                has_default = (
                    f.default is not MISSING or f.default_factory is not MISSING
                )
                if f.default is not MISSING:
                    default_val = self.uncoercer(value=f.default)
                elif f.default_factory is not MISSING:
                    default_val = self.uncoercer(value=f.default_factory())
                else:
                    default_val = None
                base_val = self.uncoercer(value=getattr(base_instance, f.name))
                current_val = self.uncoercer(value=getattr(instance, f.name))
                field_meta = field_meta_by_name[f.name]
                item: dict[str, Any] = {
                    "name": f.name,
                    "env_key": env_key,
                    "has_default": has_default,
                    "is_ui_overridden": env_key in ui_overrides,
                    "schema": field_meta["schema"],
                    "default": default_val,
                    "base_value": base_val,
                    "value": current_val,
                }
                if "description" in field_meta:
                    item["description"] = field_meta["description"]
                field_items.append(item)

            property_items: list[dict[str, Any]] = []
            for prop_name, member in vars(group.datacls).items():
                if not is_ui_property(member):
                    continue
                prop_item: dict[str, Any] = {
                    "name": prop_name,
                    "value": self.uncoercer(value=getattr(instance, prop_name)),
                }
                if member.__doc__:
                    prop_item["description"] = inspect.cleandoc(member.__doc__)
                property_items.append(prop_item)

            group_item: dict[str, Any] = {
                "group": group.name,
                "prefix": group.prefix,
                "fields": field_items,
            }
            if property_items:
                group_item["properties"] = property_items
            if "description" in group_schema:
                group_item["description"] = group_schema["description"]
            result.append(group_item)
        return result

    def update(self, *, updates: dict[str, Any]) -> dict[str, Any]:
        env_to_dtype: dict[str, Any] = {}
        for group in self.discoverer():
            hints = get_cached_type_hints(group.datacls)
            for f in fields(group.datacls):
                if not f.init:
                    continue
                env_key = group.prefix + f.name.lstrip("_").upper()
                env_to_dtype[env_key] = hints.get(f.name, f.type)

        validated: dict[str, Any] = {}
        for env_key, raw_val in updates.items():
            if env_key not in env_to_dtype:
                raise KeyError(f"Unknown setting key: {env_key!r}")
            dtype = env_to_dtype[env_key]
            coerced = self.coercer(value=raw_val, dtype=dtype)
            self.validator(value=coerced, dtype=dtype)
            validated[env_key] = self.uncoercer(value=coerced)

        merged = {**self.override_store.load(), **validated}
        self.override_store.save(merged)
        self.apply_overrides()
        return merged

    def clear_overrides(
        self, *, keys: list[str] | None = None
    ) -> dict[str, Any]:
        current = self.override_store.load()
        if keys is None:
            remaining: dict[str, Any] = {}
        else:
            remove_set = set(keys)
            remaining = {k: v for k, v in current.items() if k not in remove_set}
        self.override_store.save(remaining)
        self.apply_overrides()
        return remaining


__all__ = ["ScaffoldSettingsService"]
