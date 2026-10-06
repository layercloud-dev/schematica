"""Procedural micro-detail tools: gradients, edge wear, surface scatter.

These tools add organic weathering and variation to builds by operating on
existing solid voxels. They never fill empty space -- they modify blocks that
are already placed, so they are safe to run after the structural build is
complete.

All tools work on both ``VoxelGrid`` (dense) and ``ChunkedGrid`` (sparse)
backends. On chunked grids they stream chunk-by-chunk with a one-voxel halo
for neighbour lookups, so they scale to maps that would not fit a dense copy
in memory. (Noise-seeded scatter/gradient jitter draws are per-backend and
therefore not bit-identical across backends; structural results are.)
"""
from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from ..blocks.block import Block
from ..core.chunked import ChunkedGrid
from ..core.voxel import VoxelGrid

Grid = VoxelGrid | ChunkedGrid


# ---- dense helpers -------------------------------------------------------

def _dense_data(grid: Grid) -> np.ndarray:
    """Return a writable dense uint16 view (or copy) for vectorised ops."""
    if isinstance(grid, ChunkedGrid):
        return grid.to_dense().data
    return grid.data


def _air_neighbour_count(dense: np.ndarray) -> np.ndarray:
    """Count air face-neighbours per voxel; out-of-bounds counts as air."""
    air = dense == 0
    count = np.zeros(dense.shape, dtype=np.int8)
    px = np.zeros(dense.shape, dtype=bool)
    px[:-1, :, :] = air[1:, :, :]
    px[-1, :, :] = True
    count += px
    nx = np.zeros(dense.shape, dtype=bool)
    nx[1:, :, :] = air[:-1, :, :]
    nx[0, :, :] = True
    count += nx
    py = np.zeros(dense.shape, dtype=bool)
    py[:, :-1, :] = air[:, 1:, :]
    py[:, -1, :] = True
    count += py
    ny = np.zeros(dense.shape, dtype=bool)
    ny[:, 1:, :] = air[:, :-1, :]
    ny[:, 0, :] = True
    count += ny
    pz = np.zeros(dense.shape, dtype=bool)
    pz[:, :, :-1] = air[:, :, 1:]
    pz[:, :, -1] = True
    count += pz
    nz = np.zeros(dense.shape, dtype=bool)
    nz[:, :, 1:] = air[:, :, :-1]
    nz[:, :, 0] = True
    count += nz
    return count


def _dense_region(grid: Grid, lo: tuple[int, int, int], hi: tuple[int, int, int],
                  halo: int = 0) -> np.ndarray:
    """Dense uint16 array for region [lo..hi] plus ``halo`` ghost rings.

    Cells outside the grid / absent chunks read as air (0). Memory scales with
    the *region*, not the whole map, so this is the right way to run
    voxel-neighbour ops on chunked mega-maps.
    """
    gs = grid.shape
    rlo = [lo[i] - halo for i in range(3)]
    rhi = [hi[i] + halo for i in range(3)]
    shape = tuple(rhi[i] - rlo[i] + 1 for i in range(3))
    out = np.zeros(shape, dtype=np.uint16)
    vlo = [max(rlo[i], 0) for i in range(3)]
    vhi = [min(rhi[i], gs[i] - 1) for i in range(3)]
    if any(vlo[i] > vhi[i] for i in range(3)):
        return out
    dst = tuple(slice(vlo[i] - rlo[i], vhi[i] - rlo[i] + 1) for i in range(3))
    if not isinstance(grid, ChunkedGrid):
        out[dst] = grid.data[vlo[0]:vhi[0] + 1, vlo[1]:vhi[1] + 1,
                             vlo[2]:vhi[2] + 1].astype(np.uint16, copy=False)
        return out
    for cx, cy, cz, arr, origin in grid.iter_chunks_in_box(vlo[0], vlo[1], vlo[2],
                                                           vhi[0], vhi[1], vhi[2]):
        cs = grid._chunk_shape(cx, cy, cz)
        glo: list[int] = []
        ghi: list[int] = []
        for i in range(3):
            glo.append(max(vlo[i], origin[i]))
            ghi.append(min(vhi[i], origin[i] + cs[i] - 1))
            if glo[i] > ghi[i]:
                break
        else:
            src_slc = tuple(slice(glo[i] - origin[i], ghi[i] - origin[i] + 1)
                            for i in range(3))
            dst_slc = tuple(slice(glo[i] - rlo[i], ghi[i] - rlo[i] + 1)
                            for i in range(3))
            out[dst_slc] = arr[src_slc]
    return out


