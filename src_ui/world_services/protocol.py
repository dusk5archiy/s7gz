from __future__ import annotations

from typing import Any, Literal, Protocol

WorldScope = Literal["source", "patched"]


class WorldServiceProtocol(Protocol):
    def list_worlds(self) -> dict[str, Any]: ...

    def read_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]: ...

    def delete_world(
        self, *, scope: WorldScope, relative_path: str
    ) -> dict[str, Any]: ...

    def download_world(
        self,
        *,
        world_name: str | None = None,
        world_url: str | None = None,
        select: bool = True,
    ) -> dict[str, Any]: ...

    def prepare_world(self) -> dict[str, Any]: ...

    def patch_world(self, *, relative_path: str) -> dict[str, Any]: ...

    def sync_provider(self, *, provider: str) -> dict[str, Any]: ...


__all__ = ["WorldScope", "WorldServiceProtocol"]
