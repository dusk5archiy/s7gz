from dataclasses import dataclass
from pathlib import Path

from s7dcls import EmitterProtocol, TransformProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldWorldSdfEmitter(EmitterProtocol[Path]):
    source_world_emitter: EmitterProtocol[Path]
    world_text_transformd: TransformProtocol[str] | None = None
    patched_worlds_dir: Path
    source_worlds_dir: Path | None = None

    def _relative_output(self, source_file: Path) -> Path:
        if self.source_worlds_dir is not None:
            src_root = self.source_worlds_dir.resolve()
            src_resolved = source_file.resolve()
            if src_resolved.is_relative_to(src_root):
                return src_resolved.relative_to(src_root)
        return Path(source_file.name)

    def __call__(self):
        source_file = self.source_world_emitter()
        text = source_file.read_text(encoding="utf-8")

        transformed_text = text
        if self.world_text_transformd is not None:
            transformed_text = self.world_text_transformd(text)

        output_file = self.patched_worlds_dir / self._relative_output(source_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(transformed_text, encoding="utf-8")
        return output_file