# ---- chunked helpers ------------------------------------------------------

def _iter_halo_chunks(grid: ChunkedGrid
                      ) -> Iterator[tuple[tuple[int, int, int], np.ndarray, np.ndarray, tuple[int, int, int]]]:
    """Yield ``(chunk_key, core_array, halo_array, core_shape)`` per chunk.

    ``halo_array`` has shape ``core_shape + 2`` with the chunk's own data in
    the centre and one ring of ghost cells copied from existing neighbour
    chunks (missing neighbours / out-of-bounds = air). Mutations should be
    written to ``core_array`` (the live chunk storage).
    """
    for cx, cy, cz, arr in list(grid.iter_chunks()):
        shape = grid._chunk_shape(cx, cy, cz)
        ox, oy, oz = grid._chunk_origin(cx, cy, cz)
        halo = np.zeros((shape[0] + 2, shape[1] + 2, shape[2] + 2), dtype=arr.dtype)
        halo[1:1 + shape[0], 1:1 + shape[1], 1:1 + shape[2]] = arr
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx == dy == dz == 0:
                        continue
                    narr = grid._chunks.get((cx + dx, cy + dy, cz + dz))
                    if narr is None:
                        continue
                    nshape = grid._chunk_shape(cx + dx, cy + dy, cz + dz)
                    nox, noy, noz = grid._chunk_origin(cx + dx, cy + dy, cz + dz)
                    # overlap per axis between [o-1, o+s] and [no, no+ns)
                    slices_dst: list[slice] = []
                    slices_src: list[slice] = []
                    ok = True
                    for (o, s, no, ns) in ((ox, shape[0], nox, nshape[0]),
                                           (oy, shape[1], noy, nshape[1]),
                                           (oz, shape[2], noz, nshape[2])):
                        # halo covers global [o-1, o+s] inclusive
                        lo = max(o - 1, no)
                        hi = min(o + s, no + ns - 1)  # inclusive
                        if lo > hi:
                            ok = False
                            break
                        slices_dst.append(slice(lo - (o - 1), hi - (o - 1) + 1))
                        slices_src.append(slice(lo - no, hi - no + 1))
                    if ok:
                        halo[tuple(slices_dst)] = narr[tuple(slices_src)]
        yield (cx, cy, cz), arr, halo, shape


def _region_mask(shape: tuple[int, int, int], origin: tuple[int, int, int],
                 lo: tuple[int, int, int] | list[int],
                 hi: tuple[int, int, int] | list[int]) -> np.ndarray:
    """Boolean mask over a chunk-local array selecting global region [lo, hi]."""
    xs = np.arange(origin[0], origin[0] + shape[0])
    ys = np.arange(origin[1], origin[1] + shape[1])
    zs = np.arange(origin[2], origin[2] + shape[2])
    mx = (xs >= lo[0]) & (xs <= hi[0])
    my = (ys >= lo[1]) & (ys <= hi[1])
    mz = (zs >= lo[2]) & (zs <= hi[2])
    return (mx[:, None, None] & my[None, :, None] & mz[None, None, :])


# ---- paint gradient ----------------------------------------------------

