# Preview rendering

## `schematica.render.preview`

### `preview(grid, out_dir, views=("top", "front", "right", "iso"), max_voxels=96**3, max_dim=256) -> list[Path]`
Renders the VoxelGrid to PNG files in `out_dir`. Creates the directory if it
does not exist. Returns the list of written paths.

### `preview_region(grid, corner, size, out_dir, views=("top", "front", "right", "iso"), max_voxels=96**3, max_dim=256) -> list[Path]`
Extracts `grid[corner .. corner+size]` as a small dense sub-grid and renders it
with the standard `preview()` pipeline. Useful for reviewing a single team
base, spawn platform, or focal structure on large maps without waiting for a
full-map render. Raises `ValueError` if the region is outside the grid.

Small dense-grid files are named `preview_<view>.png`. Views:
- `top`   — looking down the Y axis (`view_init(elev=90, azim=-90)`).
- `front` — looking along Z (`elev=0, azim=-90`).
- `right` — along X (`elev=0, azim=0`).
- `iso`   — angled (`elev=30, azim=45`).

## Backend

Small dense grids use `matplotlib`'s `mpl_toolkits.mplot3d.Axes3D.voxels` under
the `Agg` backend (headless). The renderer:
1. Builds an `(sx, sy, sz, 4)` RGBA array from the palette.
2. Fills voxels where `grid.data != 0` (non-air) with their block's color and
   alpha 1.0; air voxels get alpha 0.0 (transparent).
3. Calls `ax.voxels(filled, facecolors=rgba, edgecolors=(0.05, 0.05, 0.05, 0.25))`.
4. Sets `view_init(elev, azim)` per view, `set_box_aspect((sx, sy, sz))` so the
   aspect ratio matches the grid.
5. Saves at 100 dpi, 6×6 inches.

Large dense grids above `max_voxels` emit a `RuntimeWarning` and switch to
downsampled 2D projected previews. `ChunkedGrid` previews always use projected
rendering and do not materialise a full dense array. `max_dim` caps the longest
rendered image axis. Projected fallback `iso` output is named
`preview_iso_projected.png` because it is a bounded top projection, not a true
3D isometric voxel render.

## Color map (live, texture-derived)

Preview colors are **not** a hand-picked code table anymore. Resolution order
(first hit wins):

1. `SCHEMATICA_BLOCK_COLORS` env var -> path to a JSON file
   (`{"colors": {"minecraft:stone": [r, g, b]}}` or a flat map; both 0-1
   floats and 0-255 ints are accepted).
2. Cached per-version tables `data/pc/<v>/block_colors.json` under the
   minecraft-data root, merged oldest -> newest (newest cached version wins).
   Generate one with `python -m schematica.blocks.colors <mc_version>`.
3. The bundled `scripts/schematica/data/block_colors.json` — 987 blocks with
   colors averaged from the actual vanilla textures (PrismarineJS
   minecraft-assets snapshot 1.21.4, plains-biome colormap tints applied to
   grass/foliage).
4. Family heuristic: variant blocks fall back to their base material color
   (`polished_granite_stairs` -> `minecraft:polished_granite`,
   `waxed_oxidized_cut_copper_stairs` -> `minecraft:copper_block`), with
   singular/plural tolerance (`stone_brick_wall` -> `stone_bricks`).
5. Stable name hash (last resort for modded/unknown blocks).

`_BLOCK_COLORS` still exists as a module attribute (now a merged view of the
chain above) for backwards compatibility.

## Extending colors

Preferred: point `SCHEMATICA_BLOCK_COLORS` at a small JSON of your overrides,
or regenerate a version-true table:
```bash
python -m schematica.blocks.colors 1.20.1   # fetch textures, write cache
```
The fetcher is stdlib-only (a minimal PNG decoder handles 1/2/4/8-bit
palette/RGB(A) vanilla textures), so it runs anywhere.

## Performance

- Comfortable 3D voxel rendering is still around ~32³. At larger sizes the
  projected fallback is intentionally less detailed but much safer.
- For visual debugging on large maps, use `views=("top",)` first, then add
  `front` or `right` only if needed.
- For final beauty shots, render a small `subregion(...)` with the 3D path.

## Reading previews as an agent

Agents cannot see images, but can verify:
```python
from pathlib import Path
for p in Path("previews").glob("preview_*.png"):
    assert p.stat().st_size > 1000   # non-empty PNG
```
A tiny or zero-byte PNG indicates a render failure; check stderr from the
schematica process for matplotlib exceptions.
