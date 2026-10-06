"""District layout tools: foundation pads, plazas, and road networks.

These are the tools that turn "a bunch of structures" into a *map*:
`apply_flatten` gives buildings honest foundations, `apply_plaza` creates
spawn hubs and market squares, and `apply_road_network` connects a set of
points with a minimum-spanning-tree of draped roads (or a full mesh).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from ..blocks.block import AIR
from .palettes import get_palette, resolve_blocks
from .paths import apply_path, ground_height

if TYPE_CHECKING:
    from ..session.session import Session


def _xz(frm: tuple[int, int, int], to: tuple[int, int, int]
        ) -> tuple[int, int, int, int]:
    x0, x1 = sorted((frm[0], to[0]))
    z0, z1 = sorted((frm[2], to[2]))
    return x0, x1, z0, z1


def apply_flatten(session: Session, frm: tuple[int, int, int],
                  to: tuple[int, int, int], *, y: int | None = None,
                  fill: str = "minecraft:dirt",
                  cap: str | None = None) -> int:
    """Flatten the XZ footprint of [frm, to] to a level pad.

    ``y`` defaults to the median ground height of the occupied columns, which
    keeps the pad embedded in the terrain instead of floating. Columns above
    the target are cut; columns below are filled with ``fill`` (``cap`` as the
    surface block when given, e.g. grass_block or stone_bricks). All writes go
    through session history; both backends are supported.

    Returns voxels changed.
    """
    x0, x1, z0, z1 = _xz(frm, to)
    if y is None:
        heights = [g for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
                   if (g := ground_height(session.grid, x, z)) is not None]
        if not heights:
            return 0
        y = int(np.median(np.array(heights, dtype=float)))
    sx, sy, sz = session.grid.shape
    y = min(max(y, 0), sy - 1)
    carve: list[tuple[int, int, int]] = []
    fill_l: list[tuple[int, int, int]] = []
    cap_l: list[tuple[int, int, int]] = []
    for x in range(max(x0, 0), min(x1, sx - 1) + 1):
        for z in range(max(z0, 0), min(z1, sz - 1) + 1):
            top = ground_height(session.grid, x, z)
            if top is None:
                continue
            if top > y:
                carve.extend((x, yy, z) for yy in range(y + 1, top + 1))
            elif top < y:
                fill_l.extend((x, yy, z) for yy in range(top + 1, y + 1))
            if cap:
                # uniform surface: top of every occupied column is the pad cap
                cap_l.append((x, y, z))
    changed = 0
    if carve:
        changed += session.set_many(carve, AIR)
    if fill_l:
        changed += session.set_many(fill_l, fill)
    if cap_l:
        changed += session.set_many(cap_l, cap or fill)
    return changed


def apply_plaza(session: Session, center: tuple[int, ...], radius: int, *,
                palette: str | None = None,
                bands: list[str] | None = None,
                ring_spacing: int = 4,
                border: str | None = None,
                fountain: bool = True,
                light: str | None = None) -> int:
    """Flatten and pave a circular plaza with concentric paving bands.

    ``center`` accepts (x, z) or (x, y, z); the pad level is the median
    ground height over the footprint. Band materials default to the palette's
    ``path`` role and alternate every ``ring_spacing`` of radius. A trim
    border ring, four diagonal light posts, and an optional central fountain
    (trim basin, water, light-topped pillar) complete the spawn hub.
    """
    if radius < 3:
        raise ValueError("radius must be >= 3")
    if ring_spacing < 1:
        raise ValueError("ring_spacing must be >= 1")
    cx, cz = center[0], center[-1]
    mats = resolve_blocks(bands, palette_role="path") or         resolve_blocks(palette, palette_role="path")
    if not mats:
        mats = ["minecraft:cobblestone", "minecraft:stone_bricks"]
    if len(mats) == 1:
        mats = mats * 2
    pal = get_palette(palette) if palette else None
    border_block = border or (pal.trim if pal else "minecraft:stone_slab")
    light_block = light if light is not None else (pal.light if pal else "minecraft:lantern")

    changed = apply_flatten(session, (cx - radius, 0, cz - radius),
                            (cx + radius, 0, cz + radius))
    gy = ground_height(session.grid, cx, cz)
    if gy is None:
        return changed
    pad_y = gy
    sy = session.grid.shape[1]

    pave: dict[str, list[tuple[int, int, int]]] = {}
    border_cells: list[tuple[int, int, int]] = []
    for dx in range(-radius, radius + 1):
        for dz in range(-radius, radius + 1):
            r = math.hypot(dx, dz)
            if r > radius + 0.4:
                continue
            pos = (cx + dx, pad_y, cz + dz)
            if r >= radius - 1.2:
                border_cells.append(pos)
                continue
            mat = mats[(int(r) // ring_spacing) % len(mats)]
            pave.setdefault(mat, []).append(pos)
    for b, coords in pave.items():
        changed += session.set_many(coords, b)
    if border_cells:
        changed += session.set_many(border_cells, border_block)
    if light_block and pad_y + 1 < sy:
        for sx_, sz_ in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            d = int(round((radius - 2) * math.sqrt(0.5)))
            x, z = cx + sx_ * d, cz + sz_ * d
            if session.grid.get(x, pad_y + 1, z) == AIR:
                changed += session.set_many([(x, pad_y + 1, z)], light_block)
    if fountain and pad_y + 2 < sy:
        rim: list[tuple[int, int, int]] = []
        water: list[tuple[int, int, int]] = []
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                rr = math.hypot(dx, dz)
                if 1.2 < rr <= 2.2:
                    rim.append((cx + dx, pad_y + 1, cz + dz))
                elif 0.6 < rr <= 1.2:
                    water.append((cx + dx, pad_y, cz + dz))
        changed += session.set_many(rim, border_block)
        changed += session.set_many(water, "minecraft:water")
        changed += session.set_many([(cx, pad_y + 1, cz), (cx, pad_y + 2, cz)],
                                    border_block)
        if light_block and pad_y + 3 < sy:
            changed += session.set_many([(cx, pad_y + 3, cz)], light_block)
    return changed


def mst_edges(points: list[tuple[int, ...]]) -> list[tuple[int, int]]:
    """Prim minimum spanning tree over XZ Euclidean distances.

    Returns index pairs into ``points`` — the minimal set of roads that
    keeps the network fully connected.
    """
    n = len(points)
    if n < 2:
        return []
    xs = np.array([p[0] for p in points], dtype=float)
    zs = np.array([p[-1] for p in points], dtype=float)
    in_tree = {0}
    edges: list[tuple[int, int]] = []
    while len(in_tree) < n:
        best: tuple[int, int] | None = None
        best_d = float("inf")
        for i in in_tree:
            d = np.hypot(xs - xs[i], zs - zs[i])
            for j in range(n):
                if j not in in_tree and d[j] < best_d:
                    best_d = float(d[j])
                    best = (i, j)
        assert best is not None
        edges.append(best)
        in_tree.add(best[1])
    return edges


def apply_road_network(session: Session, points: list[tuple[int, ...]], *,
                       width: int = 3, palette: str | None = None,
                       blocks: list[str] | None = None,
                       border: str | None = None, smooth: int = 0,
                       complete: bool = False,
                       extra_edges: list[tuple[int, int]] | None = None,
                       seed: int = 0) -> list[tuple[int, int]]:
    """Connect waypoints with terrain-draped roads. Returns the edge list.

    Default: a minimum spanning tree (no redundant loops). ``complete=True``
    connects every pair; ``extra_edges=[(i, j), ...]`` adds specific loops on
    top of the MST — designers use this for ring roads around a plaza.
    """
    if len(points) < 2:
        raise ValueError("road network needs at least 2 points")
    n = len(points)
    if complete:
        edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    else:
        edges = mst_edges(points)
    seen = {(min(e), max(e)) for e in edges}
    for e in extra_edges or []:
        key = (min(e), max(e))
        if key not in seen:
            edges.append(e)
            seen.add(key)
    for i, j in edges:
        a, b = points[i], points[j]
        pa = (a[0], a[-1])
        pb = (b[0], b[-1])
        apply_path(session, [pa, pb], width=width, palette=palette,
                   blocks=blocks, border=border, smooth=smooth, seed=seed)
    return edges
