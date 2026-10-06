"""Tests for Phase 15 tools: patterns, layout, buildings, decay, light, caves."""
from __future__ import annotations

import numpy as np
import pytest

from schematica.blocks.block import Block
from schematica.design import (
    ground_height,
    mst_edges,
)
from schematica.generators.templates import apply_terrain
from schematica.patterns import cumulative, is_weighted_pattern, parse_pattern
from schematica.session.session import Session
from schematica.shapes.primitives import Box


def _terrain() -> Session:
    s = Session.new((64, 28, 64))
    apply_terrain(s, seed=5, amplitude=4)
    return s


# ---- patterns ------------------------------------------------------------

def test_parse_pattern_forms():
    assert parse_pattern("stone") == [("stone", 1.0)]
    p = parse_pattern("3x stone_bricks, 25%mossy_cobblestone, oak_log[axis=y]")
    assert p[0] == ("stone_bricks", 3.0)
    assert p[1][1] == 25.0
    assert p[2][0] == "oak_log[axis=y]"
    assert parse_pattern(["a", "b"]) == [("a", 1.0), ("b", 1.0)]
    assert is_weighted_pattern("3x stone") and not is_weighted_pattern("stone|grass")


def test_parse_pattern_rejects_bad():
    with pytest.raises(ValueError):
        parse_pattern("")
    with pytest.raises(ValueError):
        parse_pattern("0%stone, dirt")
    with pytest.raises(ValueError):
        parse_pattern("3x")  # weight without block


def test_cumulative_relative_weights():
    assert cumulative(parse_pattern("5%dirt,15%stone")) == [0.25, 1.0]
    with pytest.raises(ValueError):
        cumulative([("a", 0.0)])


def test_replace_weighted_dense_and_chunked_and_undo():
    for chunked in (False, True):
        s = Session.new((16, 8, 16), chunked=chunked, chunk_size=8)
        s.add(Box(0, 0, 0, 15, 7, 15), "minecraft:stone")
        n = s.replace_weighted("minecraft:stone",
                               "75%stone_bricks, 25%mossy_cobblestone", seed=42)
        assert n == 16 * 8 * 16
        names = {b.name for b in s.grid.palette.blocks()}
        assert "minecraft:stone_bricks" in names
        assert "minecraft:mossy_cobblestone" in names
        # seeded determinism
        s.undo()
        n2 = s.replace_weighted("minecraft:stone",
                                "75%stone_bricks, 25%mossy_cobblestone", seed=42)
        assert n2 == n
        dense = s.grid.to_dense().data if s.is_chunked else s.grid.data
        # rough ratio sanity: at least one of each, mostly bricks
        pal = s.grid.palette.blocks()
        idx = {b.name: i for i, b in enumerate(pal)}
        c_brick = int(np.count_nonzero(dense == idx["minecraft:stone_bricks"]))
        c_moss = int(np.count_nonzero(dense == idx["minecraft:mossy_cobblestone"]))
        assert c_brick > c_moss > 0


def test_replace_weighted_missing_src():
    s = Session.new((8, 8, 8))
    assert s.replace_weighted("minecraft:stone", "stone") == 0


# ---- layout ---------------------------------------------------------------

def test_flatten_median_pad():
    s = _terrain()
    n = s.apply_flatten((8, 0, 8), (30, 0, 30), cap="minecraft:grass_block")
    assert n > 0
    ys = {ground_height(s.grid, x, z) for x in range(8, 31) for z in range(8, 31, 7)}
    assert len(ys) == 1
    y = ys.pop()
    assert s.grid.get(12, y, 12).name == "minecraft:grass_block"


def test_flatten_chunked_parity():
    d = _terrain()
    c = Session.new((64, 28, 64), chunked=True, chunk_size=16)
    apply_terrain(c, seed=5, amplitude=4)
    d.apply_flatten((8, 0, 8), (30, 0, 30), cap="minecraft:grass_block")
    c.apply_flatten((8, 0, 8), (30, 0, 30), cap="minecraft:grass_block")
    assert (d.grid.data == c.grid.to_dense().data).all()


def test_plaza_bands_border_fountain():
    s = _terrain()
    n = s.apply_plaza((28, 28), 8, palette="medieval_stone", fountain=True)
    assert n > 50
    pad_y = ground_height(s.grid, 28, 28)
    assert pad_y is not None
    # center fountain pillar + light present above pad
    names = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:lantern" in names
    assert "minecraft:water" in names


def test_plaza_rejects_tiny_radius():
    s = Session.new((32, 16, 32))
    with pytest.raises(ValueError):
        s.apply_plaza((16, 16), 2)


def test_mst_edges_square_no_redundancy():
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    edges = mst_edges(pts)
    assert len(edges) == len(pts) - 1
    # all points connected
    adj: dict[int, set[int]] = {}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    seen = set()
    stack = [0]
    while stack:
        i = stack.pop()
        seen.add(i)
        stack.extend(adj.get(i, set()) - seen)
    assert seen == set(range(len(pts)))


