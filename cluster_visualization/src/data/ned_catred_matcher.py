"""
Shared NED-vs-CATRED matching core.

Factored out of callbacks/ned_callbacks.py so the interactive "Load CATRED
near NED" button and the standalone batch script
(scripts/generate_ned_catred_matches.py) share one implementation instead of
two copies that can drift apart. Framework-independent - no Dash imports.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd  # type: ignore[import]

from cluster_visualization.utils.spatial_index import SpatialIndex

ARCSEC_PER_RADIAN = 206264.80625

CLUSTER_COLS = [
    "ID_UNIQUE_CLUSTER",
    "DET_CODE_NB",
    "CROSS_ID_CLUSTER",
    "RA_CLUSTER",
    "DEC_CLUSTER",
    "Z_CLUSTER",
]


@dataclass
class NedCatredMatchResult:
    """Result of matching one group of NED galaxies against loaded CATRED data."""

    catred_scatter: Dict[str, Any]
    catred_ra: np.ndarray
    catred_dec: np.ndarray
    display_matched_idx: np.ndarray  # union of CATRED indices within radius of ANY galaxy - for display
    nearest_rows: pd.DataFrame  # one row per galaxy with a match within radius - for the output file
    overall_nearest_arcsec: float  # closest CATRED source found to any galaxy in the group, for diagnostics


def _chord_to_arcsec(chord_dist: float) -> float:
    return 2 * np.arcsin(min(float(chord_dist), 1.0) / 2) * ARCSEC_PER_RADIAN


def match_ned_to_catred(
    df_in_view: pd.DataFrame,
    catred_handler,
    data: Dict[str, Any],
    radius_arcsec: float,
    catred_masked: bool = True,
    threshold: float = 0.8,
    maglim: float = 24.0,
) -> Optional[NedCatredMatchResult]:
    """Load CATRED tiles covering df_in_view's NED galaxies and match them.

    df_in_view is any subset of the NED catalog with RA/DEC/CLUSTER_COLS/Z
    columns - a pan/zoom viewport slice or a whole-cluster group both work
    identically, since the CATRED-loading bbox is built from the group's own
    RA/DEC extent rather than any external viewport.

    Returns None when there is nothing to match (empty group, non-positive
    radius, or no CATRED points loaded for the resulting bbox).
    """
    if df_in_view is None or len(df_in_view) == 0:
        return None
    if "RA" not in df_in_view.columns or "DEC" not in df_in_view.columns:
        return None

    radius_deg = max(float(radius_arcsec or 0.0), 0.0) / 3600.0
    if radius_deg <= 0:
        return None

    ned_ra = df_in_view["RA"].to_numpy()
    ned_dec = df_in_view["DEC"].to_numpy()

    margin_deg = radius_deg + 0.01
    zoom_data = {
        "ra_min": float(ned_ra.min()) - margin_deg,
        "ra_max": float(ned_ra.max()) + margin_deg,
        "dec_min": float(ned_dec.min()) - margin_deg,
        "dec_max": float(ned_dec.max()) + margin_deg,
    }

    if catred_masked:
        catred_scatter = catred_handler.update_catred_data_with_coverage(
            zoom_data, data, maglim, threshold
        )
    else:
        catred_scatter = catred_handler.update_catred_data_unmasked(
            zoom_data, data, maglim=1000.0
        )

    catred_ra = np.asarray(catred_scatter.get("ra", []), dtype=float)
    catred_dec = np.asarray(catred_scatter.get("dec", []), dtype=float)
    if len(catred_ra) == 0:
        return None

    index = SpatialIndex(catred_ra, catred_dec)

    display_matched: set = set()
    for hits in index.query_multiple_radius(ned_ra, ned_dec, radius_deg):
        display_matched.update(hits.tolist())
    display_matched_idx = np.array(sorted(display_matched))

    phz_median = catred_scatter.get("phz_median", [])
    phz_mode_1 = catred_scatter.get("phz_mode_1", [])
    has_z = "Z" in df_in_view.columns

    rows = []
    overall_nearest_arcsec = float("inf")
    for i in range(len(ned_ra)):
        dist_chord, catred_idx = index.query_nearest(ned_ra[i], ned_dec[i], k=1)
        nearest_arcsec = _chord_to_arcsec(dist_chord)
        overall_nearest_arcsec = min(overall_nearest_arcsec, nearest_arcsec)
        if nearest_arcsec > radius_arcsec:
            continue

        catred_idx = int(catred_idx)
        ned_row = df_in_view.iloc[i]
        row = {col: ned_row[col] for col in CLUSTER_COLS}
        row["RA"] = float(catred_ra[catred_idx])
        row["DEC"] = float(catred_dec[catred_idx])
        row["PHZ_MEDIAN"] = float(phz_median[catred_idx]) if catred_idx < len(phz_median) else np.nan
        row["PHZ_MODE"] = float(phz_mode_1[catred_idx]) if catred_idx < len(phz_mode_1) else np.nan
        row["NED_RA"] = float(ned_ra[i])
        row["NED_DEC"] = float(ned_dec[i])
        row["NED_Z"] = float(ned_row["Z"]) if has_z else np.nan
        rows.append(row)

    columns = CLUSTER_COLS + ["RA", "DEC", "PHZ_MEDIAN", "PHZ_MODE", "NED_RA", "NED_DEC", "NED_Z"]
    nearest_rows = pd.DataFrame(rows, columns=columns)

    return NedCatredMatchResult(
        catred_scatter=catred_scatter,
        catred_ra=catred_ra,
        catred_dec=catred_dec,
        display_matched_idx=display_matched_idx,
        nearest_rows=nearest_rows,
        overall_nearest_arcsec=overall_nearest_arcsec,
    )
