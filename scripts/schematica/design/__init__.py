"""Advanced map-design toolkit: themed palettes, terrain-draped paths and
rivers, pitched roofs, seeded vegetation, layout tools (pads, plazas, road
networks), structural generators (towers, battlements, bridges), ruin/decay,
lighting passes, and cave carving.

Everything here is data-driven (``schematica/data/design_palettes.json``) and
works through :class:`~schematica.session.session.Session` on both dense and
chunked grids.
"""
from .buildings import apply_battlements, apply_bridge, apply_tower
from .caves import apply_caves
from .decay import apply_ruin
from .flora import apply_forest, apply_tree, tree_kinds
from .layout import apply_flatten, apply_plaza, apply_road_network, mst_edges
from .light import apply_lighting
from .palettes import DesignPalette, get_palette, list_palettes, load_palettes, resolve_blocks
from .paths import apply_path, apply_river, ground_height, plan_path
from .roofs import apply_gable_roof, apply_hip_roof

__all__ = [
    "DesignPalette", "get_palette", "list_palettes", "load_palettes",
    "resolve_blocks", "apply_path", "apply_river", "ground_height",
    "plan_path", "apply_gable_roof", "apply_hip_roof", "apply_tree",
    "apply_forest", "tree_kinds", "apply_flatten", "apply_plaza",
    "apply_road_network", "mst_edges", "apply_tower", "apply_battlements",
    "apply_bridge", "apply_ruin", "apply_lighting", "apply_caves",
]
