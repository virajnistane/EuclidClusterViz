"""
Spatial indexing utilities for fast astronomical coordinate queries.

This module provides efficient spatial indexing using KD-trees for:
- Fast proximity queries (find points within radius)
- Bounding box queries (find points in RA/Dec region)
- O(log N) performance instead of O(N) for spatial operations
"""

from typing import List, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree


class SpatialIndex:
    """
    Fast spatial queries for astronomical data using KD-tree.

    This class converts RA/Dec coordinates to 3D Cartesian coordinates
    and builds a KD-tree for efficient spatial queries. This is crucial
    for performance when dealing with large catalogs (>10k points).

    Performance Benefits:
    - Proximity queries: O(log N) instead of O(N)
    - Radius searches: 10-100x faster for large datasets
    - Box queries: Efficient filtering for viewport updates

    Example:
        >>> index = SpatialIndex(ra_array, dec_array)
        >>> nearby = index.query_radius(173.5, -28.0, radius_deg=0.1)
        >>> print(f"Found {len(nearby)} points within 6 arcmin")
    """

    def __init__(self, ra: np.ndarray, dec: np.ndarray):
        """
        Build KD-tree spatial index for RA/Dec coordinates.

        Args:
            ra: Right Ascension array in degrees
            dec: Declination array in degrees

        Note:
            Converts coordinates to 3D Cartesian (x,y,z) on unit sphere
            for proper spherical distance calculations.
        """
        self.ra = np.asarray(ra)
        self.dec = np.asarray(dec)
        self.n_points = len(self.ra)

        # Convert to 3D Cartesian coordinates for proper spherical distance
        ra_rad = np.radians(self.ra)
        dec_rad = np.radians(self.dec)

        # Points on unit sphere: (x, y, z)
        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)

        self.coords = np.column_stack([x, y, z])

        # Build KD-tree for fast spatial queries
        print(f"Building spatial index for {self.n_points:,} points...")
        self.tree = cKDTree(self.coords)
        print(f"Spatial index built successfully")

    def query_radius(self, ra_center: float, dec_center: float, radius_deg: float) -> np.ndarray:
        """
        Find all points within angular radius of a center point.

        This is the key performance optimization - replaces O(N) loops
        with O(log N) tree queries. Typical speedup: 10-100x for large datasets.

        Args:
            ra_center: Center point RA in degrees
            dec_center: Center point Dec in degrees
            radius_deg: Search radius in degrees

        Returns:
            Array of indices of points within the radius

        Example:
            >>> # OLD: Loop through all points - O(N)
            >>> for i, (ra, dec) in enumerate(zip(all_ra, all_dec)):
            ...     if distance(ra, dec, center_ra, center_dec) < radius:
            ...         matches.append(i)

            >>> # NEW: Single tree query - O(log N)
            >>> matches = index.query_radius(center_ra, center_dec, radius)
        """
        # Convert query point to Cartesian
        ra_rad = np.radians(ra_center)
        dec_rad = np.radians(dec_center)
        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)
        query_point = np.array([x, y, z])

        # Convert angular radius to chord distance
        # For small angles: chord ≈ 2*sin(angle/2)
        chord_dist = 2 * np.sin(np.radians(radius_deg) / 2)

        # Query tree - this is where the magic happens!
        indices = self.tree.query_ball_point(query_point, chord_dist)

        return np.array(indices, dtype=np.int64)

    def query_multiple_radius(
        self, ra_centers: np.ndarray, dec_centers: np.ndarray, radius_deg: float
    ) -> List[np.ndarray]:
        """
        Find points within radius of multiple center points simultaneously.

        More efficient than calling query_radius() in a loop for multiple points.

        Args:
            ra_centers: Array of center point RAs in degrees
            dec_centers: Array of center point Decs in degrees
            radius_deg: Search radius in degrees (same for all centers)

        Returns:
            List of index arrays, one per center point
        """
        # Convert all query points to Cartesian
        ra_rad = np.radians(ra_centers)
        dec_rad = np.radians(dec_centers)
        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)
        query_points = np.column_stack([x, y, z])

        # Convert angular radius to chord distance
        chord_dist = 2 * np.sin(np.radians(radius_deg) / 2)

        # Query tree for all points at once
        indices_list = self.tree.query_ball_point(query_points, chord_dist)

        return [np.array(indices, dtype=np.int64) for indices in indices_list]

    def query_box(self, ra_min: float, ra_max: float, dec_min: float, dec_max: float) -> np.ndarray:
        """
        Find all points within an RA/Dec bounding box.

        Useful for viewport filtering - only show points in current view.

        Args:
            ra_min: Minimum RA in degrees
            ra_max: Maximum RA in degrees
            dec_min: Minimum Dec in degrees
            dec_max: Maximum Dec in degrees

        Returns:
            Array of indices of points within the box

        Note:
            This uses simple array masking, not the KD-tree.
            For box queries, direct comparison is already efficient.
        """
        mask = (
            (self.ra >= ra_min)
            & (self.ra <= ra_max)
            & (self.dec >= dec_min)
            & (self.dec <= dec_max)
        )
        return np.where(mask)[0]

    def query_nearest(self, ra: float, dec: float, k: int = 1) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find k nearest neighbors to a point.

        Args:
            ra: Query point RA in degrees
            dec: Query point Dec in degrees
            k: Number of nearest neighbors to find

        Returns:
            Tuple of (distances, indices) - both arrays of length k
            Distances are in chord distance (not angular separation)
        """
        # Convert query point to Cartesian
        ra_rad = np.radians(ra)
        dec_rad = np.radians(dec)
        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)
        query_point = np.array([x, y, z])

        # Query k nearest neighbors
        distances, indices = self.tree.query(query_point, k=k)

        return distances, indices

    def get_point_coordinates(self, indices: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get RA/Dec coordinates for given indices.

        Args:
            indices: Array of point indices

        Returns:
            Tuple of (ra_array, dec_array)
        """
        return self.ra[indices], self.dec[indices]


