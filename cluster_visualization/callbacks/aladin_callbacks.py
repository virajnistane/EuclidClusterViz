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

import pandas as pd
from dash import Input, Output, State, callback_context, no_update


def _within_2fov(ra: float, dec: float, ra_c: float, dec_c: float, fov: float) -> bool:
    """True if (ra, dec) is within 2× FOV radius of (ra_c, dec_c) using great-circle distance."""
    d_ra = (ra - ra_c) * math.cos(math.radians(dec_c))
    d_dec = dec - dec_c
    return math.sqrt(d_ra ** 2 + d_dec ** 2) <= fov


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
             Input("viewport-cluster-count-store", "data")],
            [
                State("algorithm-dropdown", "value"),
                State("cluster-plot", "figure"),
                State("aladin-survey-dropdown", "value"),
            ],
            prevent_initial_call=True,
        )
        def push_overlay_data(mode, vp_store, algorithm, figure, survey):
            # Determine current mode: view-mode-store is authoritative;
            # viewport-cluster-count-store fires only re-trigger when already in aladin mode
            triggered_ids = [t["prop_id"] for t in callback_context.triggered]
            vp_triggered = any("viewport-cluster-count-store" in t for t in triggered_ids)

            if vp_triggered:
                # Pre-load whenever viewport hits exactly 1 cluster (any mode)
                # Data sits in store ready; JS bridge only runs when div is visible
                if not vp_store or vp_store.get("count") != 1:
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
                if isinstance(merged_raw, pd.DataFrame):
                    merged_df = merged_raw
                elif merged_raw is not None:
                    merged_df = pd.DataFrame(merged_raw)
                else:
                    merged_df = None

                if merged_df is not None and len(merged_df) > 0:
                    ra_col = "RIGHT_ASCENSION_CLUSTER"
                    dec_col = "DECLINATION_CLUSTER"
                    if ra_col in merged_df.columns and dec_col in merged_df.columns:
                        vp = overlay.get("viewport")
                        rows = []
                        for _, row in merged_df.iterrows():
                            ra_val = float(row[ra_col])
                            dec_val = float(row[dec_col])
                            if vp:
                                if not _within_2fov(ra_val, dec_val, vp["ra"], vp["dec"], vp["fov"]):
                                    continue
                            entry: Dict[str, Any] = {"ra": ra_val, "dec": dec_val}
                            if "ID_UNIQUE_CLUSTER" in row:
                                entry["name"] = str(row["ID_UNIQUE_CLUSTER"])
                            if "SNR_CLUSTER" in row:
                                entry["SNR"] = float(row["SNR_CLUSTER"])
                            if "Z_CLUSTER" in row:
                                entry["Z"] = float(row["Z_CLUSTER"])
                            rows.append(entry)
                        overlay["clusters"] = rows
                        print(f"[Aladin] Pushed {len(rows)} cluster entries (2×FOV filter)")
            except Exception as exc:
                print(f"[Aladin] Warning: Could not load cluster data: {exc}")

            # --- CATRED ---
            # CATREDHandler.current_catred_data is flat: {"ra": [], "dec": [], ...}
            try:
                catred_data = getattr(self.catred_handler, "current_catred_data", None)
                if isinstance(catred_data, dict):
                    ra_list = catred_data.get("ra", [])
                    dec_list = catred_data.get("dec", [])
                    vp = overlay.get("viewport")
                    rows = []
                    for ra, dec in zip(ra_list, dec_list):
                        ra_f, dec_f = float(ra), float(dec)
                        if vp and not _within_2fov(ra_f, dec_f, vp["ra"], vp["dec"], vp["fov"]):
                            continue
                        rows.append({"ra": ra_f, "dec": dec_f, "name": "CATRED"})
                    overlay["catred"] = rows
                    print(f"[Aladin] Pushed {len(rows)} CATRED entries (2×FOV filter)")
            except Exception as exc:
                print(f"[Aladin] Warning: Could not load CATRED data: {exc}")

            return overlay
