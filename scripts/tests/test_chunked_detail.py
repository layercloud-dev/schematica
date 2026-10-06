"""Chunked-backend parity for procedural detail ops (halo ghost cells)."""
from __future__ import annotations

from schematica.session.session import Session
from schematica.shapes.primitives import Box, Sphere


def _pair(shape=(20, 12, 20), chunk_size=8):
    d = Session.new(shape)
    c = Session.new(shape, chunked=True, chunk_size=chunk_size)
    return d, c


def _same(d: Session, c: Session) -> bool:
    a = d.grid.data
    b = c.grid.to_dense().data
    return a.shape == b.shape and bool((a == b).all())


def test_paint_gradient_chunked_matches_dense():
    d, c = _pair()
    for s in (d, c):
        s.add(Box(2, 1, 2, 17, 8, 17), "minecraft:stone")
        s.paint_gradient((0, 0, 0), (19, 11, 19),
                         ["minecraft:deepslate_bricks", "minecraft:stone_bricks",
                          "minecraft:quartz_block"], axis="y")
    assert _same(d, c)


def test_paint_gradient_chunked_matches_dense_with_blend():
    d, c = _pair((24, 10, 24), chunk_size=8)
    for s in (d, c):
        s.add(Box(3, 1, 3, 20, 8, 20), "minecraft:stone")
        s.paint_gradient((4, 0, 4), (19, 9, 19),
                         ["minecraft:deepslate", "minecraft:stone", "minecraft:snow_block"],
                         axis="x", blend=0.35, seed=17)
    assert _same(d, c)


def test_edge_wear_chunk_boundaries_are_not_surfaces():
    # A solid box straddling chunk seams: seams must NOT count as exposed
    # (this regresses the halo ghost-cell off-by-one).
    d, c = _pair((24, 12, 24), chunk_size=8)
    nd = nc = 0
    for i, s in enumerate((d, c)):
        s.add(Box(3, 1, 3, 20, 9, 20), "minecraft:stone")
        n = s.edge_wear(["minecraft:mossy_cobblestone", "minecraft:cobblestone",
                         "minecraft:stone"], min_exposure=1, max_exposure=6)
        if i == 0:
            nd = n
        else:
            nc = n
    assert nd == nc
    assert _same(d, c)
    # surface count of an 18x9x18 box
    assert nd == 18 * 9 * 18 - 16 * 7 * 16  # total minus interior


def test_surface_scatter_density_one_matches_dense():
    d, c = _pair()
    for s in (d, c):
        s.add(Sphere(10, 6, 10, 4), "minecraft:stone")
        n = s.surface_scatter("minecraft:moss_block", density=1.0,
                              min_exposure=1, max_exposure=6)
        assert n > 0
    assert _same(d, c)


def test_paint_gradient_chunked_big_grid_no_dense_fallback():
    # A map too large to comfortably densify must still paint correctly.
    s = Session.new((256, 48, 256), chunked=True, chunk_size=16)
    s.set_box((100, 1, 100), (155, 40, 155), "minecraft:stone")
    n = s.paint_gradient((0, 0, 0), (255, 47, 255),
                         ["minecraft:deepslate", "minecraft:stone"], axis="y")
    assert n == 56 * 40 * 56
    low = s.grid.get(120, 3, 120).name    # t=3/47 ~ 0.06 -> deepslate
    high = s.grid.get(120, 38, 120).name  # t=38/47 ~ 0.81 -> stone
    assert low == "minecraft:deepslate" and high == "minecraft:stone"
