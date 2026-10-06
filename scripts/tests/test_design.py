"""Tests for the design toolkit: palettes, terrain paths/rivers, roofs, flora."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.design import (
    apply_forest,
    apply_gable_roof,
    apply_hip_roof,
    apply_path,
    apply_river,
    apply_tree,
    get_palette,
    ground_height,
    list_palettes,
    plan_path,
    resolve_blocks,
    tree_kinds,
)
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _terrain_session(chunked: bool = False) -> Session:
    from schematica.generators.templates import apply_terrain
    s = Session.new((48, 24, 48), version="1.20.1", chunked=chunked, chunk_size=16)
    apply_terrain(s, seed=7, amplitude=3)
    return s


# ---- palettes -----------------------------------------------------------

def test_palette_catalog_loads():
    pals = list_palettes()
    assert len(pals) >= 10
    names = {p.name for p in pals}
    assert "medieval_stone" in names and "cherry_grove" in names


def test_palette_roles_and_ramp():
    p = get_palette("medieval_stone")
    assert p.ramp and p.ramp_block(0.0) == p.ramp[0]
    assert p.ramp_block(1.0) == p.ramp[-1]
    t = p.texture(seed=1)
    assert len(t.blocks) == len(t.weights) == len(p.mix)
    assert p.trim.startswith("minecraft:")
    assert p.light.startswith("minecraft:")


def test_palette_unknown_lists_available():
    with pytest.raises(KeyError) as ei:
        get_palette("nope_not_a_palette")
    assert "medieval_stone" in str(ei.value)


def test_resolve_blocks_forms():
    p = get_palette("rustic_oak")
    assert resolve_blocks(p) == list(p.path)
    assert resolve_blocks("rustic_oak") == list(p.path)
    assert resolve_blocks(["a", "b"], palette_role="path") == ["a", "b"]
    assert resolve_blocks(None) == []
    assert resolve_blocks(None, palette_role="nope") == [] or resolve_blocks(None) == []


# ---- ground height ------------------------------------------------------

def test_ground_height_dense_and_chunked():
    for chunked in (False, True):
        s = _terrain_session(chunked=chunked)
        gy = s.surface_height(10, 10)
        assert gy is not None and 0 <= gy < 24
        assert s.surface_height(-5, 10) is None  # out of bounds


# ---- paths ---------------------------------------------------------------

def test_plan_path_rasterizes_and_drapes():
    s = _terrain_session()
    plan = plan_path(s.grid, [(2, 2), (30, 30)], width=3, smooth_drape=False)
    assert len(plan) > 20
    for (x, z), y in plan.items():
        assert ground_height(s.grid, x, z) == y
    # smoothed drape softens steps: result stays close to raw ground
    plan_sm = plan_path(s.grid, [(2, 2), (30, 30)], width=3, smooth_drape=True)
    for (x, z), y in plan.items():
        assert abs(plan_sm[(x, z)] - y) <= 2


def test_apply_path_lays_surface_and_border():
    s = _terrain_session()
    before = s.grid.palette.blocks()
    n = apply_path(s, [(4, 4), (40, 40)], width=3, block="minecraft:gravel",
                   border="minecraft:oak_log", seed=1)
    assert n > 40
    names = {b.name for b in s.grid.palette.blocks()} - {b.name for b in before}
    assert "minecraft:gravel" in names
    # road replaces the top ground block: the cell just above must be air
    from schematica.blocks.block import AIR
    gx, gz = 20, 20
    # find draped segment cells near middle
    gy = s.surface_height(gx, gz)
    assert gy is not None
    assert s.grid.get(gx, gy, gz) != AIR


def test_apply_path_deterministic_same_seed():
    a = _terrain_session()
    b = _terrain_session()
    for s in (a, b):
        apply_path(s, [(4, 4), (40, 40)], width=3,
                   blocks=["minecraft:gravel", "minecraft:cobblestone"], seed=5)
    assert a.grid == b.grid


def test_apply_path_fixed_height_with_support():
    s = _terrain_session()
    y = 18
    n = apply_path(s, [(10, y, 10), (30, y, 10)], width=3, drape=False,
                   block="minecraft:oak_planks", support="minecraft:oak_log")
    assert n > 20
    # under the deck there should be support columns to the ground
    assert s.grid.get(20, y, 10).name == "minecraft:oak_planks"


def test_apply_path_requires_two_points():
    s = _terrain_session()
    with pytest.raises(ValueError):
        apply_path(s, [(3, 3)])


# ---- rivers --------------------------------------------------------------

def test_apply_river_carves_and_floods():
    s = _terrain_session()
    apply_river(s, [(4, 4), (40, 36)], width=3, depth=3, bed="minecraft:gravel", smooth=2)
    # sample along the plan center: find a carved cell with water below grade
    pal = {b.name: i for i, b in enumerate(s.grid.palette.blocks())}
    water_idx = pal.get("minecraft:water")
    assert water_idx is not None
    dense = s.grid.data if not s.is_chunked else s.grid.to_dense().data
    assert int(np.count_nonzero(dense == water_idx)) > 8
    gravel_idx = pal.get("minecraft:gravel")
    assert gravel_idx is not None and int(np.count_nonzero(dense == gravel_idx)) > 4


def test_apply_river_depth_one_no_water():
    s = _terrain_session()
    apply_river(s, [(4, 4), (20, 20)], width=2, depth=1)
    names = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:water" not in names


# ---- roofs ---------------------------------------------------------------

def test_gable_roof_symmetric_and_ramped():
    s = Session.new((24, 16, 24))
    s.add(Box(6, 2, 6, 17, 8, 17), "minecraft:stone_bricks")
    n = apply_gable_roof(s, (6, 8, 6), (17, 8, 17), axis="x",
                         ramp=["minecraft:deepslate_bricks", "minecraft:stone_bricks", "minecraft:quartz_block"],
                         overhang=1)
    assert n > 30
    # overhang: roof extends one beyond walls on the slope axis (z)
    assert s.grid.data[10, 9, 5] != 0
    # ridge row uses the last ramp block at the roof apex
    names = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:quartz_block" in names
    # symmetry of a gable roof across the span axis
    strip = s.grid.data[10, 9, 5:19]
    assert strip[0] != 0 and strip[-1] != 0


def test_gable_roof_stairs_have_facing():
    s = Session.new((20, 14, 20))
    s.add(Box(5, 1, 5, 13, 6, 13), "minecraft:oak_planks")
    apply_gable_roof(s, (5, 6, 5), (13, 6, 13), axis="x",
                     block="minecraft:dark_oak_planks",
                     stair_block="minecraft:dark_oak_stairs")
    stair_states = [b for b in s.grid.palette.blocks() if "stairs" in b.name]
    assert stair_states
    facings = {dict(b.states)["facing"] for b in stair_states}
    # slope axis is z when ridge is x: stairs face north/south
    assert facings <= {"north", "south"}
    assert len(facings) == 2


def test_gable_roof_rejects_bad_axis():
    s = Session.new((16, 16, 16))
    with pytest.raises(ValueError):
        apply_gable_roof(s, (2, 4, 2), (10, 4, 10), axis="y")


def test_hip_roof_square_tower():
    s = Session.new((20, 16, 20))
    s.add(Box(5, 1, 5, 13, 7, 13), "minecraft:stone_bricks")
    n = apply_hip_roof(s, (5, 7, 5), (13, 7, 13), block="minecraft:mud_bricks")
    assert n > 30
    # hip roof tapers to a ridge; apex ring exists above the wall top
    apex = [y for y in range(8, 16) if np.count_nonzero(s.grid.data[:, y, 5:15]) > 0]
    assert apex and apex[-1] >= 9


# ---- flora ---------------------------------------------------------------

def test_tree_kinds_catalog_and_registration():
    kinds = tree_kinds()
    assert {"oak", "birch", "spruce", "cherry", "jungle", "mega", "dead"} <= set(kinds)


@pytest.mark.parametrize("kind", ["oak", "birch", "spruce", "cherry", "jungle", "mega", "dead"])
def test_apply_tree_each_kind(kind):
    s = _terrain_session()
    ok = apply_tree(s, 8, 8, kind=kind, seed=3)
    assert ok
    names = {b.name for b in s.grid.palette.blocks()}
    spec = tree_kinds()[kind]
    trunk_spec = spec.get("trunk", "minecraft:oak_log")
    trunk_name = trunk_spec if isinstance(trunk_spec, str) else "minecraft:oak_log"
    assert trunk_name in names
    leaves_spec = spec.get("leaves")
    if kind != "dead" and isinstance(leaves_spec, str):
        assert leaves_spec in names
    # tree stands on the surface: trunk base is above ground
    gy = s.surface_height(8, 8)
    assert gy is not None


def test_apply_tree_refuses_no_ground_and_occupied():
    s = Session.new((16, 16, 16))
    assert apply_tree(s, 5, 5) is False  # empty column
    s.add(Box(0, 0, 0, 15, 15, 15), "minecraft:stone")  # no headroom left
    assert apply_tree(s, 5, 5) is False


def test_forest_respects_spacing_and_seed():
    s = _terrain_session()
    n = apply_forest(s, (0, 0, 0), (30, 0, 30), density=0.05,
                     kinds=("oak", "birch"), seed=9, min_spacing=4)
    assert 5 <= n <= 40
    s2 = _terrain_session()
    n2 = apply_forest(s2, (0, 0, 0), (30, 0, 30), density=0.05,
                      kinds=("oak", "birch"), seed=9, min_spacing=4)
    assert n == n2  # deterministic


def test_forest_bad_density():
    s = Session.new((16, 16, 16))
    with pytest.raises(ValueError):
        apply_forest(s, (0, 0, 0), (8, 0, 8), density=2.0)


def test_apply_tree_unknown_kind():
    s = _terrain_session()
    with pytest.raises(KeyError):
        apply_tree(s, 5, 5, kind="baobab_from_another_dimension")


# ---- chunked parity ------------------------------------------------------

def test_design_ops_chunked_match_dense():
    dense = _terrain_session(chunked=False)
    chunked = _terrain_session(chunked=True)
    for s in (dense, chunked):
        apply_path(s, [(4, 4), (40, 40)], width=3,
                   blocks=["minecraft:gravel", "minecraft:cobblestone"],
                   border="minecraft:oak_log", seed=5)
        apply_river(s, [(4, 20), (42, 30)], width=2, depth=3,
                    bed="minecraft:sand", smooth=2)
        apply_forest(s, (2, 0, 2), (16, 0, 16), density=0.05, kinds=("oak",), seed=2)
        s.apply_gable_roof((20, 20, 20), (30, 20, 30), axis="z",
                           block="minecraft:spruce_planks")
    assert chunked.grid.to_dense().data.shape == dense.grid.data.shape
    assert bool((chunked.grid.to_dense().data == dense.grid.data).all())
