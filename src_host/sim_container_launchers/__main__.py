from __future__ import annotations

from .production import ProductionSimContainerLauncher


def main() -> int:
    return ProductionSimContainerLauncher()()


if __name__ == "__main__":
    raise SystemExit(main())
