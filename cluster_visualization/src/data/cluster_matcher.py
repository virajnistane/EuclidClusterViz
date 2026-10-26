"""
Cross-match external cluster catalogs (SPT, Planck, ACT, ...) with the Euclid merged clusters.

An external cluster matches a Euclid merged cluster within the catalog's radius
(CatalogSpec.match_radius_arcmin) and, when both have a redshift, within its
redshift tolerance |z_Euclid - z| / (1 + z) <= CatalogSpec.match_dz. Without a
redshift on either side the match is by position only.

Matches are always made against the full merged catalog of the loaded algorithm
(before the sidebar filters), so the matched IDs do not depend on the filters
that use them.

Framework-independent - no Dash imports.
"""

import zlib
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd  # type: ignore[import]

from cluster_visualization.src.data.catalog_matcher import _separation_arcsec

MATCH_COLUMNS = ("EXT_ROW", "EUCLID_ROW", "ID_UNIQUE_CLUSTER", "SEP_ARCMIN", "DZ", "BEST")
# Cross-matches kept per catalog (one per algorithm and setting, most recent last)
CACHE_SIZE = 4


def _empty_matches() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in MATCH_COLUMNS})


def _redshift_offset(z_euclid, z_ext) -> np.ndarray:
    """|z_Euclid - z| / (1 + z); NaN where either redshift is missing."""
    z_euclid = np.asarray(z_euclid, dtype=float)
    z_ext = np.asarray(z_ext, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.abs(z_euclid - z_ext) / (1 + z_ext)


def match_clusters(
    ext: pd.DataFrame, merged: np.ndarray, radius_arcmin: float, dz: float
) -> pd.DataFrame:
    """Pairs (external cluster, Euclid merged cluster) within the radius and the Δz cut.

    Args:
        ext: external clusters under the standard role names (RA, DEC, optional Z)
        merged: Euclid merged catalog (RIGHT_ASCENSION_CLUSTER, DECLINATION_CLUSTER,
            Z_CLUSTER, ID_UNIQUE_CLUSTER)
        radius_arcmin: match radius
        dz: redshift tolerance on |z_Euclid - z| / (1 + z)

    Returns:
        One row per pair: EXT_ROW (index label in ``ext``), EUCLID_ROW (row in
        ``merged``), ID_UNIQUE_CLUSTER, SEP_ARCMIN, DZ (NaN for a position-only
        match) and BEST (the nearest Euclid cluster of each external cluster).
    """
    if ext is None or len(ext) == 0 or merged is None or len(merged) == 0:
        return _empty_matches()
    from cluster_visualization.utils.spatial_index import SpatialIndex

    m_ra = np.asarray(merged["RIGHT_ASCENSION_CLUSTER"], dtype=float)
    m_dec = np.asarray(merged["DECLINATION_CLUSTER"], dtype=float)
    usable = np.flatnonzero(np.isfinite(m_ra) & np.isfinite(m_dec))
    if len(usable) == 0:
        return _empty_matches()
    e_ra = ext["RA"].to_numpy(dtype=float)
    e_dec = ext["DEC"].to_numpy(dtype=float)

    index = SpatialIndex(m_ra[usable], m_dec[usable])
    # A little wider than the radius: the exact separation below makes the cut
    hits = index.query_multiple_radius(e_ra, e_dec, radius_arcmin * 1.001 / 60.0)
    counts = np.fromiter((len(h) for h in hits), dtype=np.int64, count=len(hits))
    if counts.sum() == 0:
        return _empty_matches()
    ext_pos = np.repeat(np.arange(len(ext)), counts)
    euclid_row = usable[np.concatenate(hits)]

    sep = _separation_arcsec(e_ra[ext_pos], e_dec[ext_pos], m_ra[euclid_row], m_dec[euclid_row])
    sep = sep / 60.0
    z_ext = ext["Z"].to_numpy(dtype=float)[ext_pos] if "Z" in ext.columns else np.nan
    offset = _redshift_offset(np.asarray(merged["Z_CLUSTER"], dtype=float)[euclid_row], z_ext)
    offset = np.broadcast_to(offset, sep.shape)
    keep = (sep <= radius_arcmin) & (~np.isfinite(offset) | (offset <= dz))
    if not keep.any():
        return _empty_matches()

    pairs = pd.DataFrame(
        {
            "EXT_ROW": ext.index.to_numpy()[ext_pos[keep]],
            "EUCLID_ROW": euclid_row[keep],
            "ID_UNIQUE_CLUSTER": np.asarray(merged["ID_UNIQUE_CLUSTER"])[euclid_row[keep]],
            "SEP_ARCMIN": sep[keep],
            "DZ": offset[keep],
        }
    ).sort_values(["EXT_ROW", "SEP_ARCMIN"], kind="stable")
    pairs["BEST"] = ~pairs["EXT_ROW"].duplicated()
    return pairs.reset_index(drop=True)


def _merged_key(data: Dict[str, Any]) -> tuple:
    merged = data["data_detcluster_mergedcat"]
    ids = np.ascontiguousarray(np.asarray(merged["ID_UNIQUE_CLUSTER"]))
    return (data.get("algorithm"), len(merged), zlib.crc32(ids.tobytes()))


def cached_matches(catalog, data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """match_clusters for a loaded cluster catalog against ``data``'s merged catalog,
    remembered on the catalog per algorithm and setting. None if the catalog is unavailable."""
    df = catalog.get_all()
    if df is None:
        return None
    spec = catalog.spec
    key = _merged_key(data) + (float(spec.match_radius_arcmin), float(spec.match_dz))
    cache = catalog.match_cache
    if key in cache:
        return cache[key]
    matches = match_clusters(
        df, data["data_detcluster_mergedcat"], float(spec.match_radius_arcmin), float(spec.match_dz)
    )
    cache[key] = matches
    while len(cache) > CACHE_SIZE:
        cache.pop(next(iter(cache)))
    return matches


def matched_cluster_ids(catalog, data: Dict[str, Any]) -> np.ndarray:
    """Unique Euclid merged-cluster IDs with a counterpart in the catalog (empty if none)."""
    matches = cached_matches(catalog, data)
    if matches is None or len(matches) == 0:
        return np.array([], dtype=np.int64)
    return matches["ID_UNIQUE_CLUSTER"].unique()


def match_summary(matches: pd.DataFrame, n_ext: int) -> Dict[str, int]:
    """Counts for feedback: external clusters matched, of them by position only, Euclid clusters."""
    best = matches[matches["BEST"].astype(bool)] if len(matches) else matches
    return {
        "external": int(n_ext),
        "matched": int(len(best)),
        "position_only": (
            int((~np.isfinite(best["DZ"].to_numpy(dtype=float))).sum()) if len(best) else 0
        ),
        "euclid": int(matches["ID_UNIQUE_CLUSTER"].nunique()) if len(matches) else 0,
    }


def counterparts(catalog, ra: float, dec: float, z: Optional[float] = None) -> pd.DataFrame:
    """External clusters within the catalog's radius and Δz cut of one Euclid cluster,
    nearest first, with SEP_ARCMIN and DZ columns. Empty if none or unavailable."""
    df = catalog.get_all()
    if df is None or len(df) == 0 or ra is None or dec is None:
        return pd.DataFrame()
    spec = catalog.spec
    radius = float(spec.match_radius_arcmin)
    idx = catalog.index.query_radius(float(ra), float(dec), radius * 1.001 / 60.0)
    if len(idx) == 0:
        return df.iloc[0:0].assign(SEP_ARCMIN=[], DZ=[])
    rows = df.iloc[idx].copy()
    rows["SEP_ARCMIN"] = (
        _separation_arcsec(ra, dec, rows["RA"].to_numpy(), rows["DEC"].to_numpy()) / 60.0
    )
    z_ext = rows["Z"].to_numpy(dtype=float) if "Z" in rows.columns else np.full(len(rows), np.nan)
    z_euclid = np.nan if z is None else float(z)
    rows["DZ"] = _redshift_offset(np.full(len(rows), z_euclid), z_ext)
    dz = rows["DZ"].to_numpy(dtype=float)
    keep = (rows["SEP_ARCMIN"].to_numpy() <= radius) & (
        ~np.isfinite(dz) | (dz <= float(spec.match_dz))
    )
    return rows[keep].sort_values("SEP_ARCMIN", kind="stable")
