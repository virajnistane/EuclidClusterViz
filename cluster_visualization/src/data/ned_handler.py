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

        fits_path = None
        if config is not None and hasattr(config, "get_ned_specz_fits"):
            fits_path = config.get_ned_specz_fits()

        if fits_path and os.path.isfile(fits_path):
            try:
                with fits.open(fits_path, mode="readonly", memmap=True) as hdul:
                    self.df = Table(hdul[1].data).to_pandas()
                print(f"Debug: NEDHandler loaded {len(self.df)} spec-z rows from {fits_path}")
            except Exception as e:
                print(f"Warning: NEDHandler failed to load {fits_path}: {e}")
                self.df = None

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
