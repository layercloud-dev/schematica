"""Lighting pass: place light sources on walkable ground at a given spacing.

Deliberate, evenly-spaced lighting is what separates a designed map from a
survival base. The pass scans a lattice over the region and places the light
block one above the local ground on cells that are walkable (solid floor,
two air above) — never floating in mid-air or buried indoors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..blocks.block import AIR
from .paths import ground_height

if TYPE_CHECKING:
    from ..session.session import Session


def apply_lighting(session: Session, frm: tuple[int, int, int],
                   to: tuple[int, int, int], *, light: str = "minecraft:lantern",
                   spacing: int = 7, offset: int = 0) -> int:
    """Place ``light`` every ``spacing`` blocks on walkable ground cells.

    Lattice starts at [frm] + ``offset``. ``spacing`` must be >= 2 (denser
    than that is noise, not lighting). Returns lights placed.
    """
    if spacing < 2:
        raise ValueError("spacing must be >= 2")
    x0, x1 = sorted((frm[0], to[0]))
    z0, z1 = sorted((frm[2], to[2]))
    sx, sy, sz = session.grid.shape
    coords: list[tuple[int, int, int]] = []
    for x in range(max(x0, 0) + offset, min(x1, sx - 1) + 1, spacing):
        for z in range(max(z0, 0) + offset, min(z1, sz - 1) + 1, spacing):
            gy = ground_height(session.grid, x, z)
            if gy is None or gy + 2 >= sy:
                continue
            if session.grid.get(x, gy + 1, z) != AIR:
                continue
            if session.grid.get(x, gy + 2, z) != AIR:
                continue
            coords.append((x, gy + 1, z))
    if not coords:
        return 0
    return session.set_many(coords, light)
