import signal
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(kw_only=True, frozen=True)
class Settings:
    terminate_timeout_s: float = 5.0
    supported_signums: Sequence[signal._SIGNUM] = (signal.SIGINT, signal.SIGTERM)

    @classmethod
    def build(cls):
        return Settings()
