"""Structural building generators: towers, battlements, bridges.

Composed entirely of existing primitives + session ops (so they get history,
validation, and chunked support for free), these encode the standard build
recipes professional mapmakers repeat constantly: shell -> floors -> windows
-> roof -> trim.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..blocks.block import AIR
from ..shapes.primitives import Box, Cone, Cylinder, Dome
from .palettes import get_palette
from .paths import ground_height, plan_path
from .roofs import apply_gable_roof, apply_hip_roof

if TYPE_CHECKING:
    from ..session.session import Session

_DIRECTION_OFFSETS = {"north": (0, -1), "south": (0, 1), "west": (-1, 0), "east": (1, 0)}


def apply_tower(session: Session, x: int, z: int, *, radius: int = 4,
                height: int | None = None, floors: int = 3,
                block: str | None = None, palette: str | None = None,
                roof: str = "cone", windows: bool = True,
                door: str | None = "south", seed: int = 0) -> dict[str, int]:
    """Build a round tower, terrain-snapped. Returns per-part voxel counts.

    - ``block`` defaults to the palette's dominant ``mix`` material.
    - ``floors`` interior slab platforms (palette ``trim``); 0 skips.
    - ``windows``: two-block slits per floor, rotated 90° between floors.
    - ``roof``: ``cone`` | ``hip`` | ``gable`` | ``dome`` | ``flat`` | ``none``.
      Cone/gable/hip materials come from the palette ``ramp`` (ridge color on
      top) for a proper value gradient.
    - ``door``: compass side to carve a 2-tall opening, or None.
    """
    if radius < 2:
        raise ValueError("radius must be >= 2")
    if floors < 0:
        raise ValueError("floors must be >= 0")
    if roof not in ("cone", "hip", "gable", "dome", "flat", "none"):
        raise ValueError(f"unknown roof kind {roof!r}")
    gy = ground_height(session.grid, x, z)
    if gy is None:
        raise ValueError(f"no ground at ({x}, {z})")
    pal = get_palette(palette) if palette else None
    wall_block = block or (pal.mix[0][0] if pal and pal.mix else "minecraft:stone_bricks")
    trim = pal.trim if pal else "minecraft:stone_slab"
    ramp_last = pal.ramp[-1] if pal and pal.ramp else wall_block
    base = gy + 1
    sy = session.grid.shape[1]
    reserves = {"cone": radius + 2, "dome": radius + 2, "hip": radius + 1,
                "gable": radius + 1, "flat": 2, "none": 1}
    degraded = False
    sy_avail = sy - base - reserves[roof]
    if sy_avail < 3 and roof not in ("flat", "none"):
        # degrade the roof to a crenellated flat top rather than refusing
        if sy - base - reserves["flat"] >= 3:
            roof = "flat"
            degraded = True
            sy_avail = sy - base - reserves["flat"]
    if sy_avail < 3:
        raise ValueError(f"not enough headroom for a tower here (base={base}, "
                         f"grid height {sy}, roof reserve {reserves[roof]})")
    default_h = 3 * max(floors + 1, 2) + radius
    h = min(height or default_h, sy_avail)
    # shrink floors so they never squeeze past the walls top
    floors = min(floors, max((h - 2) // 3, 1))
    counts: dict[str, int] = {"roof_degraded_to_flat": int(degraded)}

    def _solids() -> int:
        return int(session.stats().get("solid", 0))

    walls0 = _solids()
    # walls (hollow cylinder)
    session.add(Cylinder(x, z, radius, base, base + h - 1, hollow=True), wall_block)
    counts["walls"] = _solids() - walls0

    # floor platforms
    floors0 = _solids()
    if floors > 0:
        step = h // (floors + 1)
        for f in range(1, floors + 1):
            fy = base + f * step
            if fy >= base + h - 1:
                break
            session.add(Cylinder(x, z, radius - 1, fy, fy, hollow=False), trim)

    counts["floors"] = _solids() - floors0
    # window slits: pairs at alternating compass directions per floor
    if windows:
        for f in range(1, floors + 1):
            fy = base + f * step + 1
            if fy + 1 >= base + h - 1:
                continue
            ang0 = (f - 1) * math.pi / 2 + 0.8
            for k in range(2):
                ang = ang0 + k * math.pi
                wx = int(round(x + radius * math.cos(ang)))
                wz = int(round(z + radius * math.sin(ang)))
                session.subtract(Box(wx, fy, wz, wx, fy + 1, wz))

    # door
    if door and door in _DIRECTION_OFFSETS:
        dx, dz = _DIRECTION_OFFSETS[door]
        dx0 = x + dx * radius
        dz0 = z + dz * radius
        session.subtract(Box(dx0, base, dz0, dx0, base + 1, dz0))

    # roof
    roof0 = _solids()
    top = base + h
    if roof == "cone":
        session.add(Cone(x, z, radius + 1, top, min(top + radius + 2, sy - 1)), ramp_last)
    elif roof == "dome":
        session.add(Dome(x, top, z, radius + 1), ramp_last)
    elif roof == "hip":
        y0 = top - 1
        apply_hip_roof(session, (x - radius, y0, z - radius),
                       (x + radius, y0, z + radius),
                       ramp=[wall_block, ramp_last], overhang=1)
    elif roof == "gable":
        y0 = top - 1
        apply_gable_roof(session, (x - radius, y0, z - radius),
                         (x + radius, y0, z + radius), axis="x",
                         ramp=[wall_block, ramp_last], overhang=1)
    elif roof == "flat":
        apply_battlements(session, (x - radius, top - 1, z - radius),
                          (x + radius, top - 1, z + radius), block=trim)
    counts["roof"] = max(_solids() - roof0, 0)
    counts["height"] = h
    counts["top"] = top
    return counts


def apply_battlements(session: Session, frm: tuple[int, int, int],
                      to: tuple[int, int, int], *, block: str | None = None,
                      merlon_every: int = 2, height: int = 1) -> int:
    """Crenellate the top course of a wall box.

    Places merlons every ``merlon_every``th block along the perimeter ring one
    above the top surface, leaving gaps between (the battlements reads from a
    distance). With ``block=None`` the ring's modal material is reused so the
    merlons match the existing wall.
    """
    if merlon_every < 1 or height < 1:
        raise ValueError("merlon_every and height must be >= 1")
    x0, x1 = sorted((frm[0], to[0]))
    z0, z1 = sorted((frm[2], to[2]))
    # walk the perimeter loop in order so merlon parity alternates around it
    ring: list[tuple[int, int]] = [(xx, z0) for xx in range(x0, x1 + 1)]
    ring += [(x1, zz) for zz in range(z0 + 1, z1 + 1)]
    if x1 > x0 and z1 > z0:
        ring += [(xx, z1) for xx in range(x1 - 1, x0 - 1, -1)]
        ring += [(x0, zz) for zz in range(z1 - 1, z0, -1)]
    elif z1 == z0 and x1 > x0:
        pass  # single row already walked
    ring = [c for i, c in enumerate(ring) if i == 0 or c != ring[i - 1]]
    tops: dict[tuple[int, int], int] = {}
    for xx, zz in ring:
        gy = ground_height(session.grid, xx, zz)
        if gy is not None:
            tops[(xx, zz)] = gy
    if not tops:
        return 0
    if block is None:
        from collections import Counter
        c = Counter(session.grid.get(xx, gy, zz).name for (xx, zz), gy in tops.items())
        block = c.most_common(1)[0][0]
    sy = session.grid.shape[1]
    coords: list[tuple[int, int, int]] = []
    for i, ((xx, zz), gy) in enumerate(tops.items()):
        if i % merlon_every == 0:
            for dy in range(1, height + 1):
                if gy + dy < sy and session.grid.get(xx, gy + dy, zz) == AIR:
                    coords.append((xx, gy + dy, zz))
    if not coords:
        return 0
    return session.set_many(coords, block)


def apply_bridge(session: Session, points: list[tuple[int, ...]], *,
                 width: int = 3, deck: str | None = None,
                 palette: str | None = None, railing: str | None = None,
                 support: str | None = None, pier_spacing: int = 6,
                 lamps: bool = True) -> int:
    """Elevated deck over terrain with railings, evenly spaced piers, lamps.

    The deck height is the maximum ground height along the route +1, so it
    clears the terrain it crosses. ``deck``/``railing``/``support`` default
    to the palette's ``path``, ``trim`` and a generic log. Piers drop
    supports every ``pier_spacing`` core cells to the ground; lamps place the
    palette ``light`` on the railing every two piers.
    """
    pal = get_palette(palette) if palette else None
    deck_block = deck or (pal.path[0] if pal and pal.path else "minecraft:oak_planks")
    rail_block = railing or (pal.trim if pal else "minecraft:oak_fence")
    support_block = support or "minecraft:oak_log"
    light_block = pal.light if pal else "minecraft:lantern"
    # plan with drape to learn the terrain line, then re-base to max+1
    draped = plan_path(session.grid, points, width=width, drape=True)
    if not draped:
        return 0
    deck_y = max(draped.values()) + 1
    sy = session.grid.shape[1]
    if deck_y + 1 >= sy:
        raise ValueError("deck would exceed grid height")
    ordered = list(draped.items())
    offsets = _disc(width)
    changed = 0
    rail_cells: list[tuple[int, int, int]] = []
    for idx, ((cx, cz), _gy) in enumerate(ordered):
        for dx, dz in offsets:
            x, z = cx + dx, cz + dz
            if not (0 <= x < session.grid.shape[0] and 0 <= z < session.grid.shape[2]):
                continue
            changed += session.set_many([(x, deck_y, z)], deck_block)
        # piers at cell intervals (heights from the pre-deck plan, not the
        # live grid: the deck would otherwise masquerade as ground)
        if idx % max(pier_spacing, 1) == 0:
            start = _gy + 1
            col = [(cx, yy, cz) for yy in range(start, deck_y)]
            if col:
                changed += session.set_many(col, support_block)
    xzs = {c for c, _ in ordered}
    if rail_block:
        for (cx, cz), _gy in ordered:
            for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                x, z = cx + dx, cz + dz
                if (x, z) in xzs:
                    continue
                r2 = dx * dx + dz * dz
                if r2 <= 1:
                    pos = (x, deck_y + 1, z)
                    if 0 <= x < session.grid.shape[0] and 0 <= z < session.grid.shape[2]                             and session.grid.get(*pos) == AIR:
                        rail_cells.append(pos)
        # dedupe
        rail_cells = sorted(set(rail_cells))
        if rail_cells:
            changed += session.set_many(rail_cells, rail_block)
    if lamps and light_block and rail_cells:
        lamp_cells = rail_cells[:: max(len(rail_cells) // 8, 1)][:8]
        lamp_pos = [(x, y + 1, z) for x, y, z in lamp_cells if y + 1 < sy]
        if lamp_pos:
            changed += session.set_many(lamp_pos, light_block)
    return changed


def _disc(width: int) -> list[tuple[int, int]]:
    r = (width - 1) / 2.0
    out = []
    lo, hi = math.floor(-r), math.ceil(r)
    for dx in range(lo, hi + 1):
        for dz in range(lo, hi + 1):
            if dx * dx + dz * dz <= (r + 0.35) ** 2:
                out.append((dx, dz))
    return out
