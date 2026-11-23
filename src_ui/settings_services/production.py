from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from s7dcls import (
    StandardCoercer,
    StandardTypeDescriber,
    StandardUncoercer,
    StandardValidator,
    StrictCoercerProtocol,
    StrictTypeDescriberProtocol,
    StrictUncoercerProtocol,
    StrictValidatorProtocol,
)

from ..override_stores.production import ProductionOverrideStore
from ..override_stores.protocol import OverrideStoreProtocol
from ..settings_discoverers.protocol import SettingsDiscovererProtocol
from ..settings_discoverers.standard import StandardSettingsDiscoverer
from .protocol import SettingsServiceProtocol
from .scaffold import ScaffoldSettingsService


@dataclass(kw_only=True, frozen=True)
class ProductionSettingsService(SettingsServiceProtocol):
    discoverer: SettingsDiscovererProtocol = field(
        default_factory=StandardSettingsDiscoverer
    )
    override_store: OverrideStoreProtocol = field(
        default_factory=ProductionOverrideStore
    )
    coercer: StrictCoercerProtocol = field(
        default_factory=lambda: StandardCoercer.Args(mode="json").build()
    )
    uncoercer: StrictUncoercerProtocol = field(
        default_factory=lambda: StandardUncoercer.Args().build()
    )
    type_describer: StrictTypeDescriberProtocol = field(
        default_factory=lambda: StandardTypeDescriber.Args(
            include_docstrings=True
        ).build()
    )
    validator: StrictValidatorProtocol = field(default_factory=StandardValidator)
    base_env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def _delegate(self) -> ScaffoldSettingsService:
        return ScaffoldSettingsService(
            discoverer=self.discoverer,
            override_store=self.override_store,
            coercer=self.coercer,
            uncoercer=self.uncoercer,
            type_describer=self.type_describer,
            validator=self.validator,
            base_env=self.base_env,
        )

    def apply_overrides(self) -> None:
        self._delegate().apply_overrides()

    def list_groups(
        self, *, env_overrides: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        return self._delegate().list_groups(env_overrides=env_overrides)

    def update(self, *, updates: dict[str, Any]) -> dict[str, Any]:
        return self._delegate().update(updates=updates)

    def clear_overrides(
        self, *, keys: list[str] | None = None
    ) -> dict[str, Any]:
        return self._delegate().clear_overrides(keys=keys)
