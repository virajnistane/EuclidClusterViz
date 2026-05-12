"""CATRED proximity detection and glow-trace utilities for cluster visualization.

Extracted from traces.py so that TraceCreator is focused on trace construction.

The :class:`CatredProximityDetector` class encapsulates all caching and detection
state, replacing four instance attributes that were previously scattered across
``TraceCreator``:

* ``_catred_bounds_cache``
* ``_subsampled_catred_cache``
* ``_catred_index_hash``
* ``catred_spatial_index``

The :func:`create_glow_trace` function is a pure, stateless helper that was
previously a bound method of ``TraceCreator``.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objs as go

try:
    from cluster_visualization.utils.spatial_index import CATREDSpatialIndex

    SPATIAL_INDEX_AVAILABLE = True
except ImportError:
    print("Warning: Spatial indexing not available - using fallback proximity detection")
    SPATIAL_INDEX_AVAILABLE = False


class CatredProximityDetector:
    """Encapsulates CATRED proximity detection with caching.

    Holds all state needed for both the fast (spatial-index) and legacy
    (bounding-box + linear-scan) proximity checks so that ``TraceCreator``
    does not need to manage any of these attributes itself.
    """

    def __init__(self) -> None:
        # Bounding-box cache used by the legacy per-point check
        self._bounds_cache: Optional[Dict[str, Any]] = None
        # Subsampled-points cache (avoids re-subsampling on every call)
        self._subsampled_cache: Optional[Tuple[int, List]] = None
        # Hash of the CATRED points used to build the current spatial index
        self._index_hash: Optional[int] = None
        # The spatial index itself (built lazily, rebuilt when data changes)
        self._spatial_index: Optional[Any] = None

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all internal caches (call when CATRED data is fully removed)."""
        self._bounds_cache = None
        self._subsampled_cache = None
        self._index_hash = None
        self._spatial_index = None
        print("Debug: CatredProximityDetector: all caches cleared")

    def clear_bounds_cache(self) -> None:
        """Clear only the bounds cache (call when new CATRED data arrives)."""
        if self._bounds_cache is not None:
            self._bounds_cache = None
            print("Debug: Cleared old CATRED bounds cache for new data")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_proximity_batch(
        self,
        ra_array: np.ndarray,
        dec_array: np.ndarray,
        catred_points: List,
    ) -> np.ndarray:
        """Return a boolean mask: ``True`` where a cluster is near CATRED data.

        Automatically selects the fast spatial-index path when the index is
        available and the CATRED dataset is large (> 1 000 points), falling back
        to the legacy per-point scan otherwise — preserving the original branching
        logic that lived inside ``_create_tile_traces_and_polygons`` and
        ``_add_merged_cluster_trace``.

        Args:
            ra_array:      Cluster right-ascension coordinates.
            dec_array:     Cluster declination coordinates.
            catred_points: List of ``(ra, dec)`` CATRED source positions.

        Returns:
            Boolean numpy array of length ``len(ra_array)``.
        """
        if SPATIAL_INDEX_AVAILABLE and len(catred_points) > 1000:
            print(
                f"Using spatial index for proximity detection with {len(catred_points):,} CATRED points"
            )
            return self._check_with_spatial_index(ra_array, dec_array, catred_points)
        else:
            print(
                f"Using legacy proximity detection ({len(catred_points):,} CATRED points)"
            )
            return np.array(
                [
                    self._check_single_legacy(ra, dec, catred_points)
                    for ra, dec in zip(ra_array, dec_array)
                ],
                dtype=bool,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_subsampled_points(self, catred_points: List) -> List:
        """Return (possibly subsampled) CATRED points, with caching.

        For datasets larger than 20 000 points every 5th point is kept to
        reduce the cost of the legacy O(N) scan.
        """
        if not catred_points:
            return catred_points

        catred_hash = hash(
            str(len(catred_points)) + str(catred_points[0] if catred_points else "")
        )

        if self._subsampled_cache is not None:
            cached_hash, cached_points = self._subsampled_cache
            if cached_hash == catred_hash:
                return cached_points

        if len(catred_points) > 20000:
            sampled_points = catred_points[::5]
            print(
                f"Debug: Subsampled {len(sampled_points)} from {len(catred_points)} CATRED points for proximity"
            )
        else:
            sampled_points = catred_points

        self._subsampled_cache = (catred_hash, sampled_points)
        return sampled_points

    def _check_with_spatial_index(
        self,
        ra_array: np.ndarray,
        dec_array: np.ndarray,
        catred_points: List,
        proximity_threshold: float = 0.1,
    ) -> np.ndarray:
        """Proximity check using a KD-tree spatial index — O(N log M).

        The index is built once per unique CATRED dataset and reused on
        subsequent calls.
        """
        start_time = time.time()

        catred_array = np.array(catred_points)
        catred_hash = hash(tuple(catred_array.flatten()[:1000]))

        if self._spatial_index is None or self._index_hash != catred_hash:
            print(f"Building spatial index for {len(catred_points):,} CATRED points...")
            self._spatial_index = CATREDSpatialIndex(
                catred_array[:, 0],
                catred_array[:, 1],
                subsample_threshold=100000,
            )
            self._index_hash = catred_hash

        is_near = np.zeros(len(ra_array), dtype=bool)
        for i, (ra, dec) in enumerate(zip(ra_array, dec_array)):
            is_near[i] = self._spatial_index.check_proximity_single(
                ra, dec, proximity_threshold
            )

        elapsed = time.time() - start_time
        n_near = int(np.sum(is_near))
        print(
            f"Proximity check completed: {n_near:,}/{len(ra_array):,} clusters near CATRED data ({elapsed:.2f}s)"
        )
        return is_near

    def _check_single_legacy(
        self,
        ra: float,
        dec: float,
        catred_points: List,
        proximity_threshold: float = 0.01,
    ) -> bool:
        """Check whether a single point is near any CATRED position — O(N).

        Uses a bounding-box pre-filter to skip the expensive distance loop
        for points that are clearly outside the CATRED footprint.

        This is the legacy fallback used when the spatial index is unavailable
        or the dataset is small.
        """
        if not catred_points:
            return False

        sampled_points = self.get_subsampled_points(catred_points)

        points_to_hash = sampled_points[:100] if len(sampled_points) > 100 else sampled_points
        catred_points_hash = hash(tuple(points_to_hash))

        if (
            self._bounds_cache is None
            or self._bounds_cache.get("hash") != catred_points_hash
        ):
            catred_array = np.array(sampled_points)
            self._bounds_cache = {
                "ra_min": np.min(catred_array[:, 0]) - proximity_threshold,
                "ra_max": np.max(catred_array[:, 0]) + proximity_threshold,
                "dec_min": np.min(catred_array[:, 1]) - proximity_threshold,
                "dec_max": np.max(catred_array[:, 1]) + proximity_threshold,
                "hash": catred_points_hash,
            }
            print(
                f"Debug: CATRED bounds cache created/updated - {len(sampled_points)} sampled points, hash: {catred_points_hash}"
            )

        bounds = self._bounds_cache
        if not (
            bounds["ra_min"] <= ra <= bounds["ra_max"]
            and bounds["dec_min"] <= dec <= bounds["dec_max"]
        ):
            return False

        for catred_ra, catred_dec in sampled_points:
            distance_sq = (ra - catred_ra) ** 2 + (dec - catred_dec) ** 2
            if distance_sq <= proximity_threshold**2:
                return True

        return False


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------


def create_glow_trace(
    x_coords,
    y_coords,
    size: int,
    shape: str = "square",
    opacity: float = 0.3,
    showlegend: bool = False,
    name: str = "",
) -> go.Scattergl:
    """Create a semi-transparent halo trace for cluster markers near CATRED data.

    The returned trace should be added to the figure *before* the corresponding
    cluster marker trace so that it appears behind it.

    Args:
        x_coords:   RA coordinates of the enhanced clusters.
        y_coords:   Dec coordinates of the enhanced clusters.
        size:       Marker size in pixels.
        shape:      Marker symbol (``"square"`` for PZWAV, ``"diamond"`` for AMICO).
        opacity:    Marker opacity for the glow effect (default 0.3).
        showlegend: Whether to include this trace in the legend.
        name:       Trace name shown on hover / legend.

    Returns:
        A :class:`plotly.graph_objs.Scattergl` glow trace.
    """
    return go.Scattergl(
        x=x_coords,
        y=y_coords,
        mode="markers",
        marker=dict(
            size=size,
            symbol=shape,
            color="yellow",
            opacity=opacity,
            line=dict(width=2, color="yellow"),
        ),
        name=name if name else "Cluster in Proximity",
        showlegend=showlegend,
        hoverinfo="skip",
        hovertemplate=None,
    )
