# Design Playbook — advanced 3D map building with schematica

This guide distills professional Minecraft map-building practice into concrete,
executable steps using this toolkit. Read it before any large build. It assumes
you have skimmed `workflow_guide.md` (CLI vs Python choice).

Everything here maps 1:1 to toolkit calls. The palette, tree, and color data
are *live data files* (`scripts/schematica/data/`), not baked-in opinions —
override them per project (see "Live data" at the end).

---

## 1. Think like a map designer first

Before touching blocks, answer these in order; write the answers as session
markers (`marker` / `region`) so the intent is inspectable later:

1. **Purpose** — spawn hub? survival town? PvP arena? adventure-map set piece?
   The purpose dictates sightlines, scale, and how much interior detail matters.
2. **Scale** — pick a real-world anchor. A "cozy cottage" is ~9x11 exterior;
   a castle keep reads at ~25x35x30; a market square wants 30+ open blocks.
   If unsure, overbuild 20% then resample/trim — under-scale is the #1 tell of
   amateur maps.
3. **Theme & palette** — one palette family per district, never a global soup.
   Run `palette.list` and commit to one (e.g. `medieval_stone` for the keep,
   `rustic_oak` for the village ring).
4. **Silhouette** — the map must be recognizable in the top view. Compose a
   hierarchy: one **landmark** (tallest, most distinct), 2-4 mid-masses, and
   connective low tissue. Check silhouettes early via the iso preview.
5. **Player paths** — roads are designed, not leftover space. Lay primary
   routes (`road width=5`), secondary (width=3), footpaths (width=1-2) as a
   connected network *before* placing buildings; buildings then frame the roads.
6. **Terrain treatment** — terraform first, build second; never fight the
   heightmap with flat floors. Roads/rivers drape (`drape=true`); buildings get
   foundations, not floating slabs.

---

## 2. Composition patterns that always work

### 2.1 The 60/30/10 material rule
Per facade: ~60% dominant material (e.g. stone_bricks), ~30% secondary
(cobblestone), ~10% accent (mossy/cracked variants, shutters, lanterns). The
`mix` role of each palette already encodes workable weights — apply with a
TexturePalette at low noise frequency for coherent patches:

```python
from schematica.design import get_palette
tex = get_palette("medieval_stone").texture(scale=0.12, seed=3)
# then apply via generators.texture.apply_texture / CLI texture.palette
```

### 2.2 Skyline hierarchy
Vary roof heights and shapes deliberately: gable for halls
(`roof.gable axis=x`), hip for square towers (`roof.hip`), domes for shrines
(`add.dome`), cones for spires (`add.cone`). Keep one dominant peak; two equal
peaks fight each other.

### 2.3 Depth beats detail
A flat wall with trim at y+-1 reads better than any clever flat texture:
pilasters every 5-7 blocks, inset windows (glass one deep behind the wall
plane), string courses (slab lines) at floor boundaries, cornices at the eaves
(`overhang=1..2` on roofs does this for free).

### 2.4 Negative space
Leave at least 30-40% of a district *built-up-empty*: plazas, gardens, water.
Dense maps without negative space read as noise. Carve with `subtract.*` and
treat the voids as first-class design elements.

---

## 3. Terrain & transitions

1. **Generate terrain first** (`generate.terrain`), then adapt. Never paste a
   flat 1-block plinth under a building — step the foundation down the hill
   or extend a stone footing into the ground (`set_box` from wall bottom down
   to `surface`).
2. **Rivers & lakes**: `river points=... width=W depth=3 bed=...` cuts a
   channel and floods it one below grade, keeping banks walkable. Depth 3-4
   with a gravel/sand bed reads as natural.
3. **Roads**: `road` drapes to terrain by default and smooths out single-block
   steps (`smooth_drape=true`). For bridges/clifftop causeways use 3D points
   with `drape=false support=minecraft:oak_log` — the toolkit drops support
   columns to the ground automatically.
4. **Edge transitions**: where districts meet (stone->grass->sand), blend a
   3-6 block fringe with `paint.ramp` + `blend=0.3` or scatter the neighboring
   material across the seam (`surface.scatter`).

---

## 4. Color & material theory (grounded in the shipped color table)

The bundled preview colors are averaged from the actual vanilla textures
(PrismarineJS minecraft-assets), so palette decisions made here will look the
same in-game. Practical rules:

1. **One hue family per structure.** Medieval stone = desaturated gray ramp;
   desert = warm tan ramp. Mixing saturated hues per-face is the most common
   beginner error.
2. **Value ramps drive gradients.** Each palette `ramp` is ordered dark->light.
   Vertical placement is the classic move: darker at the base (ground contact
   shadow), lighter at the top (sky light). Execute with
   `paint.ramp palette=X frm=... to=... axis=y blend=0.15` — the `blend`
   jitter keeps the bands organic instead of hard stripes.
3. **Contrast for readability**: light build blocks (quartz, concrete) against
   dark backgrounds (deepslate, blackstone); warm lighting accents
   (lantern/campfire/shroomlight) against cool masses (stone, prismarine).
