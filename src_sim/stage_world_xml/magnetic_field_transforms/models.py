from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class MagneticField:
    """World magnetic field vector in Tesla (ENU frame)."""

    x_east: float = 6e-06
    """Eastward magnetic field component in Tesla."""
    y_north: float = 2.3e-05
    """Northward magnetic field component in Tesla."""
    z_up: float = -4.2e-05
    """Upward magnetic field component in Tesla."""
