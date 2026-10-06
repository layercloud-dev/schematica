"""Advanced map-design toolkit: themed palettes, terrain-draped paths and
rivers, pitched roofs, and seeded vegetation.

Everything here is data-driven (``schematica/data/design_palettes.json``) and
works through :class:`~schematica.session.session.Session` on both dense and
chunked grids.
"""
from .flora import apply_forest, apply_tree, tree_kinds
from .palettes import DesignPalette, get_palette, list_palettes, load_palettes, resolve_blocks
from .paths import apply_path, apply_river, ground_height, plan_path
from .roofs import apply_gable_roof, apply_hip_roof

__all__ = [
    "DesignPalette", "get_palette", "list_palettes", "load_palettes",
    "resolve_blocks", "apply_path", "apply_river", "ground_height",
    "plan_path", "apply_gable_roof", "apply_hip_roof", "apply_tree",
    "apply_forest", "tree_kinds",
]
