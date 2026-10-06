"""Helpers for loading bundled JSON data files with env overrides.

Env-sensitive resolution happens *before* the cache lookup, and the cache is
keyed on the resolved absolute path -- so setting an env var after the module
was imported still takes effect (a fresh path -> fresh read).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import package_data_dir


@lru_cache(maxsize=64)
def _read_json(path_str: str) -> Any:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def data_path(filename: str, env_var: str | None = None) -> Path:
    """Resolve a data resource to its on-disk path (env override > bundled)."""
    if env_var:
        env = os.environ.get(env_var, "").strip()
        if env:
            return Path(env).resolve()
    return (package_data_dir() / filename).resolve()


def load_json_resource(filename: str, env_var: str | None = None) -> Any:
    """Load a JSON resource from ``schematica/data`` (or an env-specified path).

    Raises ``FileNotFoundError`` when neither the override nor the bundled
    file exists. Call ``clear_resource_cache()`` after replacing a file on
    disk in long-lived processes/tests.
    """
    return _read_json(str(data_path(filename, env_var)))


def clear_resource_cache() -> None:
    _read_json.cache_clear()


# Backwards-compatible shim used by tests.
def cache_clear() -> None:  # pragma: no cover - trivial
    _read_json.cache_clear()

load_json_resource.cache_clear = clear_resource_cache  # type: ignore[attr-defined]
