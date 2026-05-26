"""
ESA Sky overlay callbacks.

When the user switches to ESA Sky mode, this module pushes cluster, CATRED,
and HEALPix mask catalog data to the iframe via esasky-overlay-data-store.
The clientside JS bridge in ui_callbacks.py watches that store and calls
postMessage on the ESA Sky iframe.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from dash import Input, Output, State, no_update


class ESASkyCallbacks:
    """Pushes catalog overlay data to the ESA Sky iframe on mode switch."""

    def __init__(self, app, data_loader, catred_handler, mosaic_handler):
        self.app = app
        self.data_loader = data_loader
        self.catred_handler = catred_handler
        self.mosaic_handler = mosaic_handler
        self.setup_callbacks()

    def setup_callbacks(self):
        self._setup_overlay_push_callback()

    def _setup_overlay_push_callback(self):
        """Server-side callback: build catalog JSON for ESA Sky overlay."""

        @self.app.callback(
            Output("esasky-overlay-data-store", "data"),
            [Input("view-mode-store", "data")],
            [State("algorithm-dropdown", "value"),
             State("cluster-plot", "figure")],
            prevent_initial_call=True,
        )
        def push_overlay_data(mode, algorithm, figure):
            if mode != "esasky":
                return no_update

            algorithm = algorithm or "PZWAV"
            overlay: Dict[str, Any] = {"clusters": [], "catred": [], "mask": [], "viewport": None}

            # --- Viewport: extract RA/Dec center + FOV from current Plotly axes ---
            try:
                if figure and "layout" in figure:
                    layout = figure["layout"]
                    xaxis = layout.get("xaxis", {})
                    yaxis = layout.get("yaxis", {})
                    ra_range = xaxis.get("range")
                    dec_range = yaxis.get("range")
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
                        print(f"[ESASky] Viewport: RA={ra_center:.4f} Dec={dec_center:.4f} FOV={fov_deg:.4f}°")
            except Exception as exc:
                print(f"[ESASky] Warning: Could not extract viewport: {exc}")

            # --- Clusters ---
            try:
                data = self.data_loader.load_data(select_algorithm=algorithm)
                merged_raw = data.get("data_detcluster_mergedcat")
                # May be a DataFrame or structured numpy array
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
                        rows = []
                        for _, row in merged_df.iterrows():
                            entry: Dict[str, Any] = {
                                "ra": float(row[ra_col]),
                                "dec": float(row[dec_col]),
                            }
                            if "ID_UNIQUE_CLUSTER" in row:
                                entry["name"] = str(row["ID_UNIQUE_CLUSTER"])
                            if "SNR_CLUSTER" in row:
                                entry["SNR"] = float(row["SNR_CLUSTER"])
                            if "Z_CLUSTER" in row:
                                entry["Z"] = float(row["Z_CLUSTER"])
                            rows.append(entry)
                        overlay["clusters"] = rows
                        print(f"[ESASky] Pushed {len(rows)} cluster overlay entries")
            except Exception as exc:
                print(f"[ESASky] Warning: Could not load cluster data: {exc}")

            # --- CATRED ---
            try:
                catred_data = getattr(self.catred_handler, "current_catred_data", None)
                if catred_data is not None:
                    ra_list = catred_data.get("ra", [])
                    dec_list = catred_data.get("dec", [])
                    rows = []
                    for ra, dec in zip(ra_list, dec_list):
                        rows.append({"ra": float(ra), "dec": float(dec), "name": "CATRED"})
                    overlay["catred"] = rows
                    print(f"[ESASky] Pushed {len(rows)} CATRED overlay entries")
            except Exception as exc:
                print(f"[ESASky] Warning: Could not load CATRED data: {exc}")

            # --- HEALPix mask (centroid of each loaded tile) ---
            try:
                if self.mosaic_handler and hasattr(self.mosaic_handler, "traces_cache"):
                    mask_rows = []
                    for key, info in self.mosaic_handler.traces_cache.items():
                        bounds = info.get("bounds") if isinstance(info, dict) else None
                        if bounds:
                            ra_c = (bounds.get("ra_min", 0) + bounds.get("ra_max", 0)) / 2.0
                            dec_c = (bounds.get("dec_min", 0) + bounds.get("dec_max", 0)) / 2.0
                            mask_rows.append({
                                "ra": float(ra_c),
                                "dec": float(dec_c),
                                "name": f"Tile {key}",
                            })
                    overlay["mask"] = mask_rows
                    print(f"[ESASky] Pushed {len(mask_rows)} mask tile centroids")
            except Exception as exc:
                print(f"[ESASky] Warning: Could not load mask data: {exc}")

            return overlay
