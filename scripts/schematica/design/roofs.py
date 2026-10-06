"""Roof builders: the fastest way to make a facade look intentional.

``apply_gable_roof`` builds a pitched roof over a rectangular footprint,
expanding it by an ``overhang``, rising one voxel per ``steps_per_rise`` run
toward the ridge, and optionally laying stair courses facing the slope for
smooth edges. ``apply_hip_roof`` draws a four-sided hip roof whose hips run
from the footprint corners to the ridge.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .palettes import resolve_blocks

if TYPE_CHECKING:
    from ..session.session import Session


def _norm(frm: tuple[int, int, int], to: tuple[int, int, int]
          ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return (tuple(min(a, b) for a, b in zip(frm, to, strict=True)),
            tuple(max(a, b) for a, b in zip(frm, to, strict=True)))  # type: ignore[return-value]


def _ramp_for(block: str | None, ramp: list[str] | None, palette: str | None) -> list[str]:
    mats = resolve_blocks(ramp, palette_role="ramp") or resolve_blocks(palette, palette_role="ramp")
    if not mats and block:
        mats = [block]
    if not mats:
        mats = ["minecraft:oak_planks"]
    return mats


def _pick(mats: list[str], t: float) -> str:
    t = min(max(t, 0.0), 1.0)
    return mats[int(t * (len(mats) - 1) + 0.5)]


def apply_gable_roof(session: Session, frm: tuple[int, int, int],
                     to: tuple[int, int, int], *, axis: str = "x",
                     block: str | None = None,
                     ramp: list[str] | None = None,
                     palette: str | None = None,
                     overhang: int = 1, steps_per_rise: int = 1,
                     stair_block: str | None = None,
                     fill: bool = False) -> int:
    """Build a gable roof above the given wall box.

    ``frm``/``to`` describe the top of the walls; the roof starts one block
    above the box and is enlarged by ``overhang`` on every side. The ridge
    runs along ``axis`` (``"x"`` or ``"z"``). With a palette ``ramp``, eaves
    use ``ramp[0]`` and the ridge uses ``ramp[-1]`` (per-level gradient).
    ``stair_block`` (e.g. ``minecraft:<family>_stairs``) lays facing stair
    courses on the outermost course per level for smooth rooflines.
    Returns voxels written.
    """
    if axis not in ("x", "z"):
        raise ValueError("axis must be 'x' or 'z'")
    if overhang < 0 or steps_per_rise < 1:
        raise ValueError("overhang >= 0 and steps_per_rise >= 1 required")
    (x0, y0, z0), (x1, y1, z1) = _norm(frm, to)
    mats = _ramp_for(block, ramp, palette)
    base_y = y1 + 1
    span_ax = "z" if axis == "x" else "x"
    if span_ax == "z":
        lo, hi = z0 - overhang, z1 + overhang
        r0, r1 = x0 - overhang, x1 + overhang
    else:
        lo, hi = x0 - overhang, x1 + overhang
        r0, r1 = z0 - overhang, z1 + overhang
    width = hi - lo + 1
    levels = math.ceil(width / 2 / steps_per_rise)
    sx, sy, sz = session.grid.shape

    def clip3(p: tuple[int, int, int]) -> tuple[int, int, int]:
        return (min(max(p[0], 0), sx - 1), min(max(p[1], 0), sy - 1),
                min(max(p[2], 0), sz - 1))

    writes: dict[tuple[int, int, int], str] = {}
    last_level = levels - 1
    for level in range(levels):
        y = base_y + level
        t = level / max(last_level, 1)
        mat = _pick(mats, t)
        inner_lo = lo + level * steps_per_rise
        inner_hi = hi - level * steps_per_rise
        if inner_lo > inner_hi:
            break
        low_edge = inner_lo + steps_per_rise - 1
        high_edge = inner_hi - steps_per_rise + 1
        for s in range(inner_lo, inner_hi + 1):
            is_edge = s <= low_edge or s >= high_edge
            if not is_edge and not fill and level != last_level:
                continue
            for rr in range(r0, r1 + 1):
                use_stair = (
                    stair_block is not None and steps_per_rise == 1
                    and is_edge and not fill and level != last_level
                )
                if use_stair:
                    low_side = s <= low_edge
                    if span_ax == "z":
                        facing = "north" if low_side else "south"
                    else:
                        facing = "west" if low_side else "east"
                    block_here = f"{stair_block}[facing={facing}]"
                else:
                    block_here = mat
                pos = clip3((rr, y, s) if span_ax == "z" else (s, y, rr))
                writes[pos] = block_here
    # ridge cap along the full ridge length
    width_even = width % 2 == 0
    mid = (lo + hi) // 2
    ridge_positions = [mid, mid + 1] if width_even else [mid]
    y_ridge = base_y + levels
    for rr in range(r0, r1 + 1):
        for s in ridge_positions:
            pos = clip3((rr, y_ridge, s) if span_ax == "z" else (s, y_ridge, rr))
            writes[pos] = mats[-1]
    changed = 0
    by_block: dict[str, list[tuple[int, int, int]]] = {}
    for pos, b in writes.items():
        by_block.setdefault(b, []).append(pos)
    for b, coords in by_block.items():
        session.set_many(coords, b)
        changed += len(coords)
    return changed


def apply_hip_roof(session: Session, frm: tuple[int, int, int],
                   to: tuple[int, int, int], *, block: str | None = None,
                   ramp: list[str] | None = None, palette: str | None = None,
                   overhang: int = 1, steps_per_rise: int = 1) -> int:
    """Build a hip roof: all four faces slope up to a central ridge.

    Each level insets the footprint by ``steps_per_rise`` on both axes and
    draws a perimeter course; the roof ends at the ridge line along the long
    axis. Good default when a plain gable looks flat on square towers.
    """
    if steps_per_rise < 1 or overhang < 0:
        raise ValueError("steps_per_rise >= 1 and overhang >= 0 required")
    (x0, y0, z0), (x1, y1, z1) = _norm(frm, to)
    mats = _ramp_for(block, ramp, palette)
    base_y = y1 + 1
    lx0, lx1 = x0 - overhang, x1 + overhang
    lz0, lz1 = z0 - overhang, z1 + overhang
    levels = math.ceil(min(lx1 - lx0 + 1, lz1 - lz0 + 1) / 2 / steps_per_rise)
    sx, sy, sz = session.grid.shape
    writes: dict[tuple[int, int, int], str] = {}
    for level in range(levels):
        y = base_y + level
        if y >= sy:
            break
        t = level / max(levels - 1, 1)
        mat = _pick(mats, t)
        ix0, ix1 = lx0 + level * steps_per_rise, lx1 - level * steps_per_rise
        iz0, iz1 = lz0 + level * steps_per_rise, lz1 - level * steps_per_rise
        if ix0 > ix1 or iz0 > iz1:
            break
        for x in range(max(ix0, 0), min(ix1, sx - 1) + 1):
            for z in range(max(iz0, 0), min(iz1, sz - 1) + 1):
                edge = (x - ix0 < steps_per_rise or ix1 - x < steps_per_rise
                        or z - iz0 < steps_per_rise or iz1 - z < steps_per_rise)
                if edge or level == levels - 1:
                    writes[(x, y, z)] = mat
    changed = 0
    by_block: dict[str, list[tuple[int, int, int]]] = {}
    for pos, b in writes.items():
        by_block.setdefault(b, []).append(pos)
    for b, coords in by_block.items():
        session.set_many(coords, b)
        changed += len(coords)
    return changed
