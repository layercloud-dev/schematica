"""Preview color resolution: texture-derived table, family fallback, overrides."""
from __future__ import annotations

import json

from schematica.blocks.block import Block
from schematica.render import preview as preview_mod


def _c(name: str) -> tuple[float, float, float]:
    return preview_mod._color_for(Block.parse(name))


def test_known_textured_colors():
    r, g, b = _c("minecraft:grass_block")
    assert g > r and g > b  # green-dominant
    r, g, b = _c("minecraft:red_wool")
    assert r > 0.5 and r > g * 2 and r > b * 2
    r, g, b = _c("minecraft:ice")
    assert b > r and b > g
    assert _c("minecraft:air") == (0.0, 0.0, 0.0)


def test_variant_family_fallback():
    # polished_granite_stairs inherits granite hues (not random hash)
    near = _c("minecraft:polished_granite_stairs")
    base = _c("minecraft:polished_granite")
    assert near == base
    # mossy_stone_brick_wall -> stone_bricks family
    c = _c("minecraft:mossy_stone_brick_wall")
    sb = _c("minecraft:stone_bricks")
    assert max(abs(a - b2) for a, b2 in zip(c, sb, strict=True)) < 0.15


def test_unknown_block_is_deterministic_hash():
    a = _c("minecraft:totally_unknown_modded_block_123")
    b = _c("minecraft:totally_unknown_modded_block_123")
    assert a == b
    assert all(0.0 <= x <= 1.0 for x in a)


def test_env_color_override_wins(tmp_path, monkeypatch):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps({"minecraft:stone": [0.01, 0.02, 0.03]}))
    monkeypatch.setenv("SCHEMATICA_BLOCK_COLORS", str(p))
    preview_mod._load_block_colors.cache_clear()
    try:
        assert _c("minecraft:stone") == (0.01, 0.02, 0.03)
        assert _c("minecraft:dirt") != (0.01, 0.02, 0.03)
    finally:
        monkeypatch.delenv("SCHEMATICA_BLOCK_COLORS")
        preview_mod._load_block_colors.cache_clear()


def test_255_scale_tables_normalized(tmp_path, monkeypatch):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps({"colors": {"minecraft:stone": [128, 64, 0]}}))
    monkeypatch.setenv("SCHEMATICA_BLOCK_COLORS", str(p))
    preview_mod._load_block_colors.cache_clear()
    try:
        r, g, b = _c("minecraft:stone")
        assert abs(r - 128 / 255) < 1e-6 and abs(g - 64 / 255) < 1e-6 and b == 0.0
    finally:
        monkeypatch.delenv("SCHEMATICA_BLOCK_COLORS")
        preview_mod._load_block_colors.cache_clear()