def paint_gradient(grid: Grid, frm: tuple[int, int, int], to: tuple[int, int, int],
                   blocks: list[str], *, axis: str = "y",
                   blend: float = 0.0, seed: int = 0) -> int:
    """Paint a linear gradient of blocks along an axis across a region.

    ``blocks`` is a list of blockstate strings interpolated from ``frm`` to
    ``to``. The gradient runs along ``axis`` (``"x"``, ``"y"``, or ``"z"``).
    ``blend`` in [0, 1] adds perlin-like noise jitter to the gradient boundary
    for organic transitions (0.0 = sharp, 1.0 = very noisy).

    Only paints existing *solid* voxels (like ``paint`` / ``intersect``).
    On chunked grids this streams chunk-by-chunk without materialising a
    dense copy. Returns the number of voxels painted.
    """
    if not blocks:
        raise ValueError("blocks list cannot be empty")
    if axis not in ("x", "y", "z"):
        raise ValueError(f"axis must be x, y, or z, got {axis}")
    ax_idx = {"x": 0, "y": 1, "z": 2}[axis]
    x0, y0, z0 = frm
    x1, y1, z1 = to
    lo = [min(x0, x1), min(y0, y1), min(z0, z1)]
    hi = [max(x0, x1), max(y0, y1), max(z0, z1)]
    gs = grid.shape
    lo = [max(lo[i], 0) for i in range(3)]
    hi = [min(hi[i], gs[i] - 1) for i in range(3)]
    if any(lo[i] > hi[i] for i in range(3)):
        return 0

    palette_indices = [grid.palette.add(Block.parse(b)) for b in blocks]
    lut = np.array(palette_indices, dtype=np.uint16)
    n_blocks = len(blocks)

    ax_len = hi[ax_idx] - lo[ax_idx] + 1
    ax_coords = np.arange(ax_len, dtype=np.float32)
    ax_span = max(ax_len - 1, 1)
    t = np.clip(ax_coords / ax_span, 0.0, 1.0)
    if blend > 0:
        rng = np.random.default_rng(seed)
        jitter = rng.uniform(-blend, blend, size=ax_len).astype(np.float32)
        t = np.clip(t + jitter, 0.0, 1.0)
    block_idx = np.clip(np.rint(t * (n_blocks - 1)).astype(np.int32), 0, n_blocks - 1)

    if isinstance(grid, ChunkedGrid):
        changed = 0
        for (cx, cy, cz), arr, _halo, shape in _iter_halo_chunks(grid):
            origin = grid._chunk_origin(cx, cy, cz)
            idx_grid = np.zeros(shape, dtype=np.int32)
            for a in range(shape[ax_idx]):
                g = origin[ax_idx] + a
                val = block_idx[g - lo[ax_idx]] if lo[ax_idx] <= g <= hi[ax_idx] else -1
                if ax_idx == 0:
                    idx_grid[a, :, :] = val
                elif ax_idx == 1:
                    idx_grid[:, a, :] = val
                else:
                    idx_grid[:, :, a] = val
            valid = idx_grid >= 0
            valid &= _region_mask(shape, origin, lo, hi)  # clip y/z extents too
            solid = arr != 0
            sel = valid & solid
            if sel.any():
                new_vals = lut[idx_grid[sel]]
                arr[sel] = new_vals
                changed += int(np.count_nonzero(sel))
        return changed

    region_shape = (hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, hi[2] - lo[2] + 1)
    if ax_idx == 0:
        idx_grid = np.broadcast_to(block_idx[:, None, None], region_shape)
    elif ax_idx == 1:
        idx_grid = np.broadcast_to(block_idx[None, :, None], region_shape)
    else:
        idx_grid = np.broadcast_to(block_idx[None, None, :], region_shape)
    new_vals = lut[idx_grid]
    dense = _dense_data(grid)
    region = dense[lo[0]:hi[0] + 1, lo[1]:hi[1] + 1, lo[2]:hi[2] + 1]
    solid = region != 0
    count = int(np.count_nonzero(solid))
    if count == 0:
        return 0
    region[solid] = new_vals[solid]
    return count


# ---- edge wear -----------------------------------------------------------

