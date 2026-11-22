from dataclasses import dataclass
from pathlib import Path

from lib.type_emitters.protocol import EmitterProtocol, TransformProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldSdfEmitter(EmitterProtocol[Path]):
    source_world_emitter: EmitterProtocol[Path]
    world_text_transformd: TransformProtocol[str] | None = None
    patched_worlds_dir: Path

    def __call__(self):
        source_file = self.source_world_emitter()
        text = source_file.read_text(encoding="utf-8")

        transformed_text = text
        if self.world_text_transformd is not None:
            transformed_text = self.world_text_transformd(text)

        self.patched_worlds_dir.mkdir(parents=True, exist_ok=True)
        output_file = self.patched_worlds_dir / source_file.name
        output_file.write_text(transformed_text, encoding="utf-8")
        return output_file
