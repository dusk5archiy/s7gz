from dataclasses import dataclass, field

from .protocol import GuiConfigFileEmitterProtocol
from .settings import Settings


@dataclass(frozen=True, kw_only=True)
class ProductionGuiConfigFileEmitter(GuiConfigFileEmitterProtocol):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self):
        return self.settings.gui_config_file
