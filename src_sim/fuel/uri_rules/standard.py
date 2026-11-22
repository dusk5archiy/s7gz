from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import unquote

from ..models import FuelAssetRef, FuelUriMatch
from .protocol import FuelUriRuleProtocol
from .scaffold import SequenceFuelUriRule


@dataclass(kw_only=True, frozen=True)
class HttpFuelUriRule(FuelUriRuleProtocol):
    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"https?://(?P<server>[^/<>\s\"']+)/[\d.]+/"
        r"(?P<owner>[^/<>\s\"']+)/(?P<kind>models|worlds)/"
        r"(?P<rest>[^<>\"'\r\n]+)",
        re.IGNORECASE,
    )

    def _parse(self, match: re.Match[str]) -> FuelUriMatch:
        raw_rest = match.group("rest")
        trailing_ws = raw_rest[len(raw_rest.rstrip()) :]
        parts = raw_rest.rstrip().split("/", 3)
        subpath: str | None = None
        if (
            len(parts) >= 3
            and (parts[1] == "tip" or parts[1].isdigit())
            and parts[2] == "files"
        ):
            subpath = unquote(parts[3]) if len(parts) == 4 else ""
        return FuelUriMatch(
            asset=FuelAssetRef(
                server=match.group("server").lower(),
                owner=unquote(match.group("owner")),
                asset_kind="models"
                if match.group("kind").lower() == "models"
                else "worlds",
                name=unquote(parts[0]),
            ),
            subpath=subpath,
            trailing_ws=trailing_ws,
        )

    def find_all(self, *, text: str) -> list[FuelUriMatch]:
        return [self._parse(match) for match in self._PATTERN.finditer(text)]

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str:
        return self._PATTERN.sub(
            lambda m: r if (r := rewrite(self._parse(m))) is not None else m.group(0),
            text,
        )


@dataclass(kw_only=True, frozen=True)
class CachedFileFuelUriRule(FuelUriRuleProtocol):
    known_servers: tuple[str, ...]

    def _compile(self) -> re.Pattern[str] | None:
        servers = sorted({s for s in self.known_servers if s}, key=len, reverse=True)
        if not servers:
            return None
        servers_alt = "|".join(re.escape(s) for s in servers)
        return re.compile(
            rf"file://[^<>\"'\r\n]*?/(?P<server>{servers_alt})/"
            r"(?P<owner>[^/<>\s\"']+)/(?P<kind>models|worlds)/"
            r"(?P<rest>[^<>\"'\r\n]+)",
            re.IGNORECASE,
        )

    def _parse(self, match: re.Match[str]) -> FuelUriMatch:
        raw_rest = match.group("rest")
        trailing_ws = raw_rest[len(raw_rest.rstrip()) :]
        parts = raw_rest.rstrip().split("/", 2)
        subpath = (
            unquote(parts[2])
            if len(parts) == 3 and parts[1].isdigit() and parts[2]
            else None
        )
        return FuelUriMatch(
            asset=FuelAssetRef(
                server=match.group("server").lower(),
                owner=unquote(match.group("owner")),
                asset_kind="models"
                if match.group("kind").lower() == "models"
                else "worlds",
                name=unquote(parts[0]),
            ),
            subpath=subpath,
            trailing_ws=trailing_ws,
        )

    def find_all(self, *, text: str) -> list[FuelUriMatch]:
        pattern = self._compile()
        return (
            [] if pattern is None else [self._parse(m) for m in pattern.finditer(text)]
        )

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str:
        pattern = self._compile()
        if pattern is None:
            return text
        return pattern.sub(
            lambda m: r if (r := rewrite(self._parse(m))) is not None else m.group(0),
            text,
        )


@dataclass(kw_only=True, frozen=True)
class StandardFuelUriRule(FuelUriRuleProtocol):
    known_servers: tuple[str, ...]

    def _delegate(self) -> SequenceFuelUriRule:
        return SequenceFuelUriRule(
            rules=(
                HttpFuelUriRule(),
                CachedFileFuelUriRule(known_servers=self.known_servers),
            )
        )

    def find_all(self, *, text: str) -> list[FuelUriMatch]:
        return self._delegate().find_all(text=text)

    def replace_all(
        self, *, text: str, rewrite: Callable[[FuelUriMatch], str | None]
    ) -> str:
        return self._delegate().replace_all(text=text, rewrite=rewrite)
