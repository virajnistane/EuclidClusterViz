"""
Aladin Lite overlay callbacks.

When the user switches to Aladin mode, this module pushes cluster and CATRED
catalog data to aladin-overlay-data-store.  The clientside JS bridge in
ui_callbacks.py watches that store, lazy-loads Aladin Lite v3 from CDN, and
renders the data.  The HEALPix detection mask is added as a HiPS overlay
image layer directly in JS (no server-side data needed).
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dash import Input, Output, State, callback_context, no_update


def _within_2fov(ra: float, dec: float, ra_c: float, dec_c: float, fov: float) -> bool:
    """True if (ra, dec) is within 2× FOV radius of (ra_c, dec_c) using great-circle distance."""
    d_ra = (ra - ra_c) * math.cos(math.radians(dec_c))
    d_dec = dec - dec_c
    return math.sqrt(d_ra ** 2 + d_dec ** 2) <= fov


def _filter_within_2fov_vectorized(
    ra_arr: np.ndarray, dec_arr: np.ndarray, ra_c: float, dec_c: float, fov: float
) -> np.ndarray:
    """Vectorized 2×FOV filter. Returns boolean mask."""
    cos_dec = math.cos(math.radians(dec_c))
    d_ra = (ra_arr - ra_c) * cos_dec
    d_dec = dec_arr - dec_c
    return np.sqrt(d_ra ** 2 + d_dec ** 2) <= fov


class AladinCallbacks:
    """Pushes catalog overlay data to Aladin Lite on mode switch."""

    def __init__(self, app, data_loader, catred_handler):
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.setup_callbacks()

    def setup_callbacks(self):
        self._setup_overlay_push_callback()

    def _setup_overlay_push_callback(self):
        """Server-side callback: build catalog JSON for Aladin Lite overlay."""

        @self.app.callback(
            Output("aladin-overlay-data-store", "data"),
            [Input("view-mode-store", "data"),
             Input("viewport-cluster-count-store", "data"),
             Input("catred-ready-store", "data")],
            [
                State("algorithm-dropdown", "value"),
                State("cluster-plot", "figure"),
                State("aladin-survey-dropdown", "value"),
                State("snr-range-slider-pzwav", "value"),
                State("snr-range-slider-amico", "value"),
                State("redshift-range-slider", "value"),
            ],
            prevent_initial_call=True,
        )
        def push_overlay_data(mode, vp_store, catred_ready, algorithm, figure, survey,
                              snr_range_pzwav, snr_range_amico, redshift_range):
            # Determine current mode: view-mode-store is authoritative;
            # viewport-cluster-count-store fires only re-trigger when already in aladin mode
            triggered_ids = [t["prop_id"] for t in callback_context.triggered]
            vp_triggered = any("viewport-cluster-count-store" in t for t in triggered_ids)
            # catred-ready-store fires only after background render completes — data is guaranteed ready
            catred_triggered = any("catred-ready-store" in t for t in triggered_ids)

            if vp_triggered:
                # Pre-load whenever viewport hits exactly 1 cluster (any mode)
                # Data sits in store ready; JS bridge only runs when div is visible
                if not vp_store or vp_store.get("count") != 1:
                    return no_update
            elif catred_triggered:
                if not catred_ready:
                    return no_update
                # Re-push after CATRED render only when in aladin mode or <=1 cluster
                in_aladin = mode == "aladin"
                at_single_cluster = vp_store and vp_store.get("count") == 1
                if not (in_aladin or at_single_cluster):
                    return no_update
            else:
                if mode != "aladin":
                    return no_update

            algorithm = algorithm or "PZWAV"
            survey = survey or "P/DSS2/color"
            overlay: Dict[str, Any] = {
                "clusters": [],
                "catred": [],
                "viewport": None,
                "survey": survey,
            }

            # --- Viewport: prefer vp_store (has latest relayoutData ranges), fall back to figure ---
            try:
                ra_range = None
                dec_range = None
                if vp_store and vp_store.get("ra") and vp_store.get("dec"):
                    ra_range = vp_store["ra"]
                    dec_range = vp_store["dec"]
                elif figure and "layout" in figure:
                    layout = figure["layout"]
                    ra_range = layout.get("xaxis", {}).get("range")
                    dec_range = layout.get("yaxis", {}).get("range")

                if ra_range and dec_range and len(ra_range) == 2 and len(dec_range) == 2:
                    ra_min, ra_max = float(ra_range[0]), float(ra_range[1])
                    dec_min, dec_max = float(dec_range[0]), float(dec_range[1])
                    ra_center = (ra_min + ra_max) / 2.0
                    dec_center = (dec_min + dec_max) / 2.0
                    fov_deg = max(abs(ra_max - ra_min), abs(dec_max - dec_min))
                    overlay["viewport"] = {
                        "ra": ra_center,
                        "dec": dec_center,
                        "fov": fov_deg,
                    }
                    print(f"[Aladin] Viewport: RA={ra_center:.4f} Dec={dec_center:.4f} FOV={fov_deg:.4f}°")
            except Exception as exc:
                print(f"[Aladin] Warning: Could not extract viewport: {exc}")

            # --- Clusters ---
            try:
                data = self.data_loader.load_data(select_algorithm=algorithm)
                merged_raw = data.get("data_detcluster_mergedcat")

                ra_col = "RIGHT_ASCENSION_CLUSTER"
                dec_col = "DECLINATION_CLUSTER"

                # Extract columns as native-endian float64 — works for both DataFrame and
                # numpy structured arrays from FITS (which are big-endian on most systems).
                # .astype(np.float64) always produces a native-endian copy, avoiding the
                # "Big-endian buffer not supported" error from pandas/Arrow internals.
                def _col_f64(src, name):
                    if isinstance(src, pd.DataFrame):
                        return src[name].to_numpy().astype(np.float64)
                    return src[name].astype(np.float64)  # numpy structured array field

                def _col_str(src, name):
                    if isinstance(src, pd.DataFrame):
                        return src[name].astype(str).to_numpy()
                    return src[name].astype(str)

                def _has_col(src, name):
                    if isinstance(src, pd.DataFrame):
                        return name in src.columns
                    return name in (src.dtype.names or [])

                if merged_raw is not None and len(merged_raw) > 0 and _has_col(merged_raw, ra_col):
                    vp = overlay.get("viewport")
                    ra_arr = _col_f64(merged_raw, ra_col)
                    dec_arr = _col_f64(merged_raw, dec_col)
                    if vp:
                        mask = _filter_within_2fov_vectorized(
                            ra_arr, dec_arr, vp["ra"], vp["dec"], vp["fov"]
                        )
                        ra_arr = ra_arr[mask]
                        dec_arr = dec_arr[mask]
                        sub = merged_raw[mask] if isinstance(merged_raw, np.ndarray) else merged_raw.iloc[mask.nonzero()[0]]
                    else:
                        sub = merged_raw
                    # SNR filter — use PZWAV or AMICO range depending on algorithm
                    snr_range = snr_range_pzwav if (algorithm or "PZWAV") == "PZWAV" else snr_range_amico
                    if _has_col(sub, "SNR_CLUSTER") and snr_range and len(snr_range) == 2:
                        snr_sub = _col_f64(sub, "SNR_CLUSTER")
                        snr_mask = (snr_sub >= float(snr_range[0])) & (snr_sub <= float(snr_range[1]))
                        ra_arr = ra_arr[snr_mask]
                        dec_arr = dec_arr[snr_mask]
                        sub = sub[snr_mask] if isinstance(sub, np.ndarray) else sub.iloc[snr_mask.nonzero()[0]]

                    # Redshift filter
                    if _has_col(sub, "Z_CLUSTER") and redshift_range and len(redshift_range) == 2:
                        z_sub = _col_f64(sub, "Z_CLUSTER")
                        z_mask = (z_sub >= float(redshift_range[0])) & (z_sub <= float(redshift_range[1]))
                        ra_arr = ra_arr[z_mask]
                        dec_arr = dec_arr[z_mask]
                        sub = sub[z_mask] if isinstance(sub, np.ndarray) else sub.iloc[z_mask.nonzero()[0]]

                    has_name = _has_col(sub, "ID_UNIQUE_CLUSTER")
                    has_snr = _has_col(sub, "SNR_CLUSTER")
                    has_z = _has_col(sub, "Z_CLUSTER")
                    name_arr = _col_str(sub, "ID_UNIQUE_CLUSTER") if has_name else None
                    snr_arr = _col_f64(sub, "SNR_CLUSTER") if has_snr else None
                    z_arr = _col_f64(sub, "Z_CLUSTER") if has_z else None
                    rows = []
                    for i in range(len(ra_arr)):
                        entry: Dict[str, Any] = {"ra": float(ra_arr[i]), "dec": float(dec_arr[i])}
                        if has_name:
                            entry["name"] = name_arr[i]
                        if has_snr:
                            entry["SNR"] = float(snr_arr[i])
                        if has_z:
                            entry["Z"] = float(z_arr[i])
                        rows.append(entry)
                    overlay["clusters"] = rows
                    print(f"[Aladin] Pushed {len(rows)} cluster entries (2×FOV filter)")
            except Exception as exc:
                import traceback
                print(f"[Aladin] Warning: Could not load cluster data: {exc}")
                traceback.print_exc()

            # --- CATRED ---
            # current_catred_data is either:
            #   flat:   {"ra": [...], "dec": [...], ...}           (from catred_handler._clip_to_viewport)
            #   nested: {trace_name: {"ra": [...], "dec": [...]}}  (from traces.py _add_manual_catred_traces)
            # Handle both formats.
            try:
                # Background render runs in a separate worker process — in-process attribute is None.
                # Read from shared diskcache written by _persist_aladin_catred().
                catred_data = None
                try:
                    import diskcache as _dc
                    import os as _os
                    _state_dir = _os.path.join(_os.path.expanduser("~"), ".cache", "clusterviz_state")
                    with _dc.Cache(_state_dir) as _sc:
                        catred_data = _sc.get("catred_aladin_data")
                except Exception as _ce:
                    print(f"[Aladin] diskcache read failed: {_ce}")
                # Fallback to in-process attribute (single-process dev mode)
                if catred_data is None:
                    catred_data = getattr(self.catred_handler, "current_catred_data", None)
                print(f"[Aladin] CATRED data source: {'diskcache' if catred_data else 'none'}, type={type(catred_data).__name__}, ra_len={len(catred_data.get('ra',[])) if isinstance(catred_data,dict) and 'ra' in catred_data else 'N/A'}")
                if isinstance(catred_data, dict):
                    if "ra" in catred_data:
                        # flat format (from _clip_to_viewport / _persist_aladin_catred)
                        ra_list = catred_data.get("ra", [])
                        dec_list = catred_data.get("dec", [])
                    else:
                        # nested format — merge all trace entries
                        ra_list, dec_list = [], []
                        for entry in catred_data.values():
                            if isinstance(entry, dict):
                                ra_list.extend(entry.get("ra", []))
                                dec_list.extend(entry.get("dec", []))
                    if len(ra_list) > 0:
                        ra_arr = np.asarray(ra_list).astype(np.float64)
                        dec_arr = np.asarray(dec_list).astype(np.float64)
                        vp = overlay.get("viewport")
                        if vp:
                            mask = _filter_within_2fov_vectorized(
                                ra_arr, dec_arr, vp["ra"], vp["dec"], vp["fov"]
                            )
                            ra_arr = ra_arr[mask]
                            dec_arr = dec_arr[mask]
                        rows = [
                            {"ra": float(r), "dec": float(d), "name": "CATRED"}
                            for r, d in zip(ra_arr, dec_arr)
                        ]
                        overlay["catred"] = rows
                        print(f"[Aladin] Pushed {len(rows)} CATRED entries (2×FOV filter)")
            except Exception as exc:
                print(f"[Aladin] Warning: Could not load CATRED data: {exc}")

            return overlay
