"""Vegetation: layered trees and seeded forests with ground snap.

Tree kinds live in ``design_palettes.json`` under the ``trees`` key so new
species can be added by editing data, not code. Unlike the minimal
``apply_tree`` template these snap to the terrain surface, vary trunk height
and canopy radius per tree (seeded), and avoid double-planting with a minimum
spacing pass.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ..blocks.block import Block
from ..resources import load_json_resource
from ..shapes.primitives import Box, Cone, Sphere
from .paths import ground_height

if TYPE_CHECKING:
    from ..session.session import Session

_DEFAULT_TREES: dict[str, dict[str, object]] = {
    "oak": {"trunk": "minecraft:oak_log", "leaves": "minecraft:oak_leaves",
            "height": [5, 8], "canopy": "sphere", "canopy_r": [2, 3]},
    "birch": {"trunk": "minecraft:birch_log", "leaves": "minecraft:birch_leaves",
              "height": [6, 9], "canopy": "sphere", "canopy_r": [2, 3]},
    "spruce": {"trunk": "minecraft:spruce_log", "leaves": "minecraft:spruce_leaves",
               "height": [7, 12], "canopy": "stacked", "canopy_r": [3, 4]},
    "cherry": {"trunk": "minecraft:cherry_log", "leaves": "minecraft:cherry_leaves",
               "height": [5, 8], "canopy": "sphere", "canopy_r": [3, 4]},
    "jungle": {"trunk": "minecraft:jungle_log", "leaves": "minecraft:jungle_leaves",
               "height": [8, 14], "canopy": "sphere", "canopy_r": [3, 5]},
    "mega": {"trunk": "minecraft:spruce_log", "leaves": "minecraft:spruce_leaves",
             "height": [12, 18], "canopy": "sphere", "canopy_r": [4, 6], "trunk_w": 2},
    "dead": {"trunk": "minecraft:spruce_log", "leaves": None,
             "height": [4, 7], "canopy": "none", "canopy_r": [0, 0]},
}


def tree_kinds() -> dict[str, dict[str, object]]:
    """Tree kind table: ``data/design_palettes.json`` trees + built-in defaults."""
    out = {k: dict(v) for k, v in _DEFAULT_TREES.items()}
    try:
        raw = load_json_resource("design_palettes.json", env_var="SCHEMATICA_PALETTES")
        for k, v in raw.get("trees", {}).items():
            merged = dict(out.get(k, {}))
            merged.update(v)
            out[k] = merged
    except Exception:
        pass
    return out


def _tree_int_pair(spec: dict[str, object], key: str, default: list[int]) -> tuple[int, int]:
    v = spec.get(key, default)
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return int(v[0]), int(v[1])
    return default[0], default[1]


def _tree_str(spec: dict[str, object], key: str, default: str | None) -> str | None:
    v = spec.get(key, default)
    return v if isinstance(v, str) or v is None else default


def apply_tree(session: Session, x: int, z: int, *, kind: str = "oak",
               height: int | None = None, seed: int = 0,
               canopy: str | None = None, trunk: str | None = None,
               leaves: str | None = None) -> bool:
    """Plant one tree of ``kind`` with its base on the terrain surface.

    Returns False when there is no ground at (x, z) or the column is occupied
    (solid block at the planting level), so forests never overwrite builds.
    """
    kinds = tree_kinds()
    if kind not in kinds:
        raise KeyError(f"unknown tree kind '{kind}'; available: {', '.join(sorted(kinds))}")
    spec = kinds[kind]
    gy = ground_height(session.grid, x, z)
    if gy is None:
        return False
    sx, sy, sz = session.grid.shape
    base = gy + 1
    if base >= sy - 2:
        return False
    if session.grid.get(x, base, z) != Block.parse("minecraft:air"):
        return False
    rng = np.random.default_rng((seed, x * 1009 + z) if seed else (x * 9176 + z * 3 + 11))
    h_lo, h_hi = _tree_int_pair(spec, "height", [5, 8])
    h = height or int(rng.integers(h_lo, h_hi + 1))
    trunk_block = trunk or _tree_str(spec, "trunk", "minecraft:oak_log") or "minecraft:oak_log"
    leaves_block = leaves if leaves is not None else _tree_str(spec, "leaves", None)
    canopy_mode = canopy or _tree_str(spec, "canopy", "sphere") or "sphere"
    tw_raw = spec.get("trunk_w", 1)
    tw = tw_raw if isinstance(tw_raw, int) and not isinstance(tw_raw, bool) else 1
    top = base + h
    if top + 2 >= sy:
        h = max(3, sy - 3 - base)
        top = base + h
    for dx in range(tw):
        for dz in range(tw):
            session.add(Box(x + dx, base, z + dz, x + dx, top - 1, z + dz), trunk_block)
    if canopy_mode != "none" and leaves_block:
        r_lo, r_hi = _tree_int_pair(spec, "canopy_r", [2, 3])
        r = float(rng.uniform(r_lo, r_hi))
        cx, cz = x + (tw - 1) / 2, z + (tw - 1) / 2
        if canopy_mode == "sphere":
            session.add(Sphere(cx, top, cz, r, hollow=False), leaves_block)
        elif canopy_mode == "cone":
            session.add(Cone(cx, cz, r, top - 1, top + int(r) + 2), leaves_block)
        elif canopy_mode == "stacked":
            rr = r
            for i, frac in enumerate((1.0, 0.75, 0.5)):
                layer_r = max(rr * frac, 1.2)
                y0 = top - 2 - int(i * (h * 0.28))
                session.add(Cone(cx, cz, layer_r, y0, min(y0 + 3, top)), leaves_block)
        # keep the trunk tip poking through the canopy
        for dx in range(tw):
            for dz in range(tw):
                if top < sy:
                    session.grid.set(x + dx, top, z + dz, Block.parse(trunk_block))
    return True


def apply_forest(session: Session, frm: tuple[int, int, int],
                 to: tuple[int, int, int], *, density: float = 0.02,
                 kinds: tuple[str, ...] = ("oak",), seed: int = 0,
                 min_spacing: int = 3) -> int:
    """Seed a forest inside the given footprint.

    ``density`` is trees per XZ cell (0.02 ~= 1 tree per 50 cells). Cells are
    drawn in seeded order and accepted only when no accepted tree is within
    ``min_spacing`` cells (Chebyshev), preventing canopies from merging.
    Returns the number of trees planted.
    """
    if not (0 < density <= 1):
        raise ValueError("density must be in (0, 1]")
    x0, x1 = sorted((frm[0], to[0]))
    z0, z1 = sorted((frm[2], to[2]))
    area = (x1 - x0 + 1) * (z1 - z0 + 1)
    target = max(int(area * density), 1)
    rng = np.random.default_rng(seed)
    cells = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    keys = rng.random(len(cells))
    order = np.argsort(keys)
    accepted: list[tuple[int, int]] = []
    planted = 0
    for i in order:
        if planted >= target:
            break
        x, z = cells[int(i)]
        if any(abs(x - ax) <= min_spacing and abs(z - az) <= min_spacing
               for ax, az in accepted):
            continue
        kind = kinds[int(rng.integers(0, len(kinds)))]
        if apply_tree(session, x, z, kind=kind, seed=int(rng.integers(1, 1 << 30))):
            accepted.append((x, z))
            planted += 1
    return planted
