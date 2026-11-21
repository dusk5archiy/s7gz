from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(kw_only=True, frozen=True)
class SubprocessCommand:
    cmd: Sequence[str]
    env: Mapping[str, str] | None = None

    def __post_init__(self):
        if not self.cmd or not self.cmd[0]:
            raise ValueError({"cmd": self.cmd})
