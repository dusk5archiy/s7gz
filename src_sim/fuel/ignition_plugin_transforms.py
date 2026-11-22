from __future__ import annotations

import re
from dataclasses import dataclass

from s7dcls import TransformProtocol


@dataclass(kw_only=True, frozen=True)
class PluginRename:
    ignition_stem: str
    gz_stem: str
    ignition_class: str
    gz_class: str


DEFAULT_IGNITION_PLUGIN_RENAMES: tuple[PluginRename, ...] = (
    PluginRename(
        ignition_stem="ignition-gazebo-performer-detector-system",
        gz_stem="gz-sim-performer-detector-system",
        ignition_class="ignition::gazebo::systems::PerformerDetector",
        gz_class="gz::sim::systems::PerformerDetector",
    ),
    PluginRename(
        ignition_stem="ignition-gazebo-wind-effects-system",
        gz_stem="gz-sim-wind-effects-system",
        ignition_class="ignition::gazebo::systems::WindEffects",
        gz_class="gz::sim::systems::WindEffects",
    ),
    PluginRename(
        ignition_stem="ignition-gazebo-thermal-system",
        gz_stem="gz-sim-thermal-system",
        ignition_class="ignition::gazebo::systems::Thermal",
        gz_class="gz::sim::systems::Thermal",
    ),
)


@dataclass(kw_only=True, frozen=True)
class IgnitionPluginTransform(TransformProtocol[str]):
    renames: tuple[PluginRename, ...] = DEFAULT_IGNITION_PLUGIN_RENAMES

    def __call__(self, x: str) -> str:
        text = x
        for rename in self.renames:
            text = re.sub(
                rf'filename=(?P<q>["\'])(?P<prefix>lib)?{re.escape(rename.ignition_stem)}(?P<suffix>\.so)?(?P=q)',
                rf"filename=\g<q>\g<prefix>{rename.gz_stem}\g<suffix>\g<q>",
                text,
            )
            text = re.sub(
                rf'name=(?P<q>["\']){re.escape(rename.ignition_class)}(?P=q)',
                rf"name=\g<q>{rename.gz_class}\g<q>",
                text,
            )
        return text
