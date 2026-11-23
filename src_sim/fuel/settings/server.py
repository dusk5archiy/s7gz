from __future__ import annotations

from dataclasses import dataclass

from s7dcls import StandardDataclassFetcher, StandardShellDictFetcher

from src_common.conventions.env_prefix import SIM_ENV_PREFIX

PREFIX = SIM_ENV_PREFIX + "FUEL__"

SERVERS = (
    "fuel.gazebosim.org",
    "fuel.ignitionrobotics.org",
)


@dataclass(kw_only=True, frozen=True)
class FuelServerPolicy:
    canonical_server: str
    fallback_servers: tuple[str, ...] = ()

    @property
    def download_servers(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                h for h in (self.canonical_server, *self.fallback_servers) if h
            )
        )

    @property
    def known_servers(self) -> tuple[str, ...]:
        return self.download_servers

    @classmethod
    def from_hosts(
        cls, *, canonical_server: str, fallback_server: str | None
    ) -> FuelServerPolicy:
        return cls(
            canonical_server=canonical_server,
            fallback_servers=(fallback_server,) if fallback_server else (),
        )


@dataclass(kw_only=True, frozen=True)
class ServerSettings:
    """Gazebo Fuel server host selection and fallback policy."""

    canonical_server: str = SERVERS[0]
    """Primary Fuel server hostname."""
    fallback_server: str | None = SERVERS[1]
    """Optional secondary Fuel server hostname if the primary fails."""

    @property
    def server_policy(self) -> FuelServerPolicy:
        return FuelServerPolicy.from_hosts(
            canonical_server=self.canonical_server,
            fallback_server=self.fallback_server,
        )

    @classmethod
    def build(cls) -> ServerSettings:
        return StandardDataclassFetcher.Args(
            datacls=ServerSettings,
            dict_emitter=StandardShellDictFetcher(prefix=PREFIX),
        ).build()()


Settings = ServerSettings
