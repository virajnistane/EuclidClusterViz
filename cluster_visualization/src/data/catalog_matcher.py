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


def _chord_to_arcsec(chord_dist: float) -> float:
    return 2 * np.arcsin(min(float(chord_dist), 1.0) / 2) * ARCSEC_PER_RADIAN


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
        galaxy = galaxies.iloc[i]
        row = {role: galaxy[role] for role in roles}
        row.update(
            RA=float(gal_ra[i]),
            DEC=float(gal_dec[i]),
            CATRED_RA=float(catred_ra[j]),
            CATRED_DEC=float(catred_dec[j]),
            PHZ_MEDIAN=float(phz_median[j]) if j < len(phz_median) else np.nan,
            PHZ_MODE=float(phz_mode_1[j]) if j < len(phz_mode_1) else np.nan,
            SEP_ARCSEC=sep,
            MATCH_METHOD="position",
        )
        rows.append(row)

    return CatalogMatchResult(
        catred_scatter=catred_scatter,
        catred_ra=catred_ra,
        catred_dec=catred_dec,
        display_matched_idx=np.array(sorted(display_matched), dtype=int),
        rows=pd.DataFrame(rows, columns=roles + ["RA", "DEC"] + MATCH_COLUMNS),
        overall_nearest_arcsec=overall_nearest_arcsec,
    )


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


def _row_keys(df: pd.DataFrame, key: list) -> pd.Series:
    values = df[key].astype(str) if key == ["SOURCE_ID"] else df[key].round(9)
    return values.apply(tuple, axis=1)


def write_matches(spec, rows: pd.DataFrame) -> Optional[str]:
    """Upsert match rows into the catalog's match file; returns its path.

    Keyed by SOURCE_ID when mapped, else by the galaxy's RA/Dec, so matching the
    same galaxy again (another zoom or pan) replaces its row. Never raises: a
    failed write must not break the plot update that triggered it.
    """
    if rows is None or len(rows) == 0:
        return None
    from astropy.table import Table  # type: ignore[import]

    path = match_file_path(spec)
    key = ["SOURCE_ID"] if "SOURCE_ID" in rows.columns else ["RA", "DEC"]
    try:
        combined = rows
        if os.path.isfile(path):
            existing = Table.read(path).to_pandas()
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
