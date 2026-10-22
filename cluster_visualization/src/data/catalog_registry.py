"""
The user's galaxy catalogs: specs persisted per user, catalogs loaded on demand.

Specs live in $XDG_CONFIG_HOME/clusterviz/catalogs.json (~/.config/clusterviz/
by default), written atomically. The file is re-read whenever its mtime changes,
so the background render processes see the catalogs the UI process added.

Framework-independent - no Dash imports.
"""

import json
import os
import re
import threading
from typing import Dict, List, Optional

from loguru import logger

from cluster_visualization.src.data.galaxy_catalog import (
    CatalogSpec,
    GalaxyCatalog,
    find_table,
    inspect_columns,
    suggest_mapping,
    validate_mapping,
)

FILE_VERSION = 1


def default_registry_path() -> str:
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(config_home, "clusterviz", "catalogs.json")


class CatalogRegistry:
    """Add, edit, remove and look up the user's galaxy catalogs."""

    def __init__(self, path: Optional[str] = None, cache_dir: Optional[str] = None):
        self.path = path or default_registry_path()
        self.cache_dir = cache_dir
        self._specs: Dict[str, CatalogSpec] = {}
        self._catalogs: Dict[str, GalaxyCatalog] = {}
        self._mtime: Optional[int] = None
        self._lock = threading.RLock()
        self._refresh()

    # -- persistence ---------------------------------------------------------

    def _refresh(self) -> None:
        """Re-read the file if another process (or an earlier save) changed it."""
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except OSError:
            mtime = None
        if mtime == self._mtime:
            return
        specs: Dict[str, CatalogSpec] = {}
        if mtime is not None:
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("catalogs", []):
                    spec = CatalogSpec.from_dict(item)
                    if spec.id:
                        specs[spec.id] = spec
            except Exception as e:
                logger.warning(f"Could not read galaxy catalog list {self.path}: {e}")
                return
        # Keep loaded catalogs whose spec did not change
        self._catalogs = {
            cid: cat
            for cid, cat in self._catalogs.items()
            if cid in specs and specs[cid] == cat.spec
        }
        self._specs = specs
        self._mtime = mtime

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"version": FILE_VERSION, "catalogs": [s.to_dict() for s in self._specs.values()]},
                f,
                indent=2,
            )
        os.replace(tmp, self.path)
        self._mtime = os.stat(self.path).st_mtime_ns

    # -- queries -------------------------------------------------------------

    def list(self) -> List[CatalogSpec]:
        with self._lock:
            self._refresh()
            return list(self._specs.values())

    def get(self, catalog_id: str) -> Optional[CatalogSpec]:
        with self._lock:
            self._refresh()
            return self._specs.get(catalog_id)

    def catalog(self, catalog_id: str) -> Optional[GalaxyCatalog]:
        """The catalog object (loaded on first data access), or None if unknown."""
        with self._lock:
            self._refresh()
            spec = self._specs.get(catalog_id)
            if spec is None:
                return None
            if catalog_id not in self._catalogs:
                self._catalogs[catalog_id] = GalaxyCatalog(spec, cache_dir=self.cache_dir)
            return self._catalogs[catalog_id]

    def with_capability(self, capability: str) -> List[CatalogSpec]:
        """Specs whose mapping enables ``capability`` (see GalaxyCatalog.capabilities)."""
        return [s for s in self.list() if capability in GalaxyCatalog(s).capabilities()]

    # -- changes -------------------------------------------------------------

    def _new_id(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "catalog"
        cid, n = base, 2
        while cid in self._specs:
            cid, n = f"{base}_{n}", n + 1
        return cid

    def _check_name(self, spec: CatalogSpec, exclude_id: str = "") -> None:
        name = spec.name.strip().lower()
        if any(
            s.name.strip().lower() == name and cid != exclude_id for cid, s in self._specs.items()
        ):
            raise ValueError(f"a catalog named '{spec.name}' already exists")

    def add(self, spec: CatalogSpec) -> str:
        """Save a new catalog; returns its id. Raises ValueError on a duplicate name."""
        with self._lock:
            self._refresh()
            self._check_name(spec)
            spec.id = self._new_id(spec.name)
            self._specs[spec.id] = spec
            self._save()
            logger.info(f"Galaxy catalog added: '{spec.name}' ({spec.path})")
            return spec.id

    def update(self, catalog_id: str, spec: CatalogSpec) -> None:
        with self._lock:
            self._refresh()
            if catalog_id not in self._specs:
                raise ValueError(f"no catalog '{catalog_id}'")
            self._check_name(spec, exclude_id=catalog_id)
            spec.id = catalog_id
            self._specs[catalog_id] = spec
            self._catalogs.pop(catalog_id, None)
            self._save()
            logger.info(f"Galaxy catalog updated: '{spec.name}'")

    def remove(self, catalog_id: str) -> None:
        with self._lock:
            self._refresh()
            spec = self._specs.pop(catalog_id, None)
            self._catalogs.pop(catalog_id, None)
            if spec is not None:
                self._save()
                logger.info(f"Galaxy catalog removed: '{spec.name}'")

    def import_legacy(self, path: Optional[str], name: str = "NED spec-z") -> Optional[str]:
        """One-time import of a catalog set in the old config key ([paths] ned_specz_fits).

        Skipped when the path is empty or already registered, or the suggested
        mapping does not validate. Returns the new id, or None.
        """
        if not path:
            return None
        real = os.path.realpath(path)
        specs = self.list()
        if any(os.path.realpath(s.path) == real for s in specs):
            return None
        try:
            table = find_table(inspect_columns(path), None)
        except ValueError as e:
            logger.warning(f"Not importing legacy catalog {path}: {e}")
            return None
        spec = CatalogSpec(name=name, path=path, columns=suggest_mapping(table), hdu=table.hdu)
        if any(s.name.strip().lower() == name.lower() for s in specs):
            spec.name = f"{name} ({os.path.basename(path)})"
        result = validate_mapping(spec, table)
        if not result.ok:
            logger.warning(f"Not importing legacy catalog {path}: {'; '.join(result.errors)}")
            return None
        cid = self.add(spec)
        logger.info(
            f"Imported '{spec.name}' from the config's ned_specz_fits into {self.path}; "
            "manage it under Galaxy catalogs from now on"
        )
        return cid
