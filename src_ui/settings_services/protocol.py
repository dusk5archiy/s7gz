from __future__ import annotations

from typing import Any, Protocol


class SettingsServiceProtocol(Protocol):
    def apply_overrides(self) -> None: ...

    def list_groups(
        self, *, env_overrides: dict[str, str] | None = None
    ) -> list[dict[str, Any]]: ...

    def update(self, *, updates: dict[str, Any]) -> dict[str, Any]: ...

    def clear_overrides(
        self, *, keys: list[str] | None = None
    ) -> dict[str, Any]: ...
