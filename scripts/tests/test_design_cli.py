"""CLI dispatch tests for the design commands."""
from __future__ import annotations

from schematica.cli import validation as v
from schematica.cli.repl import dispatch
from schematica.session.session import Session


def _sess() -> Session:
    s = Session.new((48, 24, 48), version="1.20.1")
    dispatch(s, "generate.terrain seed=7 amplitude=3")
    return s


def test_palette_list_and_info():
    s = Session.new((8, 8, 8))
    out = dispatch(s, "palette.list")
    assert "medieval_stone" in out and "cherry_grove" in out
    info = dispatch(s, "palette.info name=medieval_stone")
    assert "ramp:" in info and "trim:" in info


def test_paint_ramp_command():
    s = _sess()
    dispatch(s, "add.box frm=10,12,10 to=20,20,20 block=minecraft:stone")
    out = dispatch(s, "paint.ramp palette=deepslate_dungeon frm=10,12,10 to=20,20,20 axis=y")
    assert "painted" in out
    names = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:polished_deepslate" in names


def test_paint_ramp_unknown_palette_refused():
    s = _sess()
    out = dispatch(s, "paint.ramp palette=no_such_palette frm=0,0,0 to=3,3,3")
    assert out.startswith("error:")
    assert "unknown_palette" in out


def test_road_and_river_commands():
    s = _sess()
    out = dispatch(s, "road points=2,2;40,40 width=3 palette=rustic_oak border=minecraft:oak_log seed=1")
    assert out.startswith("road paved")
    out2 = dispatch(s, "river points=2,20;40,30 width=2 depth=3 bed=minecraft:gravel")
    assert out2.startswith("river carved")
    names = {b.name for b in s.grid.palette.blocks()}
    assert "minecraft:water" in names


def test_road_bad_points_refused():
    s = _sess()
    out = dispatch(s, "road points=4 width=2")
    assert out.startswith("error:")


def test_roof_commands():
    s = _sess()
    dispatch(s, "add.hbox frm=10,10,10 to=20,18,20 block=minecraft:stone_bricks")
    g = dispatch(s, "roof.gable frm=10,18,10 to=20,18,20 axis=x palette=medieval_stone")
    h = dispatch(s, "roof.hip frm=24,18,24 to=30,18,30 block=minecraft:mud_bricks")
    assert g.startswith("gable")
    assert h.startswith("hip")
    bad = dispatch(s, "roof.gable frm=10,18,10 to=20,18,20 axis=y")
    assert bad.startswith("error:") and "bad_axis" in bad


def test_tree2_and_forest_commands():
    s = _sess()
    t = dispatch(s, "tree2 at=5,5 kind=spruce seed=2")
    assert "tree(spruce)" in t
    f = dispatch(s, "forest frm=20,0,20 to=40,0,40 density=0.05 kinds=oak+birch seed=2")
    assert f.startswith("forest planted")
    bad = dispatch(s, "tree2 at=5,5 kind=baobab")
    assert bad.startswith("error:") and "unknown_tree_kind" in bad


def test_surface_command():
    s = _sess()
    out = dispatch(s, "surface x=10 z=10")
    assert out.startswith("surface (10,10) = ")
    y = int(out.split("=")[-1])
    assert y > 0


def test_validators_direct():
    s = Session.new((24, 24, 24))
    res = v.check_paint_ramp("nope", "0,0,0", "4,4,4", "y", s)
    assert any(c.is_error and c.code == "unknown_palette" for c in res)
    res = v.check_paint_ramp("medieval_stone", "0,0,0", "4,4,4", "w", s)
    assert any(c.code == "bad_axis" for c in res)
    res = v.check_road("2,2", 0, s)
    assert any(c.code == "bad_points" for c in res)
    assert any(c.code == "bad_width" for c in res)
    res = v.check_river("2,2;8,8", 2, 0, s)
    assert any(c.code == "bad_depth" for c in res)
    res = v.check_roof("2,5,2", "8,3,8", "x", s)
    assert any(c.code == "inverted_bounds" for c in res)
    res = v.check_forest("0,0,0", "8,8,8ifbad", 0.0, "oak+acacia", s)
    assert any(c.code in ("bad_coords", "bad_density", "unknown_tree_kind") for c in res)
    res = v.check_tree2("5,5", "oak", s)
    assert res == []
