# Advanced techniques: patterns, masks, and deform thinking

This reference distills the pattern/mask/deform model used by professional
in-game tooling (WorldEdit 7, FAWE) — the sources we studied while building
this toolkit — and maps each concept onto schematica calls. It is an
*original* summary for this repo, informed by the WorldEdit 7.4 documentation
(`https://worldedit.enginehub.org/en/latest/usage/general/patterns/`) and the
WaveFunctionCollapse algorithm (mxgmn).

## What "patterns" are (and why we adopted them)

In WorldEdit, a *pattern* is anything that decides which block gets placed:
a single block, a weighted random mix, a randomized state choice, a clipboard
repeat, or a state/type remap. The two properties worth internalizing:

1. **Weights are relative, not absolute.** `5%dirt,15%stone` means 25% dirt,
   75% stone — the total is normalized. (schematica's `patterns.parse_pattern`
   shares this rule; `25%` needs at least one other choice to be meaningful.)
2. **States compose with the block name.** `oak_stairs[facing=east,half=top]`
   is a pattern too. schematica accepts full blockstate strings anywhere a
   block is expected.

### schematica pattern syntax (data: `schematica/patterns.py`)

```
stone_bricks                                single block
stone_bricks,mossy_stone_bricks             equal mix (also | or + separated)
3x stone_bricks, 1x cracked_stone_bricks    explicit weights
75%stone_bricks,25%mossy_cracked            percent-style weights
oak_log[axis=y]                              states included
```

Used by: `replace.mix src=... pattern="3x a, b"` (per-voxel weighted replace,
seeded, undoable), and accepted anywhere a "blocks" concept appears
(`road blocks=a|b` equal-mix remains; the `pattern=` style adds weights).

The closest WorldEdit cousin, the `^`-prefix "type/state applying" pattern
("turn all oak stairs into acacia, keep facings"), is covered natively by our
`retexture` module (`retexture property=facing value=east name=minecraft:oak_stairs`,
`retexture.map`), which remaps states in-place without touching other cells.

## Masks (what gets touched)

WorldEdit's mask layer answers "which voxels may this op touch?" — globally,
only-solids, only-air, near-surface, below-height... schematica encodes the
same decisions *structurally* per tool instead of as a general expression:

| Mask concept               | schematica equivalent |
|---|---|
| only existing blocks       | `paint` / `intersect` / `paint.gradient` (never fill air) |
| only exposed surfaces      | `edge.wear`, `surface.scatter` (1-6 air neighbours) |
| only on certain materials  | `surface.scatter on_blocks=...`, `replace` src filter |
| height-limited             | `paint.ramp axis=y` bands; `ruin` collapse bias |
| below-surface (buried)     | `caves protect=N` |
| region-bounded             | every op takes `frm`/`to` |

## Deform ideas (roadmap beyond today)

WorldEdit's `deform` expression parser (e.g. `y+=0.2*sin(x)` swirls) and the
FAWE bend/twist tools are the remaining classic tools we have *partially*:
`NoiseDeformed` does noise displacement today; `Rotated(angle_deg=...)` does
arbitrary yaw. A full expression-deform op is intentionally not built — a
twisted tower is better expressed as `Session.enable_radial_symmetry` +
per-level `clone.translate` or an SDF blend, both already available.

## WFC usage theory (why your tileset choice matters)

Wave Function Collapse (mxgmn, 2016) guarantees two properties:

- **(C1) hard local similarity** — every NxN pattern in the output exists in
  the input/constraints. Feed it blocks that genuinely co-occur and adjacency
  mistakes are structurally impossible.
- **(weak C2) soft distribution match** — frequencies track the input. Bias
  materials by repeating them in the palette (e.g. `stone_bricks` x3, mossy
  x1) — exactly what the `mix` role of each design palette encodes.

Practical rules for `generate.wfc`: small regions (<= 24³), theme-consistent
palettes (`palette list` first), and treat the output as raw texture to be
hand-finished — WFC writes pattern, not architecture.

## Recipes: when you want X, call Y

| Goal | Tool |
|---|---|
| level a build site | `flatten frm= to= cap=minecraft:grass_block` |
| spawn plaza | `plaza center=x,z radius=10 palette=modern_concrete fountain=true` |
| connect outposts | `road.net points=x,z;x,z width=3 palette=rustic_oak` |
| watch tower | `tower at=x,z r=4 floors=3 palette=medieval_stone roof=cone` |
| castle walls | `add.hbox ...` + `battlements frm= to= every=2` |
| river crossing | `bridge points=... pier_spacing=6 palette=rustic_oak` |
| weather a build | `ruin` (0.35) or `edge.wear` + `surface.scatter` (gentle) |
| night-ready town | `lighting frm= to= spacing=7 light=minecraft:lantern` |
| underground | `caves frm= to= threshold=0.62 protect=4` |
| mottled stone walls | `replace.mix src=minecraft:stone pattern="6x stone_bricks,2x cobble,1x mossy"` |
| cliff foundation | `flatten` + manual `set_box` footing, or `road ... support=` |
