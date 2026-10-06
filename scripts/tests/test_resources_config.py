"""Data-driven resources: fallback catalog, palettes, colors, config env."""
from __future__ import annotations

import json

import schematica.blocks.registry as registry_mod
from schematica.blocks.registry import BlockRegistry
from schematica.config import default_version, package_data_dir
from schematica.resources import load_json_resource


def test_bundled_fallback_json_loads():
    raw = json.loads((package_data_dir().parent / "blocks" / "data" / "fallback_blocks.json")
                     .read_text())
    assert raw["format"] == 1
    assert len(raw["blocks"]) >= 480
    assert len(raw["states"]) >= 15


def test_bundled_palettes_json_loads():
    raw = load_json_resource("design_palettes.json")
    assert "medieval_stone" in raw["palettes"]


def test_fallback_registry_from_json():
    reg = BlockRegistry.for_version("9.9.9")  # nonexistent -> fallback catalog
    assert "minecraft:warped_fence_gate" in reg
    states = [s.name for s in reg["minecraft:warped_fence_gate"].states]
    assert "facing" in states and "in_wall" in states
    assert len(reg.all()) >= 400


def test_fallback_env_override(tmp_path, monkeypatch):
    custom = {
        "format": 1,
        "states": {"axis": [{"name": "axis", "type": "enum",
                             "values": ["x", "y", "z"], "default": "y"}]},
        "blocks": [
            {"id": 0, "name": "minecraft:air", "displayName": "Air"},
            {"id": 42, "name": "example:handmade", "displayName": "Handmade",
             "states": ["axis"]},
        ],
    }
    p = tmp_path / "fallback.json"
    p.write_text(json.dumps(custom))
    monkeypatch.setenv("SCHEMATICA_FALLBACK_BLOCKS", str(p))
    blocks = registry_mod._load_fallback_blocks()
    names = {b["name"] for b in blocks}
    assert "example:handmade" in names and "minecraft:stone" not in names
    entry = next(b for b in blocks if b["name"] == "example:handmade")
    assert entry["states"][0]["name"] == "axis"  # table ref expanded


def test_fallback_env_missing_file_emergency(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHEMATICA_FALLBACK_BLOCKS", str(tmp_path / "nope.json"))
    blocks = registry_mod._load_fallback_blocks()
    names = {b["name"] for b in blocks}
    assert "minecraft:stone" in names and "minecraft:air" in names
    assert len(blocks) >= 4


def test_default_version_env(monkeypatch):
    assert default_version() == "1.20.1"
    monkeypatch.setenv("SCHEMATICA_MC_VERSION", "1.21.5")
    assert default_version() == "1.21.5"
    monkeypatch.delenv("SCHEMATICA_MC_VERSION")


def test_session_new_uses_env_default(monkeypatch):
    from schematica.session.session import Session
    monkeypatch.setenv("SCHEMATICA_MC_VERSION", "1.21.5")
    s = Session.new((4, 4, 4))
    assert s.version == "1.21.5"


def test_json_resource_env_override(tmp_path, monkeypatch):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps({"colors": {"minecraft:stone": [10, 20, 30]}}))
    monkeypatch.setenv("SCHEMATICA_BLOCK_COLORS", str(p))
    load_json_resource.cache_clear()
    raw = load_json_resource("block_colors.json", env_var="SCHEMATICA_BLOCK_COLORS")
    monkeypatch.delenv("SCHEMATICA_BLOCK_COLORS")
    load_json_resource.cache_clear()
    assert raw["colors"]["minecraft:stone"] == [10, 20, 30]
