"""Terrain-aware roads and rivers: the connective tissue of a real map.

These tools rasterize 2D/3D polylines (with optional Catmull-Rom smoothing)
and lay them on the actual terrain surface, one cell at a time, using
``ground_height`` scans. Deterministic per-cell variation keeps long roads
from looking machine-stamped.

Both work through :class:`~schematica.session.session.Session` methods and
support the dense and chunked backends.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from ..blocks.block import AIR
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid
from .palettes import resolve_blocks

if TYPE_CHECKING:
    from ..session.session import Session

Grid = VoxelGrid | ChunkedGrid


def ground_height(grid: Grid, x: int, z: int) -> int | None:
    """Y of the topmost non-air voxel in column (x, z), or None if empty."""
    sx, sy, sz = grid.shape
    if not (0 <= x < sx and 0 <= z < sz):
        return None
    if isinstance(grid, VoxelGrid):
        col = grid.data[x, :, z]
        nz = np.flatnonzero(col)
        return int(nz[-1]) if nz.size else None
    for y in range(sy - 1, -1, -1):
        if grid.get(x, y, z) != AIR:
            return y
    return None


# --------------------------------------------------------------------------
# polyline sampling / rasterization
# --------------------------------------------------------------------------

def _as_3d(points: list[tuple[int, ...]]) -> list[tuple[float, float, float]]:
    out = []
    for p in points:
        if len(p) == 2:
            out.append((float(p[0]), float("nan"), float(p[1])))
        elif len(p) == 3:
            out.append((float(p[0]), float(p[1]), float(p[2])))
        else:
            raise ValueError(f"path point must be (x,z) or (x,y,z), got {p!r}")
    return out


def _catmull_rom(points: list[tuple[float, float, float]], subdiv: int,
                 closed: bool) -> list[tuple[float, float, float]]:
    if len(points) < 3 or subdiv <= 1:
        return list(points)
    pts = list(points)
    if closed:
        pts = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        pts = [pts[0]] + pts + [pts[-1]]
    out: list[tuple[float, float, float]] = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(subdiv):
            t = j / subdiv
            t2, t3 = t * t, t * t * t
            c = []
            for k in range(3):
                v = 0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t
                           + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                           + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                c.append(v)
            out.append((c[0], c[1], c[2]))
    out.append(points[-1 if closed else -1])
    return out


def _rasterize(points: list[tuple[float, float, float]],
               closed: bool) -> list[tuple[int, int]]:
    """Ordered supercover XZ cells along the path (deduplicated, in order)."""
    seq = points + ([points[0]] if closed else [])
    cells: list[tuple[int, int]] = []
    seen_prev: set[int] = set()
    for a, b in zip(seq, seq[1:], strict=False):
        dx, dz = b[0] - a[0], b[2] - a[2]
        steps = int(max(abs(dx), abs(dz), 1.0)) * 3
        for i in range(steps + 1):
            t = i / steps
            x = int(round(a[0] + dx * t))
            z = int(round(a[2] + dz * t))
            key = x * 100003 + z
            if key in seen_prev and cells and cells[-1] == (x, z):
                continue
            if not cells or cells[-1] != (x, z):
                cells.append((x, z))
            seen_prev.add(key)
    return cells


def _smooth_heights(ys: list[int | None], window: int = 5) -> list[int | None]:
    """Small running median along path order to avoid stair-stepping roads."""
    n = len(ys)
    out: list[int | None] = list(ys)
    half = window // 2
    for i in range(n):
        vals = [v for v in ys[max(0, i - half): i + half + 1] if v is not None]
        if vals:
            out[i] = int(sorted(vals)[len(vals) // 2])
    return out


def _cell_pick(x: int, z: int, seed: int, n: int) -> int:
    """Deterministic per-cell index in [0, n) -- stable regardless of order."""
    if n <= 1:
        return 0
    h = (x * 7349) ^ (z * 9113) ^ (seed * 2654435761 & 0xFFFFFFFF)
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return h % n


def _disc_offsets(width: int) -> list[tuple[int, int]]:
    r = (width - 1) / 2.0
    out = []
    lo, hi = math.floor(-r), math.ceil(r)
    for dx in range(lo, hi + 1):
        for dz in range(lo, hi + 1):
            if dx * dx + dz * dz <= (r + 0.35) ** 2:
                out.append((dx, dz))
    return out


def plan_path(grid: Grid, points: list[tuple[int, ...]], *, width: int = 3,
              drape: bool = True, closed: bool = False, smooth: int = 0,
              smooth_drape: bool = True) -> dict[tuple[int, int], int]:
    """Compute ``{(x, z): y}`` cells for the core ribbon of a draped path.

    With ``drape=False`` and 3D points, the given y values are used (lerped
    between consecutive points) instead of terrain height.
    """
    pts = _as_3d(points)
    if len(pts) < 2:
        raise ValueError("path needs at least 2 points")
    sampled = _catmull_rom(pts, max(int(smooth), 1), closed)
    cells = _rasterize(sampled, closed)
    # per-cell y
    core_y: list[int | None] = []
    have_y = all(not math.isnan(p[1]) for p in pts)
    for idx, (cx, cz) in enumerate(cells):
        if not drape and have_y:
            # interpolate y from the sampled polyline position
            t = idx / max(len(cells) - 1, 1)
            yf = np.interp(t, np.linspace(0, 1, len(sampled)),
                           [p[1] for p in sampled])
            core_y.append(int(round(yf)))
        else:
            core_y.append(ground_height(grid, cx, cz))
    if drape and smooth_drape and len(cells) >= 5:
        core_y = _smooth_heights(core_y)
    return {c: y for c, y in zip(cells, core_y, strict=True) if y is not None}


def apply_path(session: Session, points: list[tuple[int, ...]], *,
               width: int = 3, block: str | None = None,
               blocks: list[str] | None = None,
               palette: str | None = None,
               border: str | None = None,
               drape: bool = True, closed: bool = False,
               smooth: int = 0, smooth_drape: bool = True,
               support: str | None = None, seed: int = 0) -> int:
    """Lay a road along ``points`` (x,z) or (x,y,z), terrain-draped by default.

    Material resolution order: ``blocks`` list (per-cell deterministic mix) >
    ``palette`` name (its ``path`` role) > single ``block``. ``border`` places
    a kerb course one above ground on the rim cells (only into air).
    ``support`` fills columns below fixed-elevation (non-draped) sections
    until ground is met -- use for bridges/viaducts. Returns voxels written.
    """
    mats = resolve_blocks(blocks, palette_role="path") or resolve_blocks(palette, palette_role="path")
    if not mats:
        mats = [block] if block else ["minecraft:cobblestone"]
    plan = plan_path(session.grid, points, width=width, drape=drape,
                     closed=closed, smooth=smooth, smooth_drape=smooth_drape)
    if not plan:
        return 0
    offsets = _disc_offsets(max(int(width), 1))
    sx, sy, sz = session.grid.shape
    writes: dict[tuple[int, int, int], str] = {}
    rim: dict[tuple[int, int], int] = {}
    road_xz: set[tuple[int, int]] = set()
    for (cx, cz), y in plan.items():
        for dx, dz in offsets:
            x, z = cx + dx, cz + dz
            if not (0 <= x < sx and 0 <= z < sz):
                continue
            road_xz.add((x, z))
            if drape:
                gy = ground_height(session.grid, x, z)
                if gy is None:
                    continue
                write: dict[tuple[int, int, int], str] = {(x, gy, z): mats[_cell_pick(x, z, seed, len(mats))]}
                if (dx * dx + dz * dz) == 0 and border is None:
                    pass
                writes.update(write)
            else:
                if (dx, dz) == (0, 0):
                    level = y
                else:
                    gy = ground_height(session.grid, x, z)
                    level = gy if gy is not None else y
                writes[(x, level, z)] = mats[_cell_pick(x, z, seed, len(mats))]
        if border:
            br = (width - 1) / 2.0 + 1.5
            for dx in range(-int(br) - 1, int(br) + 2):
                for dz in range(-int(br) - 1, int(br) + 2):
                    dist2 = dx * dx + dz * dz
                    x, z = cx + dx, cz + dz
                    if (br - 1.6) ** 2 < dist2 <= br * br and (x, z) not in road_xz:
                        if 0 <= x < sx and 0 <= z < sz:
                            gy = ground_height(session.grid, x, z) if drape else None
                            yy = (gy + 1) if (drape and gy is not None) else None
                            if yy is not None and yy < sy:
                                rim.setdefault((x, z), yy)
    # core ribbon writes
    changed = 0
    by_block: dict[str, list[tuple[int, int, int]]] = {}
    for (x, y, z), m in writes.items():
        by_block.setdefault(m, []).append((x, y, z))
    for m, coords in by_block.items():
        session.set_many(coords, m)
        changed += len(coords)
    if border and rim:
        coords = [(x, y, z) for (x, z), y in rim.items()
                  if session.grid.get(x, y, z) == AIR]
        if coords:
            session.set_many(coords, border)
            changed += len(coords)
    if support and not drape:
        supp: list[tuple[int, int, int]] = []
        for (cx, cz), y in plan.items():
            gy = ground_height(session.grid, cx, cz)
            top = min(y - 1, sy - 1)
            start = (gy + 1) if gy is not None else 0
            for yy in range(start, top + 1):
                supp.append((cx, yy, cz))
        if supp:
            session.set_many(supp, support)
            changed += len(supp)
    return changed


def apply_river(session: Session, points: list[tuple[int, ...]], *,
                width: int = 3, depth: int = 3,
                water: str = "minecraft:water",
                bed: str | None = None,
                drape: bool = True,
                closed: bool = False, smooth: int = 0) -> int:
    """Carve a river channel along points and fill it with water.

    The channel floor sits ``depth`` below grade; water fills up to one block
    below the original grade so banks remain walkable. ``bed`` (e.g. gravel,
    sand, dirt mix) repaves the channel floor. Returns voxels changed
    (carved + filled).
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    plan = plan_path(session.grid, points, width=width, drape=drape,
                     closed=closed, smooth=smooth, smooth_drape=True)
    if not plan:
        return 0
    offsets = _disc_offsets(max(int(width), 1))
    sx, sy, sz = session.grid.shape
    carve: list[tuple[int, int, int]] = []
    water_list: list[tuple[int, int, int]] = []
    bed_list: list[tuple[int, int, int]] = []
    for (cx, cz), gy in plan.items():
        for dx, dz in offsets:
            x, z = cx + dx, cz + dz
            if not (0 <= x < sx and 0 <= z < sz):
                continue
            g = ground_height(session.grid, x, z) if drape else gy
            if g is None:
                continue
            bottom = g - depth + 1
            for y in range(bottom, g + 1):
                if 0 <= y < sy:
                    carve.append((x, y, z))
            if depth >= 2:
                for y in range(bottom + 1, g):
                    water_list.append((x, y, z))
                if bed:
                    bed_list.append((x, bottom, z))
    session.set_many(carve, AIR)
    changed = len(carve)
    if bed_list and bed:
        session.set_many(bed_list, bed)
        changed += len(bed_list)
    if water_list:
        session.set_many(water_list, water)
        changed += len(water_list)
    return changed