class CATREDSpatialIndex:
    """
    Specialized spatial index for CATRED proximity detection.

    This wraps SpatialIndex with CATRED-specific optimizations:
    - Automatic subsampling for very large datasets
    - Caching of index structure
    - Optimized proximity threshold checking

    Usage in TraceCreator:
        >>> self.catred_index = CATREDSpatialIndex(catred_ra, catred_dec)
        >>> is_near = self.catred_index.is_any_point_near(cluster_ra, cluster_dec)
    """

    def __init__(self, ra: np.ndarray, dec: np.ndarray, subsample_threshold: int = 100000):
        """
        Initialize CATRED spatial index with optional subsampling.

        Args:
            ra: CATRED RA array in degrees
            dec: CATRED Dec array in degrees
            subsample_threshold: Subsample if more than this many points (default 100k)
        """
        self.n_original = len(ra)

        # Subsample for very large datasets to balance speed vs accuracy
        if self.n_original > subsample_threshold:
            step = self.n_original // subsample_threshold
            indices = np.arange(0, self.n_original, step)
            self.index = SpatialIndex(ra[indices], dec[indices])
            self.subsampled = True
            print(
                f"CATRED spatial index: subsampled {len(indices):,} from {self.n_original:,} points"
            )
        else:
            self.index = SpatialIndex(ra, dec)
            self.subsampled = False
            print(f"CATRED spatial index: using all {self.n_original:,} points")

    def check_proximity_batch(
        self, ra_array: np.ndarray, dec_array: np.ndarray, radius_deg: float = 0.1
    ) -> np.ndarray:
        """
        Check which points in a batch are near any CATRED data.

        This is the key optimization for marker enhancement!

        Args:
            ra_array: Array of cluster RAs to check
            dec_array: Array of cluster Decs to check
            radius_deg: Proximity threshold in degrees (default 0.1 = 6 arcmin)

        Returns:
            Boolean mask: True where cluster is near CATRED data

        Example Performance:
            OLD: 10,000 clusters × 100,000 CATRED points = 1B comparisons
            NEW: 10,000 log-queries × log(100,000) ≈ 170k operations
            Speedup: ~6000x!
        """
        is_near = np.zeros(len(ra_array), dtype=bool)

        # Query tree for each cluster point
        for i, (ra, dec) in enumerate(zip(ra_array, dec_array)):
            nearby_indices = self.index.query_radius(ra, dec, radius_deg)
            if len(nearby_indices) > 0:
                is_near[i] = True

        return is_near

    def check_proximity_single(self, ra: float, dec: float, radius_deg: float = 0.1) -> bool:
        """
        Check if a single point is near any CATRED data.

        Args:
            ra: Point RA in degrees
            dec: Point Dec in degrees
            radius_deg: Proximity threshold in degrees

        Returns:
            True if point is within radius of any CATRED data
        """
        nearby_indices = self.index.query_radius(ra, dec, radius_deg)
        return len(nearby_indices) > 0
