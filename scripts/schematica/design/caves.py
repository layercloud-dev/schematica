"""Cave carving: 3D Perlin worms/hollows through existing solids.

`apply_caves` evaluates a 3D simplex-noise field over the region and carves
every *solid* voxel whose field value exceeds ``threshold``. A
``protect_surface`` rule keeps a skin of terrain intact so caves stay
underground unless deliberately breached.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..blocks.block import AIR
from ..generators.noise import perlin3d
from .paths import ground_height

if TYPE_CHECKING:
    from ..session.session import Session


def apply_caves(session: Session, frm: tuple[int, int, int],
                to: tuple[int, int, int], *, scale: float = 0.08,
                octaves: int = 3, threshold: float = 0.6, seed: int = 0,
                protect_surface: int = 3) -> int:
    """Carve a cave system inside [frm, to]; returns voxels removed.

    - ``scale``: noise frequency (smaller = larger cavities).
    - ``threshold`` in (0, 1): higher = sparser caves. 0.55-0.75 is the
      useful band for coherent tunnels.
    - ``protect_surface``: only carve voxels at least this many blocks below
      the local surface (0 = may breach the surface too).
    """
    if not (0.0 < threshold < 1.0):
        raise ValueError("threshold must be in (0, 1)")
    if scale <= 0:
        raise ValueError("scale must be positive")
    x0, x1 = sorted((frm[0], to[0]))
    y0, y1 = sorted((frm[1], to[1]))
    z0, z1 = sorted((frm[2], to[2]))
    sx, sy, sz = session.grid.shape
    x0, x1 = max(x0, 0), min(x1, sx - 1)
    y0, y1 = max(y0, 0), min(y1, sy - 1)
    z0, z1 = max(z0, 0), min(z1, sz - 1)
    shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
    if any(d <= 0 for d in shape):
        return 0
    field = perlin3d(shape, scale=scale, octaves=octaves, seed=seed)
    from ..procedural.detail import _dense_region
    region = _dense_region(session.grid, (x0, y0, z0), (x1, y1, z1))
    solid = region != 0
    carve = solid & (field > threshold)
    if protect_surface > 0:
        # voxel at (x, y, z) is carvable only if surface is protect_surface above
        xs, ys, zs = np.indices(shape)
        keep_mask = np.zeros(shape, dtype=bool)
        for x in range(shape[0]):
            for z in range(shape[2]):
                gy = ground_height(session.grid, x0 + x, z0 + z)
                if gy is None:
                    continue
                min_y = gy - protect_surface + 1
                col = min(max(min_y - y0, 0), shape[1])
                keep_mask[x, col:, z] = True
        carve &= ~keep_mask
    coords = np.argwhere(carve)
    if len(coords) == 0:
        return 0
    pts = [(int(x0 + x), int(y0 + y), int(z0 + z)) for x, y, z in coords]
    return session.set_many(pts, AIR)
