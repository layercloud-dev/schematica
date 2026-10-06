"""Perlin/simplex noise helpers (via the `noise` package)."""
from __future__ import annotations

import numpy as np


def perlin2d(shape: tuple[int, int], scale: float = 0.05, octaves: int = 4,
             persistence: float = 0.5, lacunarity: float = 2.0,
             seed: int = 0) -> np.ndarray:
    try:
        from noise import snoise2
    except ImportError as e:
        raise RuntimeError("install the 'noise' package") from e
    w, h = shape
    out = np.zeros((w, h), dtype=np.float32)
    for x in range(w):
        for y in range(h):
            out[x, y] = snoise2(x * scale, y * scale, octaves=octaves,
                                persistence=persistence, lacunarity=lacunarity,
                                repeatx=1024, repeaty=1024, base=seed)
    # normalize to [0,1]
    out = (out - out.min()) / (out.max() - out.min() + 1e-9)
    return out


def fbm2d(shape: tuple[int, int], scale: float = 0.05, octaves: int = 4,
          seed: int = 0) -> np.ndarray:
    return perlin2d(shape, scale=scale, octaves=octaves, seed=seed)



def perlin3d(shape: tuple[int, int, int], scale: float = 0.08, octaves: int = 3,
             persistence: float = 0.5, lacunarity: float = 2.0,
             seed: int = 0) -> np.ndarray:
    """3D Perlin (simplex) field normalized to [0, 1].

    The bundled simplex implementation has no seed parameter, so ``seed``
    shifts the sampling window deterministically. Note the evaluation loop
    is per-voxel: budget ~1-2 s per million cells.
    """
    import noise as _noise

    ox = (abs(seed) * 73_856_093) % 4096 * 0.6180339887
    oy = (abs(seed) * 19_349_663) % 4096 * 0.4142135624
    oz = (abs(seed) * 83_492_791) % 4096 * 0.7320508076
    out = np.zeros(shape, dtype=np.float64)
    for z in range(shape[2]):
        for y in range(shape[1]):
            for x in range(shape[0]):
                out[x, y, z] = _noise.snoise3(
                    ox + x * scale, oy + y * scale, oz + z * scale,
                    octaves=int(octaves), persistence=float(persistence),
                    lacunarity=float(lacunarity),
                )
    lo, hi = float(out.min()), float(out.max())
    span = max(hi - lo, 1e-9)
    return (out - lo) / span
