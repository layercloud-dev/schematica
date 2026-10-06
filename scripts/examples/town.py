"""Mini-town showcase of the Phase 14 design toolkit.

Run from scripts/ (or with it installed):

    python examples/town.py [out_dir]

Builds: terrain, draped road + bridge-crossing river, a gable-roofed house,
a hip-roofed watchtower, a palette gradient on the tower, a spaced forest,
weathering + scatter, then previews and a Sponge export.
"""
from __future__ import annotations

import sys
from pathlib import Path

from schematica.design import (
    apply_forest,
    apply_gable_roof,
    apply_hip_roof,
    apply_path,
    apply_river,
)
from schematica.export.sponge import write_sponge
from schematica.generators.templates import apply_terrain
from schematica.render.preview import preview
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def main(out_dir: str = "town_out") -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    s = Session.new((80, 32, 80), version="1.20.1")
    apply_terrain(s, seed=11, amplitude=5)

    # Road network: main street + side street, kerbed, mix of gravel/cobble.
    apply_path(s, [(4, 8), (36, 20), (76, 70)], width=3,
               blocks=["minecraft:gravel", "minecraft:cobblestone"],
               border="minecraft:oak_log", smooth=4, seed=2)
    apply_path(s, [(36, 20), (40, 60)], width=2, block="minecraft:coarse_dirt",
               smooth=3, seed=5)

    # River crossing the map with a gravel bed.
    apply_river(s, [(2, 60), (30, 50), (60, 66), (78, 58)], width=3, depth=3,
                bed="minecraft:gravel", smooth=4)

    # House: stone-brick shell + medieval gable roof with stair courses.
    s.add(Box(28, 12, 26, 38, 20, 36), "minecraft:stone_bricks", hollow=True)
    # carve door
    s.subtract(Box(32, 13, 26, 33, 15, 26))
    apply_gable_roof(s, (28, 20, 26), (38, 20, 36), axis="x",
                     palette="medieval_stone", overhang=1,
                     stair_block="minecraft:stone_brick_stairs")

    # Watchtower with hip roof + vertical palette gradient on its walls.
    s.add(Box(50, 12, 20, 56, 26, 26), "minecraft:deepslate_bricks", hollow=True)
    s.paint_palette_gradient((50, 12, 20), (56, 26, 26), "deepslate_dungeon",
                             axis="y", blend=0.2, seed=7)
    apply_hip_roof(s, (50, 26, 20), (56, 26, 26), ramp=[
        "minecraft:deepslate_tiles", "minecraft:polished_deepslate",
    ], overhang=1)

    # Vegetation: mixed forest in the south-west quadrant.
    planted = apply_forest(s, (2, 0, 2), (24, 0, 24), density=0.06,
                           kinds=("oak", "birch"), seed=4, min_spacing=4)

    # Weathering passes: edges pick up mossy/cracked wear, moss scatter.
    s.edge_wear(["minecraft:mossy_stone_bricks", "minecraft:cobblestone",
                 "minecraft:stone_bricks"], min_exposure=3, max_exposure=6,
                noise=0.3, seed=12)
    s.surface_scatter("minecraft:moss_carpet", density=0.06, min_exposure=1,
                      max_exposure=6, seed=8, on_blocks=["minecraft:grass_block"])

    # 80^3 maps exceed the comfortable 3D-voxel render size; projected
    # previews are the intended, fast path for maps at this scale.
    paths = preview(s.grid, out / "previews", max_voxels=48 ** 3, max_dim=192)
    schem = write_sponge(s.grid, out / "town.schem")
    print(f"b town: {s.stats()}, trees={planted}")
    for p in paths:
        print("  preview:", p)
    print("  schematic:", schem)
    return schem


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "town_out")
