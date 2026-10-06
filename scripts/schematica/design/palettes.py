"""Themed design palettes (data-driven from ``data/design_palettes.json``).

A *design palette* bundles the block choices a seasoned builder makes for a
theme into named roles:

- ``ramp``     ordered dark -> light gradient ramp (used by gradients and roofs)
- ``mix``      weighted surface blend for noise texturing (block: weight)
- ``accents``  detail pops (trapdoors, foliage, ores...)
- ``trim``     edge / kerbstone material
- ``path``     road surface candidates (ordered)
- ``light``    preferred light source

The bundled table ships in ``schematica/data/design_palettes.json``; override
it with the ``SCHEMATICA_PALETTES`` environment variable pointing at your own
JSON file with the same layout -- no code changes required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..resources import load_json_resource

if TYPE_CHECKING:
    from ..generators.texture import TexturePalette


@dataclass(frozen=True)
class DesignPalette:
    name: str
    description: str = ""
    themes: tuple[str, ...] = ()
    ramp: tuple[str, ...] = ()
    mix: tuple[tuple[str, float], ...] = ()
    accents: tuple[str, ...] = ()
    trim: str = "minecraft:stone_slab"
    path: tuple[str, ...] = ()
    light: str = "minecraft:lantern"

    # -- semantic helpers -------------------------------------------------
    def ramp_block(self, t: float) -> str:
        """Block at position ``t`` (0 = darkest) along the gradient ramp."""
        if not self.ramp:
            raise ValueError(f"palette '{self.name}' has no ramp")
        t = min(max(t, 0.0), 1.0)
        return self.ramp[min(int(t * (len(self.ramp) - 1) + 0.5), len(self.ramp) - 1)]

    def texture(self, *, scale: float = 0.12, seed: int = 0,
                noise: Literal["perlin", "worley"] = "perlin") -> TexturePalette:
        """Turn the ``mix`` role into a noise-driven :class:`TexturePalette`."""
        from ..generators.texture import TexturePalette
        if not self.mix:
            raise ValueError(f"palette '{self.name}' has no mix")
        blocks = [b for b, _ in self.mix]
        weights = [w for _, w in self.mix]
        return TexturePalette(blocks=blocks, weights=weights,
                              noise=noise, scale=scale, seed=seed)


def _parse_palette(name: str, raw: dict[str, Any]) -> DesignPalette:
    mix_raw = raw.get("mix", {})
    if isinstance(mix_raw, dict):
        mix = tuple((str(k), float(v)) for k, v in mix_raw.items())
    else:
        mix = tuple((str(b), 1.0) for b in mix_raw)
    return DesignPalette(
        name=name,
        description=str(raw.get("description", "")),
        themes=tuple(raw.get("themes", ())),
        ramp=tuple(raw.get("ramp", ())),
        mix=mix,
        accents=tuple(raw.get("accents", ())),
        trim=str(raw.get("trim", "minecraft:stone_slab")),
        path=tuple(raw.get("path", ())),
        light=str(raw.get("light", "minecraft:lantern")),
    )


def load_palettes() -> dict[str, DesignPalette]:
    """Load all palettes (bundled data file, or ``SCHEMATICA_PALETTES`` override)."""
    raw = load_json_resource("design_palettes.json", env_var="SCHEMATICA_PALETTES")
    entries = raw.get("palettes", raw)
    out: dict[str, DesignPalette] = {}
    for name, spec in entries.items():
        if isinstance(spec, dict):
            out[name] = _parse_palette(name, spec)
    return out


def get_palette(name: str) -> DesignPalette:
    """Fetch a palette by name; raises ``KeyError`` with available names."""
    pals = load_palettes()
    if name not in pals:
        avail = ", ".join(sorted(pals))
        raise KeyError(f"unknown palette '{name}'; available: {avail}")
    return pals[name]


def list_palettes() -> list[DesignPalette]:
    return [load_palettes()[n] for n in sorted(load_palettes())]


def resolve_blocks(spec: str | list[str] | tuple[str, ...] | DesignPalette | None,
                   *, palette_role: str = "path") -> list[str]:
    """Normalise a blocks-or-palette argument to a concrete block list.

    Accepts: a palette name (uses its ``path``/``ramp`` role), a single block
    string, or a list/tuple of blocks. ``None`` yields an empty list.
    """
    if spec is None:
        return []
    if isinstance(spec, DesignPalette):
        return list(getattr(spec, palette_role) or spec.ramp)
    if isinstance(spec, str):
        pals = load_palettes()
        if spec in pals:
            return resolve_blocks(pals[spec], palette_role=palette_role)
        return [spec]
    return [str(b) for b in spec]
