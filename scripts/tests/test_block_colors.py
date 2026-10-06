"""Live block-color extraction from minecraft-assets (with mocked network)."""
from __future__ import annotations

import base64
import json
import struct
import zlib

import numpy as np

from schematica.blocks import colors as colors_mod


def _png_rgba(w: int, h: int, rgba: tuple[int, int, int, int]) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))
    return _wrap_png(w, h, 8, 6, raw)


def _png_palette4(w: int, h: int, idx: list[list[int]]) -> bytes:
    rows = []
    for row in idx:
        packed = bytearray()
        for i in range(0, w, 2):
            hi = row[i]
            lo = row[i + 1] if i + 1 < w else 0
            packed.append((hi << 4) | lo)
        rows.append(b"\x00" + bytes(packed))
    return _wrap_png(w, h, 4, 3, b"".join(rows), plte=[(10, 200, 30), (200, 20, 20)])


def _wrap_png(w, h, depth, ctype, data, plte=None) -> bytes:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBB", w, h, depth, ctype) + b"\x00\x00\x00"
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    if plte:
        out += chunk(b"PLTE", b"".join(bytes(p) for p in plte))
    out += chunk(b"IDAT", zlib.compress(data)) + chunk(b"IEND", b"")
    return out


def test_decode_png_rgba_8bit():
    png = _png_rgba(4, 4, (100, 150, 200, 255))
    arr = colors_mod._decode_png_rgba(png)
    assert arr.shape == (4, 4, 4)
    assert arr.dtype == np.uint8
    c = colors_mod._avg_color(arr)
    assert c is not None and np.allclose(c, np.array([100, 150, 200]) / 255.0)


def test_decode_png_palette_4bit():
    idx = [[0, 1], [1, 0]] * 2
    png = _png_palette4(2, 4, idx)
    arr = colors_mod._decode_png_rgba(png)
    assert arr.shape == (4, 2, 4)
    # index 0 -> green-ish, index 1 -> red-ish
    assert arr[0, 0, 1] == 200 and arr[0, 1, 0] == 200


def test_avg_color_ignores_transparent():
    arr = np.zeros((2, 2, 4), dtype=np.uint8)
    arr[0, 0] = (255, 0, 0, 255)     # one opaque red pixel
    c = colors_mod._avg_color(arr)
    assert c is not None and abs(c[0] - 1.0) < 1e-9 and c[1] == 0.0
    assert colors_mod._avg_color(np.zeros((2, 2, 4), dtype=np.uint8)) is None


def _fake_fetch_factory():
    png = _png_rgba(16, 16, (60, 100, 200, 255))
    uri = "data:image/png;base64," + base64.b64encode(png).decode()

    def fake(url: str, timeout: float = 60.0) -> bytes:
        if url.endswith("blocks_textures.json"):
            return json.dumps([
                {"name": "foo_block", "blockState": "foo_block",
                 "model": "m", "texture": "minecraft:blocks/foo_block"},
                {"name": "bar_block", "blockState": "bar_block",
                 "model": "m", "texture": "minecraft:blocks/bar_block_top"},
            ]).encode()
        if url.endswith("texture_content.json"):
            return json.dumps([
                {"name": "foo_block", "texture": uri},
                {"name": "bar_block", "texture": uri},
            ]).encode()
        raise AssertionError(f"unexpected fetch {url}")
    return fake


def test_compute_block_colors_with_mocked_network(monkeypatch):
    monkeypatch.setattr(colors_mod, "_http_get", _fake_fetch_factory())
    out = colors_mod.compute_block_colors("1.99.9")
    assert set(out) == {"minecraft:foo_block", "minecraft:bar_block"}
    r, g, b = out["minecraft:foo_block"]
    assert abs(r - 60 / 255) < 1e-3 and abs(b - 200 / 255) < 1e-3


def test_download_block_colors_writes_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(colors_mod, "_http_get", _fake_fetch_factory())
    monkeypatch.setattr(colors_mod, "best_assets_version", lambda v, timeout=30: "X.Y")
    dest = colors_mod.download_block_colors("1.20.1", cache_root=tmp_path)
    assert dest.name == "block_colors.json"
    payload = json.loads(dest.read_text())
    assert payload["assets_version"] == "X.Y"
    assert "minecraft:foo_block" in payload["colors"]
    # second call without force returns cached path (no fetch storms)
    dest2 = colors_mod.download_block_colors("1.20.1", cache_root=tmp_path)
    assert dest2 == dest


def test_best_assets_version_monotonic(monkeypatch):
    monkeypatch.setattr(colors_mod, "list_assets_versions",
                        lambda timeout=30.0: ["1.19.1", "1.20.2", "1.21.4"])
    assert colors_mod.best_assets_version("1.20.1") == "1.19.1"
    assert colors_mod.best_assets_version("1.21.4") == "1.21.4"
    assert colors_mod.best_assets_version("1.99.9") == "1.21.4"
    assert colors_mod.best_assets_version("1.7.10") == "1.19.1"


def test_manual_overrides_present():
    monkeypatch_ok = colors_mod._MANUAL_OVERRIDES
    assert "water" in monkeypatch_ok and "grass_block" in monkeypatch_ok
    for v in monkeypatch_ok.values():
        assert all(0.0 <= c <= 1.0 for c in v)