4. **Weathering = realism.** After texturing, run `edge_wear` so corners and
   exposed faces pick up mossy/cracked variants, then a light
   `surface.scatter` of moss/vines/pebbles (density 0.05-0.12). Order matters:
   struct -> mix -> gradient -> wear -> scatter -> lights.

---

## 5. Vegetation

- Trees are terrain furniture, not lollipops: vary height and kind with the
  seeded generator (`tree2 kind=... seed=...` or `forest density=... 
  kinds=oak+birch+spruce min_spacing=4`). `dead` trees (bare trunks) sell
  swamps and ruins.
- Canopy discipline: keep canopies off paths and roofs (min_spacing >= 4; the
  forest generator enforces it) or the map turns unreadable from above.
- Under-growth: `surface.scatter` with short_grass / fern / poppy near trunks
  and path edges, not everywhere.

---

## 5b. Layout & structure tools (Phase 15)

When the map crosses from "some structures" to "a designed place":

- **`flatten frm= to=`** — the honest foundation. Pad level = median ground;
  add a `cap=` (grass/stone_bricks) for a uniform surface. Always flatten
  *before* raising walls, then let the road network kiss the pad edge.
- **`plaza center=x,z radius=`** — spawn hubs and market squares in one call:
  banded paving (palette `path` role), trim border, four lamp posts, optional
  fountain. Plazas are the map's "rest" notes — place one per district.
- **`road.net points=...`** — give it the waypoint list (gates, plaza, tower,
  houses) and it connects them with a minimum-spanning-tree of draped roads.
  Add `edges=0,2;3,4` for ring roads or `complete=true` for full meshes.
- **`tower at=x,z r= floors= roof=`** — the 4-line watchtower: shell, floors,
  window slits, conical/hip/gabled/domed/flat roof. `roof=flat` auto-crenellates.
- **`battlements frm= to=`** — crenellation on any wall top; auto-matches the
  existing material, `every=2` merlons. Instantly medieval.
- **`bridge points=...`** — elevated deck at max-ground+1 with railings, piers
  at `pier_spacing`, lamp posts; the standard river/ravine crossing.
- **`ruin frm= to= amount=`** — seeded collapse with height bias (tops crumble
  first) and a rubble scatter made of the destroyed materials. Ruins read as
  "history"; undamaged boxes read as "tutorial".
- **`caves frm= to= threshold= protect=`** — 3D Perlin tunnels with a preserved
  surface skin. Great under keeps and inside hills.
- **`lighting frm= to= spacing=`** — even lantern grid on walkable ground.
- **`replace.mix src= pattern=`** — WorldEdit-style weighted material mixes
  (see `references/advanced_techniques.md` for the pattern language).

## 6. Lighting

- Light is functional *and* a palette accent: place per-palette `light` blocks
  along roads every 6-8 blocks, at doorways, and on roof ridges.
- Emissive blocks (glowstone, sea_lantern, shroomlight, copper_bulb) embed in
  walls/floors; lanterns/campfires/soul_lanterns sit *on* surfaces.
- Night readability check: run an iso preview and squint — the landmark and
  primary road lights should form an obvious constellation.

---

## 7. Procedural generation wisdom (WFC)

Wave Function Collapse (mxgmn's algorithm) guarantees *local similarity*:
(C1) every NxN output pattern appears in the input constraints, and
(weak C2) pattern frequencies mirror the input distribution. Practically for
`generate.wfc` here: feed it tile palettes whose blocks actually co-occur in
your theme (use palette `mix` + `accents`), keep regions small
(<= 24 on a side), and treat results as *raw texture* to be hand-finished —
WFC output is a starting texture, not a finished map.

---

## 8. The verification loop (do not skip)

After each macro pass (terrain, layout, mass, detail, vegetation):

1. `preview out_dir=...` and inspect **all four views** (top reveals layout /
   path connectivity; front+right reveal silhouettes and roof profiles; iso
   reveals depth and relationships).
2. Fix weakest axis first: flat silhouette -> bigger roof pitch / taller
   landmark; muddy top view -> widen roads, clear canopy clutter; repetitive
   walls -> `edge_wear` + pilasters + window insets.
3. `validate path=....schem` (round-trip) before shipping; `stats` sanity
   (solid ratio 15-60% is healthy for a town schematic; ~0% or ~100% means
   something went wrong).
4. Only then `export`. The map is done when the iso view is unambiguous at
   thumbnail size.

---

## 9. Live data reference

| Data | File | Override env | Producer |
|---|---|---|---|
| Fallback block catalog | `blocks/data/fallback_blocks.json` | `SCHEMATICA_FALLBACK_BLOCKS` | edit by hand |
| Preview block colors | `data/block_colors.json` | `SCHEMATICA_BLOCK_COLORS` | `python -m schematica.blocks.colors <mc_version>` (texture-derived from minecraft-assets) |
| Design palettes + trees | `data/design_palettes.json` | `SCHEMATICA_PALETTES` | edit by hand |
| Default MC version | `config.py` | `SCHEMATICA_MC_VERSION` | — |
| Full per-version catalogs | minecraft-data cache | `SCHEMATICA_MINECRAFT_DATA` | `python -m schematica.blocks.download <version>` |

A per-version `block_colors.json` cached next to a downloaded block catalog is
picked up automatically by previews (newest cached version wins).
