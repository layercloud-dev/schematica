"""Block registry loading from PrismarineJS minecraft-data JSON.

The canonical source is the PrismarineJS/minecraft-data repo, laid out as
``data/pc/<version>/blocks.json``. Each entry looks like::

    {
      "id": 1,
      "name": "minecraft:stone",
      "displayName": "Stone",
      "states": [{"name":"axis","type":"enum","num_values":3,"values":["x","y","z"],"default":"y"}]
    }

This loader reads that JSON from a configurable base directory (default:
``<repo_root>/minecraft_data``). It also ships a tiny fallback catalog so the
package is importable without the submodule vendored.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from .block import AIR, Block

_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)+$")


def _normalize_name(name: str) -> str:
    key = name.strip().lower()
    if ":" not in key:
        key = f"minecraft:{key}"
    return key


@dataclass(frozen=True)
class BlockStateSchema:
    name: str
    type: str
    default: object
    values: tuple[object, ...] = ()
    num_values: int | None = None


@dataclass(frozen=True)
class BlockDef:
    id: int
    name: str
    display_name: str
    states: tuple[BlockStateSchema, ...] = ()
    default_state: int | None = None
    min_state_id: int | None = None

    def default_block(self) -> Block:
        if not self.states:
            return Block(name=self.name)
        pairs = tuple((s.name, s.default) for s in self.states if s.default is not None)
        return Block(name=self.name, states=pairs)


# ---------------------------------------------------------------------------
# Built-in fallback catalog (data-driven).
#
# The full fallback catalog lives in the package data file
# ``schematica/blocks/data/fallback_blocks.json`` so it can be browsed,
# extended, or replaced *without touching Python code*. Set the
# ``SCHEMATICA_FALLBACK_BLOCKS`` environment variable to a JSON file with the
# same layout (``{"format": 1, "states": {...tables...}, "blocks": [...]}``).
# A block entry may reference one or more named state tables whose field lists
# are concatenated. Only a tiny air/stone set is embedded here as a last
# resort so the package stays importable if the data file is missing.
# ---------------------------------------------------------------------------

_EMERGENCY_BLOCKS: list[dict[str, object]] = [
    {"id": 0, "name": "minecraft:air", "displayName": "Air"},
    {"id": 1, "name": "minecraft:stone", "displayName": "Stone"},
    {"id": 2, "name": "minecraft:grass_block", "displayName": "Grass Block"},
    {"id": 3, "name": "minecraft:dirt", "displayName": "Dirt"},
    {"id": 12, "name": "minecraft:sand", "displayName": "Sand"},
    {"id": 20, "name": "minecraft:glass", "displayName": "Glass"},
    {"id": 49, "name": "minecraft:obsidian", "displayName": "Obsidian"},
    {"id": 89, "name": "minecraft:glowstone", "displayName": "Glowstone"},
]

_DEFAULT_FALLBACK_JSON = Path(__file__).resolve().parent / "data" / "fallback_blocks.json"


def _load_fallback_blocks() -> list[dict[str, object]]:
    """Load the fallback catalog from JSON (env override > bundled data file)."""
    import os

    env = os.environ.get("SCHEMATICA_FALLBACK_BLOCKS")
    path = Path(env) if env else _DEFAULT_FALLBACK_JSON
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        tables = raw.get("states", {})
        blocks: list[dict[str, object]] = []
        for entry in raw.get("blocks", []):
            if not isinstance(entry, dict):
                continue
            d = dict(entry)
            refs = d.pop("states", None)
            if refs:
                merged: list[dict[str, object]] = []
                for ref in refs:
                    tbl = tables.get(ref)
                    if tbl is None:
                        raise ValueError(f"fallback catalog: unknown state table '{ref}'")
                    merged.extend(tbl)
                d["states"] = merged
            blocks.append(d)
        if blocks:
            return blocks
    except Exception:
        pass  # keep the package importable even if the data file is broken
    return list(_EMERGENCY_BLOCKS)


_FALLBACK_BLOCKS: list[dict[str, object]] = _load_fallback_blocks()


def fallback_blocks() -> list[dict[str, object]]:
    """Return the raw fallback catalog entries (as loaded from JSON)."""
    return _FALLBACK_BLOCKS


def _parse_state_schema(raw: dict[str, object]) -> BlockStateSchema:
    values_raw = raw.get("values", [])
    if isinstance(values_raw, list):
        values = tuple(values_raw)
    else:
        values = ()
    return BlockStateSchema(
        name=str(raw["name"]),
        type=str(raw.get("type", "enum")),
        default=raw.get("default"),
        values=values,
        num_values=int(raw["num_values"]) if "num_values" in raw else None,
    )


def _parse_block_def(raw: dict[str, object]) -> BlockDef:
    states_raw = raw.get("states", [])
    states: tuple[BlockStateSchema, ...] = ()
    if isinstance(states_raw, list):
        states = tuple(_parse_state_schema(s) for s in states_raw if isinstance(s, dict))
    return BlockDef(
        id=int(raw["id"]),  # type: ignore[call-overload]
        name=_normalize_name(str(raw["name"])),
        display_name=str(raw.get("displayName", raw["name"])),
        states=states,
        default_state=int(raw["defaultState"]) if "defaultState" in raw else None,
        min_state_id=int(raw["minStateId"]) if "minStateId" in raw else None,
    )


def _coerce_state_value(schema: BlockStateSchema, value: object) -> object:
    match schema.type:
        case "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                low = value.lower()
                if low == "true":
                    return True
                if low == "false":
                    return False
            raise ValueError(f"state '{schema.name}' expects true or false, got {value!r}")
        case "int":
            if isinstance(value, bool):
                raise ValueError(f"state '{schema.name}' expects an integer, got {value!r}")
            try:
                return int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError) as e:
                raise ValueError(f"state '{schema.name}' expects an integer, got {value!r}") from e
        case "enum":
            return str(value).lower() if isinstance(value, str) else value
        case _:
            return str(value).lower() if isinstance(value, str) else value


def _validate_state_value(block_name: str, schema: BlockStateSchema, value: object,
                          version: str) -> object:
    value = _coerce_state_value(schema, value)
    if schema.values:
        if schema.type == "int":
            try:
                allowed_ints = [int(v) for v in schema.values]
                if value in allowed_ints:
                    return value
            except (ValueError, TypeError):
                pass
        if value not in schema.values:
            allowed = ", ".join(str(v) for v in schema.values[:12])
            suffix = "..." if len(schema.values) > 12 else ""
            raise ValueError(
                f"Block {block_name} state '{schema.name}'={value!r} is invalid for "
                f"version {version}; expected one of: {allowed}{suffix}"
            )
    return value


def _validate_states(block_def: BlockDef, states: tuple[tuple[str, object], ...],
                     version: str) -> tuple[tuple[str, object], ...]:
    schemas = {s.name: s for s in block_def.states}
    validated: list[tuple[str, object]] = []
    seen: set[str] = set()
    for key, value in states:
        if key in seen:
            raise ValueError(f"Block {block_def.name} repeats state '{key}' in version {version}")
        seen.add(key)
        schema = schemas.get(key)
        if schema is None:
            if not schemas:
                raise ValueError(
                    f"Block {block_def.name} has no known states in version {version}; "
                    f"cannot accept explicit state '{key}'"
                )
            raise ValueError(
                f"Block {block_def.name} has no state '{key}' in version {version}"
            )
        validated.append((key, _validate_state_value(block_def.name, schema, value, version)))
    return tuple(validated)


class BlockRegistry:
    """Versioned block catalog.

    Usage::

        reg = BlockRegistry.for_version("1.20.1")
        reg["minecraft:stone"]  # -> BlockDef
        reg.validate(Block.parse("minecraft:oak_log[axis=y]"))
    """

    def __init__(self, version: str, blocks: list[BlockDef]) -> None:
        self.version = version
        self._by_name: dict[str, BlockDef] = {}
        self._by_id: dict[int, BlockDef] = {}
        used_ids: set[int] = set()
        next_synthetic_id = max((b.id for b in blocks), default=-1) + 1
        for block_def in blocks:
            name = _normalize_name(block_def.name)
            bd = block_def if block_def.name == name else replace(block_def, name=name)
            if name in self._by_name:
                # Prefer the first definition so fallback duplicates cannot
                # overwrite known legacy ids such as glowstone=89 or obsidian=49.
                continue
            if bd.id in used_ids:
                while next_synthetic_id in used_ids:
                    next_synthetic_id += 1
                bd = replace(bd, id=next_synthetic_id)
                next_synthetic_id += 1
            self._by_name[name] = bd
            self._by_id[bd.id] = bd
            used_ids.add(bd.id)

    @classmethod
    @lru_cache(maxsize=16)
    def for_version(cls, version: str, data_root: str | Path | None = None) -> BlockRegistry:
        root = Path(data_root) if data_root else _default_data_root()
        path = root / "data" / "pc" / version / "blocks.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                raw_list = json.load(fh)
            blocks = [_parse_block_def(r) for r in raw_list if isinstance(r, dict)]
        else:
            blocks = [_parse_block_def(r) for r in _FALLBACK_BLOCKS]
        return cls(version=version, blocks=blocks)

    def __getitem__(self, name: str) -> BlockDef:
        key = _normalize_name(name)
        if key not in self._by_name:
            raise KeyError(f"Unknown block '{name}' for version {self.version}")
        return self._by_name[key]

    def by_id(self, block_id: int) -> BlockDef:
        return self._by_id[block_id]

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return _normalize_name(name) in self._by_name

    def validate(self, block: Block) -> Block:
        bd = self[block.name]
        _validate_states(bd, block.states, self.version)
        return block

    def resolve(self, block: Block, *, strict: bool = True) -> Block:
        """Validate and fill defaults: returns a Block with all states explicit."""
        bd = self[block.name]
        if not bd.states:
            if strict:
                _validate_states(bd, block.states, self.version)
            return Block(name=bd.name)

        explicit = dict(block.states)
        if strict:
            explicit = dict(_validate_states(bd, block.states, self.version))

        unflattened_defaults = {}
        if bd.default_state is not None and bd.min_state_id is not None:
            offset = bd.default_state - bd.min_state_id
            if offset >= 0:
                for s in reversed(bd.states):
                    n = len(s.values) if s.values else s.num_values if s.num_values is not None else 2 if s.type == "bool" else 1
                    if n <= 0:
                        n = 1

                    val_idx = offset % n
                    if s.values:
                        val = s.values[val_idx]
                    elif s.type == "bool":
                        val = [True, False][val_idx]
                    elif s.type == "int":
                        val = val_idx
                    else:
                        val = ""

                    unflattened_defaults[s.name] = val
                    offset = offset // n

        for s in bd.states:
            if s.name not in explicit:
                if s.default is None:
                    if s.name in unflattened_defaults:
                        explicit[s.name] = unflattened_defaults[s.name]
                    else:
                        match s.type:
                            case "bool":
                                explicit[s.name] = False
                            case "int":
                                try:
                                    explicit[s.name] = int(s.values[0]) if s.values else 0
                                except (ValueError, TypeError):
                                    explicit[s.name] = s.values[0] if s.values else "0"
                            case "enum":
                                explicit[s.name] = s.values[0] if s.values else ""
                            case _:
                                explicit[s.name] = s.values[0] if s.values else ""
                else:
                    explicit[s.name] = s.default
            elif strict:
                explicit[s.name] = _validate_state_value(bd.name, s, explicit[s.name], self.version)
        return Block(name=bd.name, states=tuple(sorted(explicit.items())))

    def search(self, query: str, limit: int = 50) -> list[BlockDef]:
        q = query.lower()
        return [b for b in self._by_name.values() if q in b.name or q in b.display_name.lower()][:limit]

    def all(self) -> list[BlockDef]:
        return list(self._by_name.values())

    @staticmethod
    def list_versions(data_root: str | Path | None = None) -> list[str]:
        root = Path(data_root) if data_root else _default_data_root()
        pc = root / "data" / "pc"
        if not pc.exists():
            return []
        out: list[str] = []
        for p in pc.iterdir():
            if p.is_dir() and _VERSION_DIR_RE.match(p.name) and (p / "blocks.json").exists():
                out.append(p.name)
        return sorted(out, key=lambda v: tuple(int(x) for x in v.split(".")))


def _default_data_root() -> Path:
    """Locate the minecraft-data tree: env var > repo/skill root > scripts dir > fallback."""
    import os

    env = os.environ.get("SCHEMATICA_MINECRAFT_DATA")
    if env:
        return Path(env)
    scripts_root = Path(__file__).resolve().parent.parent.parent
    for cand in (scripts_root.parent / "minecraft_data", scripts_root / "minecraft_data"):
        if cand.exists():
            return cand
    return Path()  # triggers fallback in for_version


def air() -> Block:
    return AIR