def test_road_network_connects_and_scales():
    s = _terrain()
    edges = s.apply_road_network([(4, 4), (30, 12), (58, 10), (60, 55), (20, 50)],
                                 width=3, palette="rustic_oak", seed=2)
    assert len(edges) == 4
    pal = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:gravel" in pal or "minecraft:coarse_dirt" in pal


def test_road_network_complete_mesh():
    s = Session.new((24, 24, 24))
    s.set_box((0, 0, 0), (23, 3, 23), "minecraft:grass_block")
    edges = s.apply_road_network([(2, 2), (21, 2), (2, 21)], complete=True, width=1,
                                  blocks=["minecraft:cobblestone"])
    assert len(edges) == 3  # triangle


# ---- buildings --------------------------------------------------------------

def test_tower_parts_and_roof():
    s = _terrain()
    res = s.apply_tower(20, 20, radius=4, floors=3, palette="medieval_stone",
                        roof="cone", seed=1)
    assert res["walls"] > 40 and res["floors"] > 0 and res["roof"] > 10
    pal = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:stone_bricks" in pal
    assert any("slab" in n for n in pal)  # floors from trim


def test_tower_flat_roof_makes_battlements():
    s = _terrain()
    s.apply_tower(20, 20, radius=3, floors=1, block="minecraft:stone_bricks",
                  roof="flat")
    pal = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:stone_slab" in pal  # crenels from default trim


def test_tower_requires_ground_and_radius():
    s = Session.new((16, 16, 16))
    with pytest.raises(ValueError):
        s.apply_tower(5, 5, radius=1)   # too small... but no ground anyway
    s2 = Session.new((16, 16, 16))
    with pytest.raises(ValueError):
        s2.apply_tower(5, 5, radius=4)  # no ground


def test_battlements_auto_material_and_spacing():
    s = Session.new((20, 16, 20))
    s.add(Box(3, 2, 3, 15, 8, 15), "minecraft:cobblestone", hollow=True)
    n = s.apply_battlements((3, 8, 3), (15, 8, 15), merlon_every=2)
    assert n > 10
    # top ring y=9 alternates merlon/gap
    ring_y = 9
    ring = [(x, 3) for x in range(3, 16)]
    filled = [s.grid.get(x, ring_y, 3) != Block.parse("minecraft:air") for x, _ in ring]
    assert any(filled) and not all(filled)


def test_bridge_deck_above_terrain_with_rails():
    s = _terrain()
    pre = ground_height(s.grid, 16, 35)
    n = s.apply_bridge([(4, 30), (30, 40)], width=3, palette="rustic_oak",
                       pier_spacing=5)
    assert n > 20
    pal = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:spruce_slab" in pal  # railing defaults to rustic trim
    assert "minecraft:oak_log" in pal      # default support piers
    # deck rises above the local terrain at the crossing point
    post = ground_height(s.grid, 16, 35)
    assert post is not None and pre is not None and post > pre
    # and the deck is elevated: somewhere above y=14 on the route
    assert s.grid.get(16, post, 35).name != "minecraft:air"



# ---- decay ------------------------------------------------------------------

def test_ruin_removes_and_leaves_debris():
    s = Session.new((32, 24, 32))
    s.add(Box(8, 1, 8, 23, 18, 23), "minecraft:stone_bricks", hollow=True)
    s.add(Box(8, 18, 8, 23, 18, 23), "minecraft:oak_planks")
    before = s.stats()["solid"]
    n = s.apply_ruin((8, 1, 8), (23, 18, 23), amount=0.5, seed=3)
    after = s.stats()["solid"]
    assert n > 20
    assert after < before  # some removed even with debris added
    # seeded determinism
    s2 = Session.new((32, 24, 32))
    s2.add(Box(8, 1, 8, 23, 18, 23), "minecraft:stone_bricks", hollow=True)
    s2.add(Box(8, 18, 8, 23, 18, 23), "minecraft:oak_planks")
    s2.apply_ruin((8, 1, 8), (23, 18, 23), amount=0.5, seed=3)
    assert (s.grid.data == s2.grid.data).all()


def test_ruin_amount_validation():
    s = Session.new((8, 8, 8))
    with pytest.raises(ValueError):
        s.apply_ruin((0, 0, 0), (4, 4, 4), amount=0.0)


# ---- lighting ---------------------------------------------------------------

def test_lighting_lattice_places_on_ground():
    s = _terrain()
    n = s.apply_lighting((2, 0, 2), (60, 0, 60), light="minecraft:lantern", spacing=8)
    assert n >= 30
    pal = s.grid.palette
    idx = next((i for i, b in enumerate(pal.blocks())
                if b.name == "minecraft:lantern"), None)
    assert idx is not None
    ys = np.argwhere(s.grid.data == idx)
    for x, y, z in ys[:5]:
        # light sits one above a solid floor
        assert s.grid.data[x, y - 1, z] != 0


