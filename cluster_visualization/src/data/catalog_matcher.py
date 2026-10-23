"""
Match galaxy catalog rows to CATRED sources.

Works on a catalog's standard columns (see galaxy_catalog.py), so any mapped
catalog can be matched. Framework-independent - no Dash imports.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd  # type: ignore[import]
from loguru import logger

from cluster_visualization.src.data.galaxy_catalog import (
    CSV_EXTENSIONS,
    ECSV_EXTENSIONS,
    FITS_EXTENSIONS,
    PARQUET_EXTENSIONS,
    default_cache_dir,
)
from cluster_visualization.utils.spatial_index import SpatialIndex

ARCSEC_PER_RADIAN = 206264.80625

# Catalog roles copied into each match row, when mapped
ROW_ROLES = ("SOURCE_ID", "OBJECT_ID", "CLUSTER_ID", "SPEC_Z", "SPEC_Z_ERR", "PHOT_Z")
MATCH_COLUMNS = ["CATRED_RA", "CATRED_DEC", "PHZ_MEDIAN", "PHZ_MODE", "SEP_ARCSEC", "MATCH_METHOD"]


@dataclass
class CatalogMatchResult:
    """CATRED sources near one group of catalog galaxies."""

    catred_scatter: Dict[str, Any]
    catred_ra: np.ndarray
    catred_dec: np.ndarray
    display_matched_idx: np.ndarray  # CATRED indices within the radius of any galaxy - drawn
    rows: pd.DataFrame  # nearest CATRED source per galaxy that has one within the radius
    overall_nearest_arcsec: float  # closest CATRED source to any galaxy, for the log
    # Per drawn source: row position (in the galaxies passed in) of its catalog galaxy,
    # the nearest one for a position match; gives the spec-z shown with its p(z)
    display_galaxy_idx: Optional[np.ndarray] = None


def _chord_to_arcsec(chord_dist: float) -> float:
    return 2 * np.arcsin(min(float(chord_dist), 1.0) / 2) * ARCSEC_PER_RADIAN


def _separation_arcsec(ra1, dec1, ra2, dec2) -> np.ndarray:
    """Angular separation (haversine), degrees in, arcsec out."""
    ra1, dec1, ra2, dec2 = (np.radians(np.asarray(v, dtype=float)) for v in (ra1, dec1, ra2, dec2))
    h = np.sin((dec2 - dec1) / 2) ** 2 + np.cos(dec1) * np.cos(dec2) * np.sin((ra2 - ra1) / 2) ** 2
    return 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1))) * ARCSEC_PER_RADIAN


def _match_row(galaxy, roles, catred_ra, catred_dec, phz_median, phz_mode, sep, method) -> dict:
    row = {role: galaxy[role] for role in roles}
    row.update(
        RA=float(galaxy["RA"]),
        DEC=float(galaxy["DEC"]),
        CATRED_RA=float(catred_ra),
        CATRED_DEC=float(catred_dec),
        PHZ_MEDIAN=float(phz_median) if phz_median is not None else np.nan,
        PHZ_MODE=float(phz_mode) if phz_mode is not None else np.nan,
        SEP_ARCSEC=float(sep),
        MATCH_METHOD=method,
    )
    return row


def load_catred_around(
    galaxies: pd.DataFrame,
    catred_handler,
    data,
    margin_deg: float,
    catred_masked: bool = True,
    threshold: float = 0.8,
    maglim: float = 24.0,
) -> Dict[str, Any]:
    """CATRED sources in the galaxies' RA/Dec box plus ``margin_deg``.

    The CATRED loaders replace catred_handler.current_catred_data with their own
    flat result; the per-trace click data it held (Members, earlier matches) is
    put back so those markers stay clickable.
    """
    ra, dec = galaxies["RA"].to_numpy(), galaxies["DEC"].to_numpy()
    zoom_data = {
        "ra_min": float(ra.min()) - margin_deg,
        "ra_max": float(ra.max()) + margin_deg,
        "dec_min": float(dec.min()) - margin_deg,
        "dec_max": float(dec.max()) + margin_deg,
    }
    click_data = catred_handler.current_catred_data
    try:
        if catred_masked:
            return catred_handler.update_catred_data_with_coverage(
                zoom_data, data, maglim, threshold
            )
        return catred_handler.update_catred_data_unmasked(zoom_data, data, maglim=1000.0)
    finally:
        catred_handler.current_catred_data = click_data


def match_by_position(
    galaxies: pd.DataFrame,
    catred_handler,
    data,
    radius_arcsec: float,
    catred_masked: bool = True,
    threshold: float = 0.8,
    maglim: float = 24.0,
) -> Optional[CatalogMatchResult]:
    """Match catalog galaxies (standard columns, at least RA/DEC) to CATRED by position.

    Returns None when there is nothing to match (no galaxies, non-positive radius,
    or no CATRED sources loaded around them).
    """
    if galaxies is None or len(galaxies) == 0:
        return None
    radius_deg = max(float(radius_arcsec or 0.0), 0.0) / 3600.0
    if radius_deg <= 0:
        return None

    catred_scatter = load_catred_around(
        galaxies, catred_handler, data, radius_deg + 0.01, catred_masked, threshold, maglim
    )
    catred_ra = np.asarray(catred_scatter.get("ra", []), dtype=float)
    catred_dec = np.asarray(catred_scatter.get("dec", []), dtype=float)
    if len(catred_ra) == 0:
        return None

    gal_ra, gal_dec = galaxies["RA"].to_numpy(), galaxies["DEC"].to_numpy()
    index = SpatialIndex(catred_ra, catred_dec)
    display_matched: set = set()
    for hits in index.query_multiple_radius(gal_ra, gal_dec, radius_deg):
        display_matched.update(hits.tolist())

    phz_median = catred_scatter.get("phz_median", [])
    phz_mode_1 = catred_scatter.get("phz_mode_1", [])
    roles = [r for r in ROW_ROLES if r in galaxies.columns]
    rows = []
    overall_nearest_arcsec = float("inf")
    for i in range(len(gal_ra)):
        dist_chord, j = index.query_nearest(gal_ra[i], gal_dec[i], k=1)
        sep = _chord_to_arcsec(dist_chord)
        overall_nearest_arcsec = min(overall_nearest_arcsec, sep)
        if sep > radius_arcsec:
            continue
        j = int(j)
        rows.append(
            _match_row(
                galaxies.iloc[i],
                roles,
                catred_ra[j],
                catred_dec[j],
                phz_median[j] if j < len(phz_median) else None,
                phz_mode_1[j] if j < len(phz_mode_1) else None,
                sep,
                "position",
            )
        )

    display_idx = np.array(sorted(display_matched), dtype=int)
    galaxy_index = SpatialIndex(gal_ra, gal_dec)
    display_galaxy_idx = np.array(
        [int(galaxy_index.query_nearest(catred_ra[j], catred_dec[j], k=1)[1]) for j in display_idx],
        dtype=int,
    )
    return CatalogMatchResult(
        catred_scatter=catred_scatter,
        catred_ra=catred_ra,
        catred_dec=catred_dec,
        display_matched_idx=display_idx,
        rows=pd.DataFrame(rows, columns=roles + ["RA", "DEC"] + MATCH_COLUMNS),
        overall_nearest_arcsec=overall_nearest_arcsec,
        display_galaxy_idx=display_galaxy_idx,
    )


# Tiles searched around galaxies whose MER tile is unknown (or not where the ID was)
ID_SEARCH_MARGIN_DEG = 0.05


def _merge_lookups(first: Dict[str, Any], second: Dict[str, Any]) -> Dict[str, Any]:
    merged = {}
    for key, values in first.items():
        if isinstance(values, np.ndarray):
            merged[key] = np.concatenate([values, second[key]])
        else:
            merged[key] = list(values) + list(second[key])
    return merged


def match_by_id(galaxies: pd.DataFrame, catred_handler, data) -> Optional[CatalogMatchResult]:
    """Match catalog galaxies to CATRED by OBJECT_ID (exact; no radius, mask or magnitude cut).

    Searches the galaxies' TILE_ID tiles when mapped, then the tiles around the
    galaxies for IDs not found there. Returns None without galaxies or OBJECT_ID;
    a result with no rows when none of the IDs is in CATRED.
    """
    if galaxies is None or len(galaxies) == 0 or "OBJECT_ID" not in galaxies.columns:
        return None
    object_ids = galaxies["OBJECT_ID"].to_numpy(dtype=np.int64)  # integer role: no missing values

    searched = []
    if "TILE_ID" in galaxies.columns:
        searched = [int(t) for t in pd.unique(galaxies["TILE_ID"].dropna())]
    found = catred_handler.lookup_by_object_id(object_ids, data, searched)
    missing = np.setdiff1d(object_ids, found["object_id"])
    if len(missing):
        ra, dec = galaxies["RA"].to_numpy(), galaxies["DEC"].to_numpy()
        m = ID_SEARCH_MARGIN_DEG
        around = catred_handler._find_intersecting_tiles(
            data, ra.min() - m, ra.max() + m, dec.min() - m, dec.max() + m
        )
        others = [t for t in around if t not in set(searched)]
        if others:
            found = _merge_lookups(found, catred_handler.lookup_by_object_id(missing, data, others))

    catred_scatter = {
        key: found[key]
        for key in ("ra", "dec", "phz_pdf", "phz_mode_1", "phz_median", "phz_70_int")
    }
    catred_scatter["ra"], catred_scatter["dec"] = list(found["ra"]), list(found["dec"])
    position = {int(oid): j for j, oid in enumerate(found["object_id"])}

    roles = [r for r in ROW_ROLES if r in galaxies.columns]
    rows, galaxy_of_source = [], {}
    for i, oid in enumerate(object_ids):
        j = position.get(int(oid))
        if j is None:
            continue
        galaxy = galaxies.iloc[i]
        galaxy_of_source.setdefault(j, i)
        sep = _separation_arcsec(galaxy["RA"], galaxy["DEC"], found["ra"][j], found["dec"][j])
        rows.append(
            _match_row(
                galaxy,
                roles,
                found["ra"][j],
                found["dec"][j],
                found["phz_median"][j],
                found["phz_mode_1"][j],
                sep,
                "object_id",
            )
        )

    display_idx = np.arange(len(found["object_id"]), dtype=int)
    return CatalogMatchResult(
        catred_scatter=catred_scatter,
        catred_ra=found["ra"],
        catred_dec=found["dec"],
        display_matched_idx=display_idx,
        rows=pd.DataFrame(rows, columns=roles + ["RA", "DEC"] + MATCH_COLUMNS),
        overall_nearest_arcsec=float("nan"),
        display_galaxy_idx=np.array([galaxy_of_source[j] for j in display_idx], dtype=int),
    )


def spec_z_values(galaxies, galaxy_idx, n) -> dict:
    """{"spec_z", "spec_z_err"}: per matched source, its catalog galaxy's values (None when
    missing); {} when the catalog maps no SPEC_Z."""
    if galaxy_idx is None or "SPEC_Z" not in galaxies.columns or len(galaxy_idx) != n:
        return {}
    out = {}
    for role, key in (("SPEC_Z", "spec_z"), ("SPEC_Z_ERR", "spec_z_err")):
        if role in galaxies.columns:
            values = galaxies[role].to_numpy(dtype=float)[galaxy_idx]
            out[key] = [float(v) if np.isfinite(v) else None for v in values]
    return out


# ---------------------------------------------------------------------------
# Match file
# ---------------------------------------------------------------------------


def file_stem(path: str) -> str:
    name = os.path.basename(path)
    for ext in FITS_EXTENSIONS + CSV_EXTENSIONS + ECSV_EXTENSIONS + PARQUET_EXTENSIONS:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return os.path.splitext(name)[0]


def match_file_path(spec) -> str:
    """Where a catalog's CATRED matches are recorded: next to the catalog when that
    folder is writable, else under ~/.cache/clusterviz_catalogs/matches/."""
    filename = f"{file_stem(spec.path)}_catalogMatches.fits"
    folder = os.path.dirname(os.path.abspath(spec.path))
    if not os.access(folder, os.W_OK):
        folder = os.path.join(default_cache_dir(), "matches")
    return os.path.join(folder, filename)


def match_key(columns) -> list:
    """Columns identifying a match row: the galaxy (SOURCE_ID, else its RA/Dec) and, when
    mapped, its cluster: a catalog may list one galaxy once per cluster (NED does)."""
    key = ["SOURCE_ID"] if "SOURCE_ID" in columns else ["RA", "DEC"]
    return key + (["CLUSTER_ID"] if "CLUSTER_ID" in columns else [])


def _row_keys(df: pd.DataFrame, key: list) -> pd.Series:
    parts = [
        df[c].round(9).astype(str) if pd.api.types.is_float_dtype(df[c]) else df[c].astype(str)
        for c in key
    ]
    return pd.Series(list(zip(*parts)), index=df.index)


def write_matches(spec, rows: pd.DataFrame) -> Optional[str]:
    """Upsert match rows into the catalog's match file; returns its path.

    Keyed by match_key, so matching the same galaxy again (another zoom or pan, or
    the batch script) replaces its row. Never raises: a failed write must not break
    the plot update that triggered it.
    """
    if rows is None or len(rows) == 0:
        return None
    from astropy.table import Table  # type: ignore[import]

    path = match_file_path(spec)
    key = match_key(rows.columns)
    try:
        combined = rows
        if os.path.isfile(path):
            existing = Table.read(path, character_as_bytes=False).to_pandas()
            if list(existing.columns) != list(rows.columns):
                logger.warning(
                    f"Match file {path} has other columns (mapping changed?); starting it again"
                )
            elif len(existing):
                existing = existing[~_row_keys(existing, key).isin(set(_row_keys(rows, key)))]
                combined = pd.concat([existing, rows], ignore_index=True)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        Table.from_pandas(combined).write(path, overwrite=True)
        logger.info(
            f"Catalog '{spec.name}': {len(rows)} CATRED match(es) recorded in {path} ({len(combined)} rows)"
        )
        return path
    except Exception as e:
        logger.warning(f"Catalog '{spec.name}': could not write match file {path}: {e}")
        return None
