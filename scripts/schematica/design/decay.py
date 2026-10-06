"""Ruin & decay generator: the fastest way to make ruins believable.

`apply_ruin` removes blocks with a probability that grows with height and
exposure (tops collapse first), then rains a light rubble scatter of matching
materials at grade level. Everything is seeded and goes through session
history; both grid backends supported.
"""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

from ..blocks.block import AIR
from ..procedural.detail import _air_neighbour_count
from .paths import ground_height

if TYPE_CHECKING:
    from ..session.session import Session

_RUBBLE_DEFAULTS = ("minecraft:cobblestone", "minecraft:mossy_cobblestone",
                    "minecraft:gravel")


def apply_ruin(session: Session, frm: tuple[int, int, int],
               to: tuple[int, int, int], *, amount: float = 0.35,
               seed: int = 0, collapse_bias: float = 1.0,
               debris: bool = True,
               debris_blocks: list[str] | None = None) -> int:
    """Randomly demolish the contents of [frm, to].

    Removal probability at voxel y is ``amount * height_factor(y)`` where the
    height factor rises from ~0.6f at the region floor to ~1.4x at the top
    when ``collapse_bias=1`` (linear; 0 = uniform decay). A block with at
    least one air neighbour gets +0.15 probability (exterior crumbles first).

    With ``debris=True`` a light scatter (~12% of removed blocks, capped) of
    rubble material lands on the ground inside the footprint, so the ruin
    leaves believable residue instead of a clean cut. Returns voxels removed
    + debris placed.
    """
    if not (0.0 < amount <= 1.0):
        raise ValueError("amount must be in (0, 1]")
    x0, x1 = sorted((frm[0], to[0]))
    y0, y1 = sorted((frm[1], to[1]))
    z0, z1 = sorted((frm[2], to[2]))
    sx, sy, sz = session.grid.shape
    x0, x1 = max(x0, 0), min(x1, sx - 1)
    y0, y1 = max(y0, 0), min(y1, sy - 1)
    z0, z1 = max(z0, 0), min(z1, sz - 1)
    if x0 > x1 or y0 > y1 or z0 > z1:
        return 0

    from ..procedural.detail import _dense_region
    dense_h = _dense_region(session.grid, (x0, y0, z0), (x1, y1, z1), halo=1)
    region = dense_h[1:-1, 1:-1, 1:-1]
    solid = region != 0
    if not solid.any():
        return 0
    rng = np.random.default_rng(seed)
    ys = np.arange(y0, y1 + 1, dtype=np.float32)
    span = max(y1 - y0, 1)
    hf = 0.6 + 0.8 * collapse_bias * (ys - y0) / span  # bottom .6x .. top 1.4x
    prob = amount * hf[None, :, None]
    prob = np.broadcast_to(prob, region.shape).copy()
    exposed = _air_neighbour_count(dense_h)[1:-1, 1:-1, 1:-1] > 0
    prob = prob + np.where(exposed, 0.15, 0.0)
    kill = solid & (rng.random(region.shape) < prob)
    n_kill = int(np.count_nonzero(kill))
    if n_kill == 0:
        return 0

    # gather material histogram for plausible rubble
    removed_idx = region[kill]
    pal = session.grid.palette.blocks()
    removed_names = Counter(pal[int(i)].name for i in removed_idx)

    coords = np.argwhere(kill)
    session.set_many([(int(x0 + x), int(y0 + y), int(z0 + z)) for x, y, z in coords],
                     AIR)
    changed = n_kill

    if debris:
        rubble = debris_blocks or (
            [n for n, _ in removed_names.most_common(2)] if removed_names else list(_RUBBLE_DEFAULTS)
        )
        n_drop = min(max(n_kill // 8, 1), 64)
        drops: list[tuple[int, int, int]] = []
        for _ in range(n_drop * 3):
            if len(drops) >= n_drop:
                break
            x = int(rng.integers(x0, x1 + 1))
            z = int(rng.integers(z0, z1 + 1))
            gy = ground_height(session.grid, x, z)
            if gy is None or gy + 1 >= sy:
                continue
            if session.grid.get(x, gy + 1, z) != AIR:
                continue
            drops.append((x, gy + 1, z))
        if drops:
            session.set_many(drops, rubble[0])
        changed += len(drops)
    return changed