def edge_wear(grid: Grid, blocks: list[str], *,
              min_exposure: int = 1, max_exposure: int = 6,
              noise: float = 0.0, seed: int = 0) -> int:
    """Apply weathering blocks to exposed surfaces.

    Solid voxels with between ``min_exposure`` and ``max_exposure`` air
    face-neighbours are repainted from ``blocks``; more exposed voxels map to
    earlier (more weathered) entries. ``noise`` in [0, 1] randomly skips
    voxels for patchy wear. Returns the number of voxels weathered.
    """
    if not blocks:
        raise ValueError("blocks list cannot be empty")
    if min_exposure < 1 or max_exposure < 1:
        raise ValueError("exposure must be >= 1")
    if min_exposure > max_exposure:
        raise ValueError("min_exposure cannot exceed max_exposure")

    if isinstance(grid, ChunkedGrid):
        rng = np.random.default_rng(seed) if noise > 0 else None
        changed = 0
        palette_indices = np.array(
            [grid.palette.add(Block.parse(b)) for b in blocks], dtype=np.uint16)
        n = len(blocks)
        span = max(max_exposure - min_exposure, 1)
        for _key, arr, halo, _shape in _iter_halo_chunks(grid):
            core = halo[1:-1, 1:-1, 1:-1]
            solid = core != 0
            exposed = solid.copy()
            cnt = _air_count_uint16(halo)[1:-1, 1:-1, 1:-1]
            exposed &= (cnt >= min_exposure) & (cnt <= max_exposure)
            if rng is not None:
                exposed &= ~(rng.random(core.shape) < noise)
            if not exposed.any():
                continue
            t = 1.0 - (cnt[exposed].astype(np.float32) - min_exposure) / span
            idx = np.clip((np.clip(t, 0, 1) * (n - 1)).astype(np.int32), 0, n - 1)
            arr[exposed] = palette_indices[idx]
            changed += int(np.count_nonzero(exposed))
        return changed

    dense = _dense_data(grid)
    solid = dense != 0
    air_count = _air_neighbour_count(dense)
    exposed = solid & (air_count >= min_exposure) & (air_count <= max_exposure)
    if noise > 0:
        rng = np.random.default_rng(seed)
        skip = rng.random(dense.shape) < noise
        exposed = exposed & ~skip
    if not exposed.any():
        return 0
    n = len(blocks)
    span = max(max_exposure - min_exposure, 1)
    exposed_counts = air_count[exposed]
    t = 1.0 - (exposed_counts.astype(np.float32) - min_exposure) / span
    t = np.clip(t, 0.0, 1.0)
    block_indices = (t * (n - 1)).astype(np.int32)
    block_indices = np.clip(block_indices, 0, n - 1)
    palette_indices = np.array(
        [grid.palette.add(Block.parse(b)) for b in blocks], dtype=np.uint16
    )
    new_vals = palette_indices[block_indices]
    dense[exposed] = new_vals
    return int(np.count_nonzero(exposed))


def _air_count_uint16(arr: np.ndarray) -> np.ndarray:
    return _air_neighbour_count(np.asarray(arr, dtype=np.uint16))


# ---- surface scatter ------------------------------------------------------

def surface_scatter(grid: Grid, block: str, *,
                    density: float = 0.1, min_exposure: int = 1,
                    max_exposure: int = 6, seed: int = 0,
                    on_blocks: list[str] | None = None) -> int:
    """Scatter a block on exposed surfaces with probabilistic density.

    Each solid voxel with between ``min_exposure`` and ``max_exposure`` air
    face-neighbours has a ``density`` probability of being repainted with
    ``block``. ``on_blocks`` restricts to voxels currently holding one of
    those blocks. Returns the number of voxels scattered.
    """
    if density <= 0:
        return 0
    rng = np.random.default_rng(seed)
    new_idx = grid.palette.add(Block.parse(block))

    allowed_names = set()
    if on_blocks:
        allowed_names = {Block.parse(n).name for n in on_blocks}
    allowed_idx: set[int] = set()
    if allowed_names:
        pal = grid.palette.blocks()
        for i, b in enumerate(pal):
            if b.name in allowed_names:
                allowed_idx.add(i)

    if isinstance(grid, ChunkedGrid):
        changed = 0
        for _key, arr, halo, _shape in _iter_halo_chunks(grid):
            core = halo[1:-1, 1:-1, 1:-1]
            cnt = _air_count_uint16(halo)[1:-1, 1:-1, 1:-1]
            exposed = (core != 0) & (cnt >= min_exposure) & (cnt <= max_exposure)
            if allowed_idx:
                mask_allowed = np.isin(core, list(allowed_idx))
                exposed &= mask_allowed
            if not exposed.any():
                continue
            sel = exposed & (rng.random(core.shape) < density)
            if sel.any():
                arr[sel] = new_idx
                changed += int(np.count_nonzero(sel))
        return changed

    dense = _dense_data(grid)
    solid = dense != 0
    air_count = _air_neighbour_count(dense)
    exposed = solid & (air_count >= min_exposure) & (air_count <= max_exposure)
    if allowed_idx:
        exposed &= np.isin(dense, list(allowed_idx))
    if not exposed.any():
        return 0
    selected = exposed & (rng.random(dense.shape) < density)
    if not selected.any():
        return 0
    dense[selected] = new_idx
    return int(np.count_nonzero(selected))
