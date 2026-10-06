"""Command spec table: name, arg kinds, handler -> Session method.

Used by the REPL for parsing + completion. Each entry maps a command name to a
list of (keyword, type) specs and a function that mutates the session.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import default_version
from .session import Session


@dataclass
class ArgSpec:
    name: str
    kind: str  # 'int','float','str','coords','bool','block','shape'
    required: bool = True
    default: Any = None


@dataclass
class CommandSpec:
    name: str
    args: tuple[ArgSpec, ...]
    handler: Callable[..., Any]
    help: str = ""


def _coord_tuple(s: str) -> tuple[int, int, int]:
    if isinstance(s, (tuple, list)):
        return tuple(int(p) for p in s)
    s = s.strip().lstrip("(").rstrip(")")
    parts = s.replace(",", " ").split()
    if len(parts) != 3:
        raise ValueError(f"expected x,y,z got {s}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def _coord_pair(s: str) -> tuple[float, float]:
    if isinstance(s, (tuple, list)) and len(s) == 2:
        return (float(s[0]), float(s[1]))
    s = s.strip().lstrip("(").rstrip(")")
    parts = s.replace(",", " ").split()
    if len(parts) != 2:
        raise ValueError(f"expected x,z got {s}")
    return (float(parts[0]), float(parts[1]))


def _size_tuple(s: str) -> tuple[int, int, int]:
    return _coord_tuple(s.replace("x", ","))


def cmd_session_new(s: Session, size: str, version: str = "",
                    fill: str = "minecraft:air", chunked: bool = False,
                    chunk_size: int = 16) -> str:
    from ..blocks.block import Block as _Block
    new = Session.new(_size_tuple(size), version=version or default_version(),
                      fill=_Block.parse(fill), chunked=chunked,
                      chunk_size=chunk_size)
    s.__dict__.update(new.__dict__)
    mode = "chunked" if chunked else "dense"
    return f"new session {size} v{new.version} ({mode})"


def cmd_add_box(s: Session, frm: str, to: str, block: str = "minecraft:stone",
                hollow: bool = False) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Box(x0, y0, z0, x1, y1, z1, hollow=hollow), block)
    return f"box {frm}->{to} {block}"


def cmd_add_sphere(s: Session, center: str, r: float, block: str = "minecraft:stone",
                   hollow: bool = False) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.add(Sphere(cx, cy, cz, r, hollow=hollow), block)
    return f"sphere @ {center} r={r}"


def cmd_add_cylinder(s: Session, center: str, r: float, h: int, block: str = "minecraft:stone",
                     hollow: bool = False) -> str:
    from ..shapes.primitives import Cylinder
    cx, _, cz = _coord_tuple(center)
    y0 = _coord_tuple(center)[1]
    s.add(Cylinder(cx, cz, r, y0, y0 + h - 1, hollow=hollow), block)
    return f"cylinder {center} r={r} h={h}"


def cmd_add_dome(s: Session, center: str, r: float, block: str = "minecraft:stone",
                 hollow: bool = False) -> str:
    from ..shapes.primitives import Dome
    cx, cy, cz = _coord_tuple(center)
    s.add(Dome(cx, cy, cz, r, hollow=hollow), block)
    return f"dome @ {center} r={r}"


def cmd_add_helix(s: Session, center: str, r: float, y0: int, y1: int,
                  turns: float = 3.0, block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Helix
    cx, _, cz = _coord_tuple(center)
    cy = _coord_tuple(center)[1]
    s.add(Helix(cx, cy, cz, r, y0, y1, turns=turns), block)
    return f"helix @ {center} r={r} y={y0}->{y1} turns={turns}"


def cmd_add_arch(s: Session, center: str, z0: int, z1: int, r: float,
                 thickness: float = 1.0, block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Arch
    cx, cy, _ = _coord_tuple(center)
    s.add(Arch(cx, cy, z0, z1, r, thickness=thickness), block)
    return f"arch @ {center} r={r} z={z0}->{z1}"


def cmd_add_staircase(s: Session, corner: str, y1: int, step_width: int = 3,
                      step_depth: int = 2, step_height: int = 1,
                      axis: str = "x", block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Staircase
    x0, y0, z0 = _coord_tuple(corner)
    s.add(Staircase(x0, y0, z0, y1, step_width=step_width,
                    step_depth=step_depth, step_height=step_height, axis=axis), block)
    return f"staircase @ {corner} y1={y1} axis={axis}"


def cmd_subtract_sphere(s: Session, center: str, r: float) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.subtract(Sphere(cx, cy, cz, r))
    return f"subtracted sphere @ {center} r={r}"


def cmd_subtract_cylinder(s: Session, center: str, r: float, h: int) -> str:
    from ..shapes.primitives import Cylinder
    cx, _, cz = _coord_tuple(center)
    y0 = _coord_tuple(center)[1]
    s.subtract(Cylinder(cx, cz, r, y0, y0 + h - 1))
    return f"subtracted cylinder @ {center} r={r} h={h}"


def cmd_paint_box(s: Session, frm: str, to: str, block: str) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.paint(Box(x0, y0, z0, x1, y1, z1), block)
    return f"painted box {frm}->{to} {block}"


# WorldEdit-style hollow shortcuts (h-prefix = hollow=True forced)
def cmd_add_hbox(s: Session, frm: str, to: str, block: str = "minecraft:stone") -> str:
    return cmd_add_box(s, frm, to, block=block, hollow=True).replace("box", "hbox", 1)


def cmd_add_hsphere(s: Session, center: str, r: float, block: str = "minecraft:stone") -> str:
    return cmd_add_sphere(s, center, r, block=block, hollow=True).replace("sphere", "hsphere", 1)


def cmd_add_hcylinder(s: Session, center: str, r: float, h: int,
                      block: str = "minecraft:stone") -> str:
    return cmd_add_cylinder(s, center, r, h, block=block, hollow=True).replace("cylinder", "hcylinder", 1)


def cmd_add_hdome(s: Session, center: str, r: float, block: str = "minecraft:stone") -> str:
    return cmd_add_dome(s, center, r, block=block, hollow=True).replace("dome", "hdome", 1)


def cmd_add_hellipsoid(s: Session, center: str, rx: float, ry: float, rz: float,
                       block: str = "minecraft:stone") -> str:
    return cmd_add_ellipsoid(s, center, rx, ry, rz, block=block, hollow=True).replace("ellipsoid", "hellipsoid", 1)


def cmd_add_cone(s: Session, center: str, r_base: float, y_base: int, y_apex: int,
                 block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Cone
    cx, _, cz = _coord_tuple(center)
    s.add(Cone(cx, cz, r_base, y_base, y_apex), block)
    return f"cone @ {center} r={r_base} y={y_base}->{y_apex}"


def cmd_add_ellipsoid(s: Session, center: str, rx: float, ry: float, rz: float,
                      block: str = "minecraft:stone",
                      hollow: bool = False) -> str:
    from ..shapes.primitives import Ellipsoid
    cx, cy, cz = _coord_tuple(center)
    s.add(Ellipsoid(cx, cy, cz, rx, ry, rz, hollow=hollow), block)
    return f"ellipsoid @ {center} rx={rx} ry={ry} rz={rz}"


def cmd_add_pyramid(s: Session, center: str, base_half: int, y_base: int, y_apex: int,
                    block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Pyramid
    cx, _, cz = _coord_tuple(center)
    s.add(Pyramid(cx, cz, base_half, y_base, y_apex), block)
    return f"pyramid @ {center} half={base_half} y={y_base}->{y_apex}"


def cmd_add_torus(s: Session, center: str, R: float, r: float,
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Torus
    cx, cy, cz = _coord_tuple(center)
    s.add(Torus(cx, cy, cz, R, r), block)
    return f"torus @ {center} R={R} r={r}"


def cmd_add_line(s: Session, frm: str, to: str,
                 block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Line
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Line(x0, y0, z0, x1, y1, z1), block)
    return f"line {frm}->{to}"


def cmd_add_wedge(s: Session, frm: str, to: str, split_axis: str = "x",
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Wedge
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.add(Wedge(x0, y0, z0, x1, y1, z1, split_axis=split_axis), block)
    return f"wedge {frm}->{to} split={split_axis}"


def cmd_add_spiral(s: Session, center: str, r_inner: float, r_outer: float,
                   y0: int, y1: int, turns: float = 2.0,
                   block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Spiral
    cx, _, cz = _coord_tuple(center)
    s.add(Spiral(cx, cz, y0, y1, r_inner, r_outer, turns=turns), block)
    return f"spiral @ {center} r={r_inner}->{r_outer} y={y0}->{y1} turns={turns}"


def cmd_add_plane(s: Session, axis: str, coord: int, thickness: int = 1,
                  block: str = "minecraft:stone") -> str:
    from ..shapes.primitives import Plane
    s.add(Plane(axis, coord, thickness=thickness), block)
    return f"plane axis={axis} coord={coord} thickness={thickness}"


def cmd_subtract_dome(s: Session, center: str, r: float) -> str:
    from ..shapes.primitives import Dome
    cx, cy, cz = _coord_tuple(center)
    s.subtract(Dome(cx, cy, cz, r))
    return f"subtracted dome @ {center} r={r}"


def cmd_subtract_pyramid(s: Session, center: str, base_half: int,
                         y_base: int, y_apex: int) -> str:
    from ..shapes.primitives import Pyramid
    cx, _, cz = _coord_tuple(center)
    s.subtract(Pyramid(cx, cz, base_half, y_base, y_apex))
    return f"subtracted pyramid @ {center} half={base_half}"


def cmd_paint_sphere(s: Session, center: str, r: float, block: str) -> str:
    from ..shapes.primitives import Sphere
    cx, cy, cz = _coord_tuple(center)
    s.paint(Sphere(cx, cy, cz, r), block)
    return f"painted sphere @ {center} r={r} {block}"


def cmd_subtract_box(s: Session, frm: str, to: str) -> str:
    from ..shapes.primitives import Box
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    s.subtract(Box(x0, y0, z0, x1, y1, z1))
    return f"subtracted box {frm}->{to}"


def cmd_replace(s: Session, src: str, dst: str) -> str:
    n = s.replace(src, dst)
    return f"replaced {n} {src}->{dst}"


def cmd_replace_bulk(s: Session, mapping: str) -> str:
    """mapping is comma-separated 'src=dst' pairs, e.g. 'stone=diorite,dirt=grass_block'."""
    from ..generators.replace import replace_bulk
    pairs: dict[str, str] = {}
    for part in mapping.split(","):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        pairs[k.strip()] = v.strip()
    n = replace_bulk(s.grid, pairs)
    return f"bulk replaced {n} ({len(pairs)} mappings)"


def cmd_replace_by_name(s: Session, src_name: str, dst: str) -> str:
    """Replace every block with name == src_name regardless of state."""
    from ..generators.replace import replace_by_name
    n = replace_by_name(s.grid, src_name, dst)
    return f"replaced-by-name {n} {src_name}->{dst}"


def cmd_replace_pattern(s: Session, src: str, dst: str,
                        neighbours: str = "") -> str:
    """Replace src with dst where neighbour constraints hold.

    neighbours is a ';'-separated list of 'dx,dy,dz=block' specs, e.g.
    '0,1,0=minecraft:air;0,-1,0=*' meaning "air above, any-solid below".
    """
    from ..generators.replace import NeighbourSpec, replace_pattern
    specs: list[NeighbourSpec] = []
    if neighbours:
        for part in neighbours.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            offset_s, _, block = part.partition("=")
            dx, dy, dz = (int(v) for v in offset_s.split(","))
            specs.append(NeighbourSpec((dx, dy, dz), block.strip()))
    n = replace_pattern(s.grid, src, dst, neighbours=specs or None)
    return f"pattern-replaced {n} {src}->{dst}"


def cmd_retexture(s: Session, property: str, value: str,
                  name: str = "") -> str:
    """Set a blockstate property on all blocks that have it.

    e.g. retexture property=axis value=x name=minecraft:oak_log
    """
    from ..generators.retexture import retexture
    n = retexture(s.grid, property, value, name=name or None)
    return f"retextured {n} ({property}={value})"


def cmd_retexture_map(s: Session, property: str, mapping: str,
                      name: str = "") -> str:
    """Remap a state property across many values. mapping is 'x=y,y=z,z=x'."""
    from ..generators.retexture import retexture_map
    pairs: dict[object, object] = {}
    for part in mapping.split(","):
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        pairs[k.strip()] = v.strip()
    n = retexture_map(s.grid, property, pairs, name=name or None)
    return f"retextured {n} ({property} remap)"


def cmd_texture_palette(s: Session, frm: str, to: str,
                        blocks: str, weights: str = "",
                        noise: str = "perlin", scale: float = 0.15,
                        seed: int = 0) -> str:
    """Paint a region with a noise-driven texture palette.

    blocks is '+ -separated list of blockstate strings.
    weights is optional '+ -separated list of relative weights.
    """
    from ..generators.texture import TexturePalette, apply_texture
    bl = [b.strip() for b in blocks.split("+") if b.strip()]
    w = [float(x) for x in weights.split("+") if x.strip()] if weights else []
    tp = TexturePalette(blocks=bl, weights=w or [1.0] * len(bl),
                        noise=noise, scale=scale, seed=seed)  # type: ignore[arg-type]
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    n = apply_texture(s, tp, (x0, y0, z0), (x1, y1, z1))
    return f"texture-painted {n} ({len(bl)} blocks, {noise})"


def cmd_undo(s: Session) -> str:
    return "undo ok" if s.undo() else "nothing to undo"


def cmd_redo(s: Session) -> str:
    return "redo ok" if s.redo() else "nothing to redo"


def cmd_clear(s: Session) -> str:
    s.clear()
    return "cleared"


def cmd_stats(s: Session) -> str:
    st = s.stats()
    base = (f"shape={st['shape']} vol={st['volume']} solid={st['solid']} "
            f"palette={st['palette_size']}")
    if st.get("chunked"):
        base += (f" chunks={st['chunks']} chunk_size={st['chunk_size']} "
                 f"mem={st['memory_bytes']}B")
    return base


def cmd_preview(s: Session, out_dir: str = "previews") -> str:
    from ..render.preview import preview
    paths = preview(s.grid, out_dir)
    return "previews: " + ", ".join(p.name for p in paths)


def cmd_export(s: Session, path: str) -> str:
    from ..export.sponge import write_sponge
    p = write_sponge(s.grid, path)
    return f"exported {p}"


def cmd_marker(s: Session, name: str, x: int, y: int, z: int,
               kind: str = "point") -> str:
    s.marker(name, x, y, z, kind=kind)
    return f"marker {name} at ({x},{y},{z}) kind={kind}"


def cmd_region(s: Session, name: str, corner_x: int, corner_y: int, corner_z: int,
               sx: int, sy: int, sz: int, kind: str = "area") -> str:
    s.region(name, (corner_x, corner_y, corner_z), (sx, sy, sz), kind=kind)
    return f"region {name} at ({corner_x},{corner_y},{corner_z}) size={sx}x{sy}x{sz} kind={kind}"


def cmd_export_markers(s: Session, path: str) -> str:
    p = s.export_markers(path)
    return f"markers exported {p}"


def cmd_preview_region(s: Session, corner_x: int, corner_y: int, corner_z: int,
                       sx: int, sy: int, sz: int, out_dir: str = "previews") -> str:
    from ..render.preview import preview_region
    paths = preview_region(s.grid, (corner_x, corner_y, corner_z),
                           (sx, sy, sz), out_dir)
    return "previews: " + ", ".join(p.name for p in paths)


def cmd_report(s: Session) -> str:
    from ..export.report import format_report, palette_report
    rep = palette_report(s.grid)
    return format_report(rep) + " | unknown=" + str(rep["unknown_blocks"]) + " mcedit=" + str(rep["mcedit_unmapped"])


def cmd_paint_gradient(s: Session, frm: str, to: str, blocks: str,
                       axis: str = "y", blend: float = 0.0,
                       seed: int = 0) -> str:
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    block_list = [b.strip() for b in blocks.split(",") if b.strip()]
    n = s.paint_gradient((x0, y0, z0), (x1, y1, z1), block_list,
                         axis=axis, blend=blend, seed=seed)
    return f"gradient painted {n} voxels axis={axis} blocks={len(block_list)}"


def cmd_edge_wear(s: Session, blocks: str, min_exposure: int = 1,
                  max_exposure: int = 6, noise: float = 0.0,
                  seed: int = 0) -> str:
    block_list = [b.strip() for b in blocks.split(",") if b.strip()]
    n = s.edge_wear(block_list, min_exposure=min_exposure,
                    max_exposure=max_exposure, noise=noise, seed=seed)
    return f"edge-worn {n} voxels"


def cmd_surface_scatter(s: Session, block: str, density: float = 0.1,
                        min_exposure: int = 1, max_exposure: int = 6,
                        seed: int = 0, on_blocks: str = "") -> str:
    on_list = [b.strip() for b in on_blocks.split(",") if b.strip()] if on_blocks else None
    n = s.surface_scatter(block, density=density, min_exposure=min_exposure,
                          max_exposure=max_exposure, seed=seed, on_blocks=on_list)
    return f"scattered {n} voxels of {block}"


def cmd_walkable(s: Session, x: int, y: int, z: int) -> str:
    ok = s.walkable_at(x, y, z)
    clr = s.clearance_at(x, y, z)
    return f"walkable={ok} clearance={clr} at ({x},{y},{z})"


def cmd_connected(s: Session, a: str, b: str) -> str:
    ax, ay, az = _coord_tuple(a)
    bx, by, bz = _coord_tuple(b)
    ok = s.is_connected((ax, ay, az), (bx, by, bz))
    return f"connected={ok} {a}->{b}"


def cmd_reachable(s: Session, x: int, y: int, z: int) -> str:
    n = s.reachable_area((x, y, z))
    return f"reachable area from ({x},{y},{z}): {n} voxels"


def cmd_path(s: Session, a: str, b: str) -> str:
    ax, ay, az = _coord_tuple(a)
    bx, by, bz = _coord_tuple(b)
    path = s.shortest_path((ax, ay, az), (bx, by, bz))
    if path is None:
        return f"no path {a}->{b}"
    return f"path {a}->{b}: {len(path)} steps"


def cmd_validate(s: Session, path: str, fmt: str = "sponge") -> str:
    from ..export.validation import validate_export
    r = validate_export(s.grid, path, fmt=fmt)
    return str(r)


def cmd_validate_all(s: Session, dir_path: str) -> str:
    from ..export.validation import validate_all
    results = validate_all(s.grid, dir_path)
    lines = []
    for r in results:
        lines.append(str(r))
    return "\n".join(lines)


def cmd_substitutions(s: Session) -> str:
    from ..export.materials import suggest_substitutions
    subs = suggest_substitutions(s.grid)
    if not subs:
        return "no substitutions needed (all blocks have legacy mappings)"
    lines = [f"  {k} -> {v}" for k, v in sorted(subs.items())]
    return f"{len(subs)} substitutions needed:\n" + "\n".join(lines)


def cmd_apply_substitutions(s: Session) -> str:
    from ..export.materials import apply_substitutions
    n = apply_substitutions(s.grid)
    if not s.is_chunked:
        s._record(s.grid.data.copy())
    return f"applied {n} voxel substitutions for legacy compatibility"


def cmd_constraint_add(s: Session, kind: str, a: str = "", b: str = "",
                       c: str = "", d: str = "", e: str = "") -> str:
    from ..constraints import (
        BlockAllowlist,
        BlockBan,
        BoxBounds,
        ConstraintSet,
        HeightLimit,
        MaxBlockCount,
        PaletteLimit,
        SolidRatio,
        Symmetry,
    )
    cs = s.metadata.setdefault("constraints", ConstraintSet())
    if kind == "height":
        max_y = int(a) if a else 31
        constr = HeightLimit(max_y=max_y)
    elif kind == "ban":
        banned = set(str(b.strip()) for b in a.split(",") if b.strip())
        constr = BlockBan(banned=banned)
    elif kind == "allowlist":
        allowed = set(str(b.strip()) for b in a.split(",") if b.strip())
        constr = BlockAllowlist(allowed=allowed)
    elif kind == "symmetry":
        ax = {"x": 0, "y": 1, "z": 2}.get(a or "x", 0)
        constr = Symmetry(axis=ax)
    elif kind == "bounds":
        lo = _coord_tuple(a or "0,0,0")
        hi = _coord_tuple(b or "0,0,0")
        constr = BoxBounds(min_corner=lo, max_corner=hi)
    elif kind == "max_count":
        constr = MaxBlockCount(block_name=a, max_count=int(b) if b else 100)
    elif kind == "palette":
        constr = PaletteLimit(max_size=int(a) if a else 256)
    elif kind == "solid_ratio":
        mn = float(a) if a else 0.0
        mx = float(b) if b else 1.0
        constr = SolidRatio(min_frac=mn, max_frac=mx)
    else:
        return f"unknown constraint kind: {kind}"
    cs.add(constr)
    return f"added constraint {constr.name}"


def cmd_constraint_check(s: Session) -> str:
    from ..constraints import ConstraintSet
    cs: ConstraintSet = s.metadata.get("constraints")
    if cs is None or not cs.constraints:
        return "no constraints registered"
    violations = cs.check_all(s.grid)
    if not violations:
        return f"all {len(cs.constraints)} constraints OK"
    lines = []
    for name, msgs in violations.items():
        for msg in msgs:
            lines.append(f"  [{name}] {msg}")
    return f"{len(violations)} constraints violated:\n" + "\n".join(lines)


def cmd_export_mcedit(s: Session, path: str) -> str:
    from ..export.mcedit import write_mcedit
    p = write_mcedit(s.grid, path)
    return f"exported (mcedit) {p}"


def cmd_export_litematic(s: Session, path: str) -> str:
    from ..export.litematic import write_litematic
    p = write_litematic(s.grid, path)
    return f"exported (litematic) {p}"


def cmd_save(s: Session, path: str) -> str:
    p = s.save(path)
    return f"saved {p}"


def cmd_load(s: Session, path: str) -> str:
    new = Session.load(path)
    s.__dict__.update(new.__dict__)
    return f"loaded {path}"


def cmd_fill(s: Session, block: str) -> str:
    s.fill_all(block)
    return f"filled {block}"


def cmd_mirror(s: Session, axis: str) -> str:
    amap = {"x": 0, "y": 1, "z": 2}
    s.transform_mirror(amap[axis])
    return f"mirrored {axis}"


def cmd_rotate(s: Session, times: int, axes: str = "xy") -> str:
    s.transform_rotate(times, axes)
    return f"rotated {times} {axes}"


def cmd_clone_translate(s: Session, frm: str, to: str, offset: str,
                        count: int = 1, include_air: bool = False) -> str:
    n = s.clone_translate(_coord_tuple(frm), _coord_tuple(to), _coord_tuple(offset),
                          count=count, include_air=include_air)
    return f"clone-translated {n} voxels"


def cmd_clone_cardinal(s: Session, frm: str, to: str, center: str,
                       include_air: bool = False) -> str:
    n = s.clone_cardinal(_coord_tuple(frm), _coord_tuple(to), _coord_pair(center),
                         include_air=include_air)
    return f"clone-cardinal {n} voxels"


def cmd_generate_terrain(s: Session, seed: int = 0, amplitude: int = 8,
                         scale: float = 0.06,
                         top: str = "minecraft:grass_block",
                         filler: str = "minecraft:dirt") -> str:
    from ..generators.templates import apply_terrain
    apply_terrain(s, seed=seed, amplitude=amplitude, scale=scale,
                  top=top, filler=filler)
    return f"terrain seed={seed} amp={amplitude}"


def cmd_generate_tree(s: Session, at: str, height: int = 6,
                      trunk: str = "minecraft:oak_log",
                      leaves: str = "minecraft:oak_leaves") -> str:
    from ..generators.templates import apply_tree
    x, y, z = _coord_tuple(at)
    apply_tree(s, x=x, z=z, height=height, trunk=trunk, leaves=leaves)
    return f"tree @ {at} h={height}"


def cmd_generate_wfc(s: Session, frm: str, to: str,
                     blocks: str, seed: int = 0) -> str:
    """Run WFC over a sub-box and place the resulting blocks."""
    from ..generators.wfc import run_wfc, tileset_wildcard
    x0, y0, z0 = _coord_tuple(frm)
    x1, y1, z1 = _coord_tuple(to)
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    shape = (x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1)
    if any(d <= 0 for d in shape):
        return "error: wfc box must have positive volume"
    palette = [b.strip() for b in blocks.split("+") if b.strip()]
    if not palette:
        return "error: wfc blocks must include at least one block"
    ts = tileset_wildcard(palette)
    blocks = run_wfc(shape, ts, seed=seed)
    from ..blocks.block import Block
    for xx in range(shape[0]):
        for yy in range(shape[1]):
            for zz in range(shape[2]):
                b = blocks[xx, yy, zz]
                if b != "minecraft:air":
                    s.grid.set(x0 + xx, y0 + yy, z0 + zz, Block.parse(b))
    return f"wfc {frm}->{to} blocks={len(palette)} seed={seed}"


def _points_list(s: str) -> list[tuple[int, ...]]:
    """Parse "x,z;x,z" or "x,y,z;..." path point lists."""
    out: list[tuple[int, ...]] = []
    for part in s.split(";"):
        part = part.strip().lstrip("(").rstrip(")")
        if not part:
            continue
        nums = [int(p) for p in part.replace(",", " ").split()]
        if len(nums) == 2:
            out.append((nums[0], nums[1]))
        elif len(nums) == 3:
            out.append((nums[0], nums[1], nums[2]))
        else:
            raise ValueError(f"expected x,z or x,y,z point, got {part!r}")
    return out


def _pipe_list(s: str) -> list[str]:
    out = [b.strip() for b in s.replace("+", "|").split("|") if b.strip()]
    return out


def cmd_palette_list(s: Session) -> str:
    from ..design.palettes import list_palettes
    lines = [f"{p.name} -- {p.description}" for p in list_palettes()]
    return "palettes:\n  " + "\n  ".join(lines)


def cmd_palette_info(s: Session, name: str) -> str:
    from ..design.palettes import get_palette
    p = get_palette(name)
    def short(b: str) -> str:
        return b.removeprefix("minecraft:")

    ramp_str = " -> ".join(short(b) for b in p.ramp)
    mix_str = ", ".join(f"{short(b)}x{w:g}" for b, w in p.mix)
    accent_str = ", ".join(short(b) for b in p.accents)
    return (f"palette {p.name}: {p.description}\n"
            f"  ramp: {ramp_str}\n"
            f"  mix: {mix_str}\n"
            f"  accents: {accent_str}\n"
            f"  trim: {p.trim} | light: {p.light} | path: {', '.join(p.path)}")


def cmd_paint_ramp(s: Session, palette: str, frm: str, to: str,
                   axis: str = "y", blend: float = 0.0, seed: int = 0) -> str:
    n = s.paint_palette_gradient(_coord_tuple(frm), _coord_tuple(to), palette,
                                 axis=axis, blend=blend, seed=seed)
    return f"palette gradient '{palette}' painted {n} voxels axis={axis}"


def cmd_road(s: Session, points: str, width: int = 3, block: str = "",
             blocks: str = "", palette: str = "", border: str = "",
             drape: bool = True, closed: bool = False, smooth: int = 0,
             support: str = "", seed: int = 0) -> str:
    n = s.apply_path(
        _points_list(points), width=width,
        block=block or None, blocks=_pipe_list(blocks) or None,
        palette=palette or None, border=border or None,
        drape=drape, closed=closed, smooth=smooth,
        support=support or None, seed=seed,
    )
    return f"road paved {n} voxels width={width}"


def cmd_river(s: Session, points: str, width: int = 3, depth: int = 3,
              water: str = "minecraft:water", bed: str = "",
              smooth: int = 0, closed: bool = False) -> str:
    n = s.apply_river(_points_list(points), width=width, depth=depth,
                      water=water, bed=bed or None, smooth=smooth, closed=closed)
    return f"river carved {n} voxels width={width} depth={depth}"


def cmd_roof_gable(s: Session, frm: str, to: str, axis: str = "x",
                   block: str = "", ramp: str = "", palette: str = "",
                   overhang: int = 1, steps: int = 1, stairs: str = "",
                   fill: bool = False) -> str:
    n = s.apply_gable_roof(_coord_tuple(frm), _coord_tuple(to), axis=axis,
                           block=block or None, ramp=_pipe_list(ramp) or None,
                           palette=palette or None, overhang=overhang,
                           steps_per_rise=steps, stair_block=stairs or None,
                           fill=fill)
    return f"gable roof placed {n} voxels axis={axis}"


def cmd_roof_hip(s: Session, frm: str, to: str, block: str = "",
                 ramp: str = "", palette: str = "", overhang: int = 1,
                 steps: int = 1) -> str:
    n = s.apply_hip_roof(_coord_tuple(frm), _coord_tuple(to),
                         block=block or None, ramp=_pipe_list(ramp) or None,
                         palette=palette or None, overhang=overhang,
                         steps_per_rise=steps)
    return f"hip roof placed {n} voxels"


def cmd_tree2(s: Session, at: str, kind: str = "oak", height: int = 0,
              seed: int = 0) -> str:
    pts = _points_list(at)
    p = pts[0]
    x, z = p[0], (p[2] if len(p) == 3 else p[1])
    ok = s.apply_tree_v2(x, z, kind=kind, height=height or None, seed=seed)
    return f"tree({kind}) {'planted' if ok else 'skipped (no ground/occupied)'} at {x},{z}"


def cmd_forest(s: Session, frm: str, to: str, density: float = 0.02,
               kinds: str = "oak", seed: int = 0, min_spacing: int = 3) -> str:
    kinds_t = tuple(_pipe_list(kinds)) or ("oak",)
    n = s.apply_forest(_coord_tuple(frm), _coord_tuple(to), density=density,
                       kinds=kinds_t, seed=seed, min_spacing=min_spacing)
    return f"forest planted {n} trees kinds={'+'.join(kinds_t)}"


def cmd_surface(s: Session, x: int, z: int) -> str:
    y = s.surface_height(int(x), int(z))
    return f"surface ({x},{z}) = {'none (empty column)' if y is None else y}"



def cmd_flatten(s: Session, frm: str, to: str, y: int = 0,
                fill: str = "minecraft:dirt", cap: str = "") -> str:
    n = s.apply_flatten(_coord_tuple(frm), _coord_tuple(to),
                        y=(y if y > 0 else None), fill=fill, cap=cap or None)
    return f"flattened {frm}->{to} changed={n}"


def cmd_plaza(s: Session, center: str, radius: int, palette: str = "",
              bands: str = "", ring: int = 4, border: str = "",
              fountain: bool = True, light: str = "") -> str:
    pts = _points_list(center)
    if not pts:
        return "error: center did not parse"
    n = s.apply_plaza(pts[0], radius, palette=palette or None,
                      bands=_pipe_list(bands) or None, ring_spacing=ring,
                      border=border or None, fountain=fountain,
                      light=light or None)
    return f"plaza r={radius} at {center} changed={n}"


def cmd_road_network(s: Session, points: str, width: int = 3,
                     palette: str = "", blocks: str = "", border: str = "",
                     smooth: int = 0, complete: bool = False,
                     edges: str = "", seed: int = 0) -> str:
    extra = []
    for e in edges.split(";"):
        e = e.strip()
        if not e:
            continue
        a, _, b = e.partition(",")
        extra.append((int(a), int(b)))
    pts = _points_list(points)
    edge_list = s.apply_road_network(
        pts, width=width, palette=palette or None,
        blocks=_pipe_list(blocks) or None, border=border or None,
        smooth=smooth, complete=complete, extra_edges=extra or None, seed=seed)
    return f"road.network laid {len(edge_list)} roads between {len(pts)} waypoints"


def cmd_tower(s: Session, at: str, r: int = 4, h: int = 0, floors: int = 3,
              block: str = "", palette: str = "", roof: str = "cone",
              windows: bool = True, door: str = "south", seed: int = 0) -> str:
    pts = _points_list(at)
    if not pts:
        return "error: at did not parse"
    x, z = pts[0][0], pts[0][-1]
    res = s.apply_tower(x, z, radius=r, height=h or None, floors=floors,
                        block=block or None, palette=palette or None,
                        roof=roof, windows=windows, door=door or None, seed=seed)
    return f"tower at {x},{z} h={res['height']} top={res['top']} walls={res['walls']}"


def cmd_battlements(s: Session, frm: str, to: str, block: str = "",
                    every: int = 2, height: int = 1) -> str:
    n = s.apply_battlements(_coord_tuple(frm), _coord_tuple(to),
                            block=block or None, merlon_every=every, height=height)
    return f"battlements placed {n} merlons"


def cmd_bridge(s: Session, points: str, width: int = 3, deck: str = "",
               palette: str = "", railing: str = "", support: str = "",
               pier_spacing: int = 6, lamps: bool = True) -> str:
    n = s.apply_bridge(_points_list(points), width=width, deck=deck or None,
                       palette=palette or None, railing=railing or None,
                       support=support or None, pier_spacing=pier_spacing,
                       lamps=lamps)
    return f"bridge built, {n} voxels"


def cmd_ruin(s: Session, frm: str, to: str, amount: float = 0.35,
             seed: int = 0, debris: bool = True) -> str:
    n = s.apply_ruin(_coord_tuple(frm), _coord_tuple(to), amount=amount,
                     seed=seed, debris=debris)
    return f"ruin decayed {n} voxels (amount={amount})"


def cmd_lighting(s: Session, frm: str, to: str, light: str = "minecraft:lantern",
                 spacing: int = 7, offset: int = 0) -> str:
    n = s.apply_lighting(_coord_tuple(frm), _coord_tuple(to), light=light,
                         spacing=spacing, offset=offset)
    return f"lighting placed {n} lights at spacing={spacing}"


def cmd_caves(s: Session, frm: str, to: str, scale: float = 0.08,
              octaves: int = 3, threshold: float = 0.6, seed: int = 0,
              protect: int = 3) -> str:
    n = s.apply_caves(_coord_tuple(frm), _coord_tuple(to), scale=scale,
                      octaves=octaves, threshold=threshold, seed=seed,
                      protect_surface=protect)
    return f"caves carved {n} voxels (threshold={threshold})"


def cmd_replace_mix(s: Session, src: str, pattern: str, seed: int = 0) -> str:
    n = s.replace_weighted(src, pattern, seed=seed)
    return f"replace.mix {src} -> [{pattern}]: {n} voxels"



COMMANDS: dict[str, CommandSpec] = {
    "session.new": CommandSpec("session.new", (
        ArgSpec("size", "str"), ArgSpec("version", "str", default=default_version(), required=False),
        ArgSpec("fill", "block", default="minecraft:air", required=False),
        ArgSpec("chunked", "bool", default=False, required=False),
        ArgSpec("chunk_size", "int", default=16, required=False),
    ), cmd_session_new, "create a new session: size=16x16x16 version=1.20.1 chunked=true chunk_size=16"),
    "add.box": CommandSpec("add.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_box, "add a box from=A to=B block=X hollow=true"),
    "add.hbox": CommandSpec("add.hbox", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hbox, "hollow box (walls only) from=A to=B"),
    "add.sphere": CommandSpec("add.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_sphere, "add sphere center=X r=N block=X"),
    "add.hsphere": CommandSpec("add.hsphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hsphere, "hollow sphere (shell only) center=X r=N"),
    "add.cylinder": CommandSpec("add.cylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_cylinder, "add cylinder center=X r=N h=N"),
    "add.hcylinder": CommandSpec("add.hcylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hcylinder, "hollow cylinder (tube only) center=X r=N h=N"),
    "add.dome": CommandSpec("add.dome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_dome, "add dome center=X r=N block=X hollow=true"),
    "add.hdome": CommandSpec("add.hdome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hdome, "hollow dome (shell only) center=X r=N"),
    "add.helix": CommandSpec("add.helix", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
        ArgSpec("y0", "int"), ArgSpec("y1", "int"),
        ArgSpec("turns", "float", default=3.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_helix, "add helix center=X r=N y0=A y1=B turns=N"),
    "add.arch": CommandSpec("add.arch", (
        ArgSpec("center", "coords"), ArgSpec("z0", "int"), ArgSpec("z1", "int"),
        ArgSpec("r", "float"),
        ArgSpec("thickness", "float", default=1.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_arch, "add arch center=X z0=A z1=B r=N thickness=N"),
    "add.staircase": CommandSpec("add.staircase", (
        ArgSpec("corner", "coords"), ArgSpec("y1", "int"),
        ArgSpec("step_width", "int", default=3, required=False),
        ArgSpec("step_depth", "int", default=2, required=False),
        ArgSpec("step_height", "int", default=1, required=False),
        ArgSpec("axis", "str", default="x", required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_staircase, "add staircase corner=X y1=N axis=x|z"),
    "add.cone": CommandSpec("add.cone", (
        ArgSpec("center", "coords"), ArgSpec("r_base", "float"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_cone, "add cone center=X r_base=N y_base=A y_apex=B"),
    "add.ellipsoid": CommandSpec("add.ellipsoid", (
        ArgSpec("center", "coords"), ArgSpec("rx", "float"),
        ArgSpec("ry", "float"), ArgSpec("rz", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
        ArgSpec("hollow", "bool", default=False, required=False),
    ), cmd_add_ellipsoid, "add ellipsoid center=X rx=N ry=N rz=N"),
    "add.hellipsoid": CommandSpec("add.hellipsoid", (
        ArgSpec("center", "coords"), ArgSpec("rx", "float"),
        ArgSpec("ry", "float"), ArgSpec("rz", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_hellipsoid, "hollow ellipsoid (shell only)"),
    "add.pyramid": CommandSpec("add.pyramid", (
        ArgSpec("center", "coords"), ArgSpec("base_half", "int"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_pyramid, "add pyramid center=X half=N y_base=A y_apex=B"),
    "add.torus": CommandSpec("add.torus", (
        ArgSpec("center", "coords"), ArgSpec("R", "float"), ArgSpec("r", "float"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_torus, "add torus center=X R=major r=minor"),
    "add.line": CommandSpec("add.line", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_line, "add 1-voxel line from=A to=B"),
    "add.wedge": CommandSpec("add.wedge", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("split_axis", "str", default="x", required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_wedge, "add wedge from=A to=B split_axis=x|z"),
    "add.spiral": CommandSpec("add.spiral", (
        ArgSpec("center", "coords"), ArgSpec("r_inner", "float"),
        ArgSpec("r_outer", "float"), ArgSpec("y0", "int"), ArgSpec("y1", "int"),
        ArgSpec("turns", "float", default=2.0, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_spiral, "add spiral center=X r_inner=A r_outer=B y0=C y1=D"),
    "add.plane": CommandSpec("add.plane", (
        ArgSpec("axis", "str"), ArgSpec("coord", "int"),
        ArgSpec("thickness", "int", default=1, required=False),
        ArgSpec("block", "block", default="minecraft:stone", required=False),
    ), cmd_add_plane, "add plane axis=x|y|z coord=N thickness=N"),
    "subtract.box": CommandSpec("subtract.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
    ), cmd_subtract_box, "carve a box"),
    "subtract.sphere": CommandSpec("subtract.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
    ), cmd_subtract_sphere, "carve a sphere"),
    "subtract.cylinder": CommandSpec("subtract.cylinder", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("h", "int"),
    ), cmd_subtract_cylinder, "carve a cylinder"),
    "subtract.dome": CommandSpec("subtract.dome", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"),
    ), cmd_subtract_dome, "carve a dome"),
    "subtract.pyramid": CommandSpec("subtract.pyramid", (
        ArgSpec("center", "coords"), ArgSpec("base_half", "int"),
        ArgSpec("y_base", "int"), ArgSpec("y_apex", "int"),
    ), cmd_subtract_pyramid, "carve a pyramid"),
    "paint.box": CommandSpec("paint.box", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"), ArgSpec("block", "block"),
    ), cmd_paint_box, "repaint existing solid voxels in a box"),
    "paint.sphere": CommandSpec("paint.sphere", (
        ArgSpec("center", "coords"), ArgSpec("r", "float"), ArgSpec("block", "block"),
    ), cmd_paint_sphere, "repaint existing solid voxels in a sphere"),
    "replace": CommandSpec("replace", (
        ArgSpec("src", "block"), ArgSpec("dst", "block"),
    ), cmd_replace, "replace src dst"),
    "replace.bulk": CommandSpec("replace.bulk", (
        ArgSpec("mapping", "str"),
    ), cmd_replace_bulk, "bulk replace mapping=stone=diorite,dirt=grass_block"),
    "replace.by_name": CommandSpec("replace.by_name", (
        ArgSpec("src_name", "str"), ArgSpec("dst", "block"),
    ), cmd_replace_by_name, "replace all blocks named src_name regardless of state"),
    "replace.pattern": CommandSpec("replace.pattern", (
        ArgSpec("src", "block"), ArgSpec("dst", "block"),
        ArgSpec("neighbours", "str", default="", required=False),
    ), cmd_replace_pattern, "replace src with dst where neighbours match (dx,dy,dz=block;...)"),
    "retexture": CommandSpec("retexture", (
        ArgSpec("property", "str"), ArgSpec("value", "str"),
        ArgSpec("name", "str", default="", required=False),
    ), cmd_retexture, "set a blockstate property on all blocks that have it"),
    "retexture.map": CommandSpec("retexture.map", (
        ArgSpec("property", "str"), ArgSpec("mapping", "str"),
        ArgSpec("name", "str", default="", required=False),
    ), cmd_retexture_map, "remap a state property (x=y,y=z,z=x)"),
    "texture.palette": CommandSpec("texture.palette", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("blocks", "str"),
        ArgSpec("weights", "str", default="", required=False),
        ArgSpec("noise", "str", default="perlin", required=False),
        ArgSpec("scale", "float", default=0.15, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_texture_palette, "paint a region with a noise-driven texture palette"),
    "undo": CommandSpec("undo", (), cmd_undo, "undo last op"),
    "redo": CommandSpec("redo", (), cmd_redo, "redo"),
    "clear": CommandSpec("clear", (), cmd_clear, "clear grid"),
    "stats": CommandSpec("stats", (), cmd_stats, "show stats"),
    "report": CommandSpec("report", (), cmd_report,
                          "show palette compatibility report for all export formats"),
    "marker": CommandSpec("marker", (
        ArgSpec("name", "str"), ArgSpec("x", "int"), ArgSpec("y", "int"), ArgSpec("z", "int"),
        ArgSpec("kind", "str", default="point", required=False),
    ), cmd_marker, "add a named marker marker=name x=N y=N z=N kind=point"),
    "region": CommandSpec("region", (
        ArgSpec("name", "str"),
        ArgSpec("corner_x", "int"), ArgSpec("corner_y", "int"), ArgSpec("corner_z", "int"),
        ArgSpec("sx", "int"), ArgSpec("sy", "int"), ArgSpec("sz", "int"),
        ArgSpec("kind", "str", default="area", required=False),
    ), cmd_region, "add a named region name=X corner_x=A corner_y=B corner_z=C sx=N sy=N sz=N kind=area"),
    "export.markers": CommandSpec("export.markers", (ArgSpec("path", "str"),),
                                   cmd_export_markers, "export markers+regions JSON"),
    "preview.region": CommandSpec("preview.region", (
        ArgSpec("corner_x", "int"), ArgSpec("corner_y", "int"), ArgSpec("corner_z", "int"),
        ArgSpec("sx", "int"), ArgSpec("sy", "int"), ArgSpec("sz", "int"),
        ArgSpec("out_dir", "str", default="previews", required=False),
    ), cmd_preview_region, "render a cropped sub-region preview.region corner_x=A corner_y=B corner_z=C sx=N sy=N sz=N"),
    "preview": CommandSpec("preview", (
        ArgSpec("out_dir", "str", default="previews", required=False),
    ), cmd_preview, "render preview PNGs"),
    "export": CommandSpec("export", (ArgSpec("path", "str"),), cmd_export,
                          "export Sponge .schem"),
    "export.mcedit": CommandSpec("export.mcedit", (ArgSpec("path", "str"),),
                                  cmd_export_mcedit, "export legacy MCEdit .schematic"),
    "export.litematic": CommandSpec("export.litematic", (ArgSpec("path", "str"),),
                                      cmd_export_litematic, "export Litematica .litematic"),
    "save": CommandSpec("save", (ArgSpec("path", "str"),), cmd_save,
                       "save session"),
    "load": CommandSpec("load", (ArgSpec("path", "str"),), cmd_load,
                        "load session"),
    "fill": CommandSpec("fill", (ArgSpec("block", "block"),), cmd_fill, "fill all"),
    "mirror": CommandSpec("mirror", (ArgSpec("axis", "str"),), cmd_mirror,
                           "mirror x/y/z"),
    "rotate": CommandSpec("rotate", (
        ArgSpec("times", "int"), ArgSpec("axes", "str", default="xy", required=False),
    ), cmd_rotate, "rotate 90*times in xy/xz/yz plane"),
    "clone.translate": CommandSpec("clone.translate", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"), ArgSpec("offset", "coords"),
        ArgSpec("count", "int", default=1, required=False),
        ArgSpec("include_air", "bool", default=False, required=False),
    ), cmd_clone_translate, "clone source box by offset, repeated count times"),
    "clone.cardinal": CommandSpec("clone.cardinal", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"), ArgSpec("center", "str"),
        ArgSpec("include_air", "bool", default=False, required=False),
    ), cmd_clone_cardinal, "clone source box to the other three Y-axis cardinal rotations"),
    "generate.terrain": CommandSpec("generate.terrain", (
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("amplitude", "int", default=8, required=False),
        ArgSpec("scale", "float", default=0.06, required=False),
        ArgSpec("top", "block", default="minecraft:grass_block", required=False),
        ArgSpec("filler", "block", default="minecraft:dirt", required=False),
    ), cmd_generate_terrain, "generate terrain seed=N amplitude=N"),
    "generate.tree": CommandSpec("generate.tree", (
        ArgSpec("at", "coords"), ArgSpec("height", "int", default=6, required=False),
        ArgSpec("trunk", "block", default="minecraft:oak_log", required=False),
        ArgSpec("leaves", "block", default="minecraft:oak_leaves", required=False),
    ), cmd_generate_tree, "generate a tree at=X height=N"),
    "generate.wfc": CommandSpec("generate.wfc", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("blocks", "str"),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_generate_wfc, "wave function collapse fill frm=A to=B blocks=a+b+c"),
    # ---- procedural detail ----
    "paint.gradient": CommandSpec("paint.gradient", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("blocks", "str"),
        ArgSpec("axis", "str", default="y", required=False),
        ArgSpec("blend", "float", default=0.0, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_paint_gradient, "paint gradient frm=A to=B blocks=stone,cobblestone,stone_bricks axis=y"),
    "edge.wear": CommandSpec("edge.wear", (
        ArgSpec("blocks", "str"),
        ArgSpec("min_exposure", "int", default=1, required=False),
        ArgSpec("max_exposure", "int", default=6, required=False),
        ArgSpec("noise", "float", default=0.0, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_edge_wear, "apply weathering to exposed edges blocks=mossy_cobblestone,cobblestone,stone"),
    "surface.scatter": CommandSpec("surface.scatter", (
        ArgSpec("block", "block"),
        ArgSpec("density", "float", default=0.1, required=False),
        ArgSpec("min_exposure", "int", default=1, required=False),
        ArgSpec("max_exposure", "int", default=6, required=False),
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("on_blocks", "str", default="", required=False),
    ), cmd_surface_scatter, "scatter block on exposed surfaces block=moss density=0.1"),
    # ---- spatial analysis ----
    "walkable": CommandSpec("walkable", (
        ArgSpec("x", "int"), ArgSpec("y", "int"), ArgSpec("z", "int"),
    ), cmd_walkable, "check if position is walkable x=N y=N z=N"),
    "connected": CommandSpec("connected", (
        ArgSpec("a", "coords"), ArgSpec("b", "coords"),
    ), cmd_connected, "check walkability between two points a=X b=Y"),
    "reachable": CommandSpec("reachable", (
        ArgSpec("x", "int"), ArgSpec("y", "int"), ArgSpec("z", "int"),
    ), cmd_reachable, "flood-fill reachable walkable area from (x,y,z)"),
    "path": CommandSpec("path", (
        ArgSpec("a", "coords"), ArgSpec("b", "coords"),
    ), cmd_path, "shortest walking path a=X b=Y"),
    # ---- export validation ----
    "validate": CommandSpec("validate", (
        ArgSpec("path", "str"), ArgSpec("fmt", "str", default="sponge", required=False),
    ), cmd_validate, "validate export round-trip path=out.schem fmt=sponge|litematic|mcedit"),
    "validate.all": CommandSpec("validate.all", (
        ArgSpec("dir_path", "str"),
    ), cmd_validate_all, "validate all three formats into a directory"),
    # ---- material intelligence ----
    "substitutions": CommandSpec("substitutions", (), cmd_substitutions,
                                  "show suggested legacy substitutions for unmapped blocks"),
    "apply.substitutions": CommandSpec("apply.substitutions", (),
                                       cmd_apply_substitutions,
                                       "replace unmapped blocks with legacy-compatible substitutes"),
    # ---- constraints ----
    "constraint.add": CommandSpec("constraint.add", (
        ArgSpec("kind", "str"),
        ArgSpec("a", "str", default="", required=False),
        ArgSpec("b", "str", default="", required=False),
    ), cmd_constraint_add, "add a constraint kind=height|ban|allowlist|symmetry|bounds|max_count|palette|solid_ratio a=... b=..."),
    "constraint.check": CommandSpec("constraint.check", (), cmd_constraint_check,
                                    "check all constraints against the current grid"),
    # ---- design toolkit ----
    "palette.list": CommandSpec("palette.list", (), cmd_palette_list,
                                 "list themed design palettes"),
    "palette.info": CommandSpec("palette.info", (ArgSpec("name", "str"),),
                                 cmd_palette_info, "show one palette's roles"),
    "paint.ramp": CommandSpec("paint.ramp", (
        ArgSpec("palette", "str"), ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("axis", "str", default="y", required=False),
        ArgSpec("blend", "float", default=0.0, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_paint_ramp, "gradient using a palette's ramp palette=NAME frm=A to=B axis=y"),
    "road": CommandSpec("road", (
        ArgSpec("points", "str"),
        ArgSpec("width", "int", default=3, required=False),
        ArgSpec("block", "str", default="", required=False),
        ArgSpec("blocks", "str", default="", required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("border", "str", default="", required=False),
        ArgSpec("drape", "bool", default=True, required=False),
        ArgSpec("closed", "bool", default=False, required=False),
        ArgSpec("smooth", "int", default=0, required=False),
        ArgSpec("support", "str", default="", required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_road, "terrain-draped road points=x,z;x,z width=3 palette=NAME border=..."),
    "river": CommandSpec("river", (
        ArgSpec("points", "str"),
        ArgSpec("width", "int", default=3, required=False),
        ArgSpec("depth", "int", default=3, required=False),
        ArgSpec("water", "block", default="minecraft:water", required=False),
        ArgSpec("bed", "block", default="", required=False),
        ArgSpec("smooth", "int", default=0, required=False),
        ArgSpec("closed", "bool", default=False, required=False),
    ), cmd_river, "carve a river points=x,z;x,z width=3 depth=3 bed=minecraft:gravel"),
    "roof.gable": CommandSpec("roof.gable", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("axis", "str", default="x", required=False),
        ArgSpec("block", "str", default="", required=False),
        ArgSpec("ramp", "str", default="", required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("overhang", "int", default=1, required=False),
        ArgSpec("steps", "int", default=1, required=False),
        ArgSpec("stairs", "str", default="", required=False),
        ArgSpec("fill", "bool", default=False, required=False),
    ), cmd_roof_gable, "gable roof over wall box frm=A to=B axis=x palette=NAME"),
    "roof.hip": CommandSpec("roof.hip", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "str", default="", required=False),
        ArgSpec("ramp", "str", default="", required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("overhang", "int", default=1, required=False),
        ArgSpec("steps", "int", default=1, required=False),
    ), cmd_roof_hip, "hip roof over wall box frm=A to=B palette=NAME"),
    "tree2": CommandSpec("tree2", (
        ArgSpec("at", "coords"),
        ArgSpec("kind", "str", default="oak", required=False),
        ArgSpec("height", "int", default=0, required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_tree2, "terrain-snapped tree at=X,Z kind=oak|birch|spruce|cherry|jungle|mega|dead"),
    "forest": CommandSpec("forest", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("density", "float", default=0.02, required=False),
        ArgSpec("kinds", "str", default="oak", required=False),
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("min_spacing", "int", default=3, required=False),
    ), cmd_forest, "seeded forest frm=A to=B density=0.02 kinds=oak+birch"),
    "surface": CommandSpec("surface", (
        ArgSpec("x", "int"), ArgSpec("z", "int"),
    ), cmd_surface, "print top surface y at column x,z"),
    # ---- design toolkit: phase 15 ----
    "flatten": CommandSpec("flatten", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("y", "int", default=0, required=False),
        ArgSpec("fill", "block", default="minecraft:dirt", required=False),
        ArgSpec("cap", "block", default="", required=False),
    ), cmd_flatten, "level pad frm=A to=B [y=N fill=F cap=C]"),
    "plaza": CommandSpec("plaza", (
        ArgSpec("center", "str"), ArgSpec("radius", "int"),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("bands", "str", default="", required=False),
        ArgSpec("ring", "int", default=4, required=False),
        ArgSpec("border", "block", default="", required=False),
        ArgSpec("fountain", "bool", default=True, required=False),
        ArgSpec("light", "block", default="", required=False),
    ), cmd_plaza, "paved plaza center=x,z radius=R palette=P fountain=true"),
    "road.net": CommandSpec("road.net", (
        ArgSpec("points", "str"),
        ArgSpec("width", "int", default=3, required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("blocks", "str", default="", required=False),
        ArgSpec("border", "str", default="", required=False),
        ArgSpec("smooth", "int", default=0, required=False),
        ArgSpec("complete", "bool", default=False, required=False),
        ArgSpec("edges", "str", default="", required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_road_network, "MST road network points=x,z;x,z;... complete=false edges=0,2;1,4"),
    "tower": CommandSpec("tower", (
        ArgSpec("at", "coords"),
        ArgSpec("r", "int", default=4, required=False),
        ArgSpec("h", "int", default=0, required=False),
        ArgSpec("floors", "int", default=3, required=False),
        ArgSpec("block", "str", default="", required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("roof", "str", default="cone", required=False),
        ArgSpec("windows", "bool", default=True, required=False),
        ArgSpec("door", "str", default="south", required=False),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_tower, "round tower at=X,Z r=4 floors=3 roof=cone|hip|gable|dome|flat|none"),
    "battlements": CommandSpec("battlements", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("block", "str", default="", required=False),
        ArgSpec("every", "int", default=2, required=False),
        ArgSpec("height", "int", default=1, required=False),
    ), cmd_battlements, "crenellate wall top frm=A to=B every=2"),
    "bridge": CommandSpec("bridge", (
        ArgSpec("points", "str"),
        ArgSpec("width", "int", default=3, required=False),
        ArgSpec("deck", "str", default="", required=False),
        ArgSpec("palette", "str", default="", required=False),
        ArgSpec("railing", "str", default="", required=False),
        ArgSpec("support", "str", default="", required=False),
        ArgSpec("pier_spacing", "int", default=6, required=False),
        ArgSpec("lamps", "bool", default=True, required=False),
    ), cmd_bridge, "elevated bridge points=x,z;x,z railing=F support=S"),
    "ruin": CommandSpec("ruin", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("amount", "float", default=0.35, required=False),
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("debris", "bool", default=True, required=False),
    ), cmd_ruin, "seeded decay frm=A to=B amount=0.35 debris=true"),
    "lighting": CommandSpec("lighting", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("light", "block", default="minecraft:lantern", required=False),
        ArgSpec("spacing", "int", default=7, required=False),
        ArgSpec("offset", "int", default=0, required=False),
    ), cmd_lighting, "place lights frm=A to=B spacing=7"),
    "caves": CommandSpec("caves", (
        ArgSpec("frm", "coords"), ArgSpec("to", "coords"),
        ArgSpec("scale", "float", default=0.08, required=False),
        ArgSpec("octaves", "int", default=3, required=False),
        ArgSpec("threshold", "float", default=0.6, required=False),
        ArgSpec("seed", "int", default=0, required=False),
        ArgSpec("protect", "int", default=3, required=False),
    ), cmd_caves, "carve 3D-noise caves frm=A to=B threshold=0.6 protect=3"),
    "replace.mix": CommandSpec("replace.mix", (
        ArgSpec("src", "block"), ArgSpec("pattern", "str"),
        ArgSpec("seed", "int", default=0, required=False),
    ), cmd_replace_mix, "weighted replace src=B pattern='3x stone_bricks, mossy_cobblestone'"),
}