def test_lighting_spacing_validation():
    s = _terrain()
    with pytest.raises(ValueError):
        s.apply_lighting((0, 0, 0), (10, 0, 10), spacing=1)


# ---- caves ------------------------------------------------------------------

def test_caves_carves_underground_protects_surface():
    s = Session.new((48, 24, 48))
    s.set_box((0, 0, 0), (47, 20, 47), "minecraft:stone")
    top_surface = [ground_height(s.grid, x, z) for x in (6, 20, 40) for z in (6, 20, 40)]
    n = s.apply_caves((2, 2, 2), (45, 16, 45), scale=0.2, threshold=0.55,
                      seed=42, protect_surface=3)
    assert n > 100
    # surface skin untouched: same tops
    after = [ground_height(s.grid, x, z) for x in (6, 20, 40) for z in (6, 20, 40)]
    assert top_surface == after
    # caves are air pockets inside
    assert int(np.count_nonzero(s.grid.data)) == 48 * 21 * 48 - n


def test_caves_determinism_and_validation():
    a = Session.new((24, 16, 24))
    b = Session.new((24, 16, 24))
    for s in (a, b):
        s.set_box((0, 0, 0), (23, 12, 23), "minecraft:stone")
        s.apply_caves((0, 0, 0), (23, 12, 23), scale=0.2, threshold=0.6, seed=1,
                      protect_surface=0)
    assert (a.grid.data == b.grid.data).all()
    with pytest.raises(ValueError):
        a.apply_caves((0, 0, 0), (4, 4, 4), threshold=1.5)


def test_ruin_and_caves_chunked_match_dense():
    from schematica.generators.templates import apply_terrain
    d = Session.new((48, 24, 48))
    c = Session.new((48, 24, 48), chunked=True, chunk_size=16)
    for s in (d, c):
        apply_terrain(s, seed=5, amplitude=4)
        s.add(Box(20, 16, 20, 34, 24, 34), "minecraft:stone_bricks", hollow=True)
        s.apply_ruin((20, 16, 20), (34, 24, 34), amount=0.5, seed=3)
        s.apply_caves((2, 2, 2), (45, 14, 45), scale=0.2, threshold=0.6,
                      seed=1, protect_surface=3)
    _assert_same_named_blocks(d, c)


def _assert_same_named_blocks(d, c):
    import numpy as np
    da = d.grid.data
    ca = c.grid.to_dense().data
    d_names = [b.name for b in d.grid.palette.blocks()]
    c_names = [b.name for b in c.grid.palette.blocks()]
    lut = np.array([d_names.index(n) for n in c_names], dtype=np.uint64)
    assert (da == lut[ca]).all()


def test_ruin_caves_chunked_do_not_densify(monkeypatch):
    # On chunked sessions these ops must work per-region; forbid to_dense.
    from schematica.core.chunked import ChunkedGrid
    s = Session.new((64, 28, 64), chunked=True, chunk_size=16)
    from schematica.generators.templates import apply_terrain
    apply_terrain(s, seed=1, amplitude=2)
    s.add(Box(10, 12, 10, 30, 22, 30), "minecraft:stone_bricks", hollow=True)

    original = ChunkedGrid.to_dense

    def _boom(self):  # pragma: no cover - failure signal
        raise AssertionError("dense materialization forbidden in region ops")

    monkeypatch.setattr(ChunkedGrid, "to_dense", _boom)
    n1 = s.apply_ruin((10, 12, 10), (30, 22, 30), amount=0.6, seed=4)
    n2 = s.apply_caves((2, 2, 2), (40, 12, 40), scale=0.25, threshold=0.6,
                       seed=0, protect_surface=4)
    monkeypatch.setattr(ChunkedGrid, "to_dense", original)
    assert n1 > 20 and n2 > 50


def test_tower_degrades_roof_when_headroom_tight():
    # 24-tall grid, ground almost at the top: cone can't fit; degrade to flat.
    s = Session.new((24, 24, 24))
    s.set_box((8, 0, 8), (14, 17, 14), "minecraft:stone")
    res = s.apply_tower(11, 11, radius=3, block="minecraft:stone_bricks",
                        roof="cone", floors=2)
    assert res["roof_degraded_to_flat"] == 1 and res["height"] >= 3


def test_tower_raises_when_impossible():
    s = Session.new((24, 24, 24))
    s.set_box((8, 0, 8), (14, 22, 14), "minecraft:stone")  # base=23, sy=24
    with pytest.raises(ValueError):
        s.apply_tower(11, 11, radius=3, block="minecraft:stone_bricks")
