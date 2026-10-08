"""
NED (NASA/IPAC Extragalactic Database) spectroscopic-redshift handling module.

Loads the NED spec-z cross-match catalog: for each detected cluster, the
galaxies with known spec-z within a radius (e.g. 2 Mpc) and a redshift
window around Z_CLUSTER. This catalog is small and static compared to the
per-tile CATRED/mosaic data, so it is loaded eagerly and kept in memory as a
single pandas DataFrame rather than lazily per-tile.
"""

import os

import numpy as np
import pandas as pd  # type: ignore[import]
from astropy.io import fits  # type: ignore[import]
from astropy.table import Table  # type: ignore[import]

from typing import Any, Optional


class NEDHandler:
    """Handler for the NED spectroscopic-redshift verification catalog."""

    def __init__(self, config: Optional[Any] = None):
        """
        Initialize by eagerly loading the NED catalog if configured.

        Args:
            config: Config instance exposing get_ned_specz_fits(); may be
                None or lack the method, in which case the handler is inert.
        """
        self.config = config
        self.df: Optional[pd.DataFrame] = None
        # Why the catalog is (not) available; shown in the log and next to the filter switch
        self.status = "not configured ([paths] ned_specz_fits is empty)"

        fits_path = None
        if config is not None and hasattr(config, "get_ned_specz_fits"):
            fits_path = config.get_ned_specz_fits()
        self.fits_path = fits_path

        if fits_path and not os.path.isfile(fits_path):
            self.status = f"file not found: {fits_path}"
        elif fits_path:
            try:
                with fits.open(fits_path, mode="readonly", memmap=True) as hdul:
                    self.df = Table(hdul[1].data).to_pandas()
                n_clusters = self.df["ID_UNIQUE_CLUSTER"].nunique()
                self.status = (
                    f"{n_clusters} clusters{self._per_algorithm_counts()}, "
                    f"{len(self.df)} spec-z galaxies"
                )
                print(f"✓ NED spec-z catalog: {self.status} ({fits_path})")
            except Exception as e:
                self.status = f"could not read {fits_path}: {e}"
                self.df = None

        if self.df is None:
            # Configured but unusable is an error worth seeing; not configured is a choice
            prefix = "⚠️  NED spec-z catalog" if fits_path else "NED spec-z catalog"
            print(f"{prefix} unavailable: {self.status}. Spec-z filter and display are off.")

    def _per_algorithm_counts(self) -> str:
        """" (AMICO 91, PZWAV 0)": the filter only keeps clusters of the algorithm on
        screen (DET_CODE_NB: 1 = AMICO, 2 = PZWAV), so say which ones the catalog has."""
        if self.df is None or "DET_CODE_NB" not in self.df.columns:
            return ""
        codes = self.df.groupby("ID_UNIQUE_CLUSTER")["DET_CODE_NB"].first()
        names = {1: "AMICO", 2: "PZWAV"}
        parts = [f"{name} {int((codes == code).sum())}" for code, name in names.items()]
        other = int((~codes.isin(list(names))).sum())
        if other:
            parts.append(f"other {other}")
        return f" ({', '.join(parts)})"

    def is_available(self) -> bool:
        """Return True if a NED catalog was successfully loaded."""
        return self.df is not None

    def get_unique_cluster_ids(self) -> np.ndarray:
        """Return unique ID_UNIQUE_CLUSTER values present in the NED catalog.

        Rows are duplicated per NED galaxy match for the same cluster, so
        this collapses to one entry per cluster.
        """
        if self.df is None:
            return np.array([])
        return self.df["ID_UNIQUE_CLUSTER"].unique()

    def get_all_galaxies(self) -> Optional[pd.DataFrame]:
        """Return the full NED galaxy DataFrame, or None if unavailable."""
        return self.df

    def get_catred_output_path(self) -> Optional[str]:
        """Path to the companion NED-vs-CATRED match FITS file.

        Derived from the configured ned_specz_fits path's stem (extension
        stripped), so a different configured catalog automatically writes to
        a different output file.
        """
        if not self.fits_path:
            return None
        stem, _ext = os.path.splitext(self.fits_path)
        return f"{stem}_catred.fits"

    def write_catred_matches(self, new_rows: pd.DataFrame) -> None:
        """Upsert nearest-CATRED-to-NED match rows into the companion FITS file.

        Keyed by (NED_RA, NED_DEC): a re-render that re-matches a galaxy
        already recorded from an earlier zoom/pan replaces its row rather
        than duplicating it. Never raises - a write failure must not break
        the on-screen render that triggered it.
        """
        output_path = self.get_catred_output_path()
        if not output_path or new_rows is None or len(new_rows) == 0:
            return

        key_cols = ["NED_RA", "NED_DEC"]
        try:
            if os.path.isfile(output_path):
                with fits.open(output_path, mode="readonly", memmap=True) as hdul:
                    existing = Table(hdul[1].data).to_pandas()
            else:
                existing = new_rows.iloc[0:0].copy()

            if not existing.empty:
                new_keys = set(map(tuple, new_rows[key_cols].round(9).to_numpy()))
                existing_keys = existing[key_cols].round(9).apply(tuple, axis=1)
                existing = existing[~existing_keys.isin(new_keys)]

            combined = pd.concat([existing, new_rows], ignore_index=True)
            Table.from_pandas(combined).write(output_path, overwrite=True)
            print(
                f"Debug: NED-nearby-CATRED: wrote {len(new_rows)} match(es) to {output_path} "
                f"({len(combined)} total rows)"
            )
        except Exception as e:
            print(f"Warning: Failed to update NED-nearby-CATRED output file {output_path}: {e}")
