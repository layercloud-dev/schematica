"""Central configuration for schematica (no scattered hardcodes).

All package-wide defaults live here and are overridable via environment
variables, so agents and CI can retarget the toolkit without editing source:

- ``SCHEMATICA_MC_VERSION``     default Minecraft version for new sessions
- ``SCHEMATICA_MINECRAFT_DATA`` path to a vendored/cached minecraft-data tree
- ``SCHEMATICA_FALLBACK_BLOCKS`` path to an alternate fallback-blocks JSON
- ``SCHEMATICA_BLOCK_COLORS``   path to an alternate preview-color JSON
- ``SCHEMATICA_DATA_ROOT``      path to an alternate package-data directory
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_VERSION_FALLBACK = "1.20.1"


def default_version() -> str:
    """Default Minecraft version for new sessions (env overridable)."""
    v = os.environ.get("SCHEMATICA_MC_VERSION", "").strip()
    return v or DEFAULT_VERSION_FALLBACK


def package_data_dir() -> Path:
    """Directory holding bundled JSON data files (env overridable).

    Bundled data: ``blocks/data/fallback_blocks.json`` stays with the blocks
    module for historical layout; design palettes and preview colors live in
    ``schematica/data/``. ``SCHEMATICA_DATA_ROOT`` only overrides the latter.
    """
    env = os.environ.get("SCHEMATICA_DATA_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "data"
