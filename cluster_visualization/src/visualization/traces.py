"""
Trace creation module for cluster visualization.

This module handles the creation of all Plotly traces including:
- Cluster detection scatter traces (merged and individual tiles)
- Polygon traces (LEV1, CORE, MER tiles)
- CATRED high-resolution data traces
- SNR filtering and data layering
- Trace styling and hover text formatting
"""

import json
import os
import numpy as np
import plotly.graph_objs as go
from typing import Dict, List, Any, Optional, Tuple


class TraceCreator:
    """Handles creation of all Plotly traces for cluster visualization."""
    
    def __init__(self, colors_list=None, colors_list_transparent=None, catred_handler=None):
        """
        Initialize TraceCreator with color schemes and CATRED handler.
        
        Args:
            colors_list: List of colors for tile traces
            colors_list_transparent: List of transparent colors for polygon fills
            catred_handler: CATRED handler instance for trace caching
        """
        self.colors_list = colors_list or self._get_default_colors()
        self.colors_list_transparent = colors_list_transparent or self._get_default_transparent_colors()
        self.catred_handler = catred_handler
        
        # For fallback when no CATRED handler is available
        self.current_catred_data = None
    
    def create_traces(self, data: Dict[str, Any], show_polygons: bool = True, 
                     show_mer_tiles: bool = False, relayout_data: Optional[Dict] = None,
                     show_catred_mertile_data: bool = False, manual_catred_data: Optional[Dict] = None,
                     existing_catred_traces: Optional[List] = None, snr_threshold_lower: Optional[float] = None,
                     snr_threshold_upper: Optional[float] = None) -> List:
        """
        Create all Plotly traces for the visualization.
        
        Args:
            data: Main data dictionary with cluster and tile information
            show_polygons: Whether to fill polygons or show outlines only
            show_mer_tiles: Whether to show MER tile polygons
            relayout_data: Current zoom/pan state for zoom threshold checking
            show_catred_mertile_data: Whether to show high-res CATRED data
            manual_catred_data: Manually loaded CATRED scatter data
            existing_catred_traces: Existing CATRED traces to preserve
            snr_threshold_lower: Lower SNR threshold for filtering
            snr_threshold_upper: Upper SNR threshold for filtering
            
        Returns:
            List of Plotly traces ordered for proper layering
        """
        traces = []  # Polygon traces (bottom layer)
        data_traces = []  # Data traces (top layer)
        
        # Apply SNR filtering to merged data
        datamod_merged = self._apply_snr_filtering(data['merged_data'], snr_threshold_lower, snr_threshold_upper)

        # Check zoom threshold for CATRED data display
        zoom_threshold_met = self._check_zoom_threshold(relayout_data, show_catred_mertile_data)

        # Get CATRED data points for proximity-based marker enhancement
        catred_points = self._get_catred_data_points(manual_catred_data, existing_catred_traces)

        # Create data traces in layered order: CATRED → Merged → Individual tiles
        self._add_existing_catred_traces(data_traces, existing_catred_traces)
        self._add_manual_catred_traces(data_traces, show_mer_tiles, show_catred_mertile_data,
                                       manual_catred_data, zoom_threshold_met)
        self._add_merged_cluster_trace(data_traces, datamod_merged, data['algorithm'], catred_points)
        
        # Create tile traces and polygons
        tile_traces = self._create_tile_traces_and_polygons(
            data, traces, show_polygons, show_mer_tiles, snr_threshold_lower, snr_threshold_upper, catred_points
        )
        
        # Add tile traces to top layer
        data_traces.extend(tile_traces)
        
        # Return combined traces: polygons first (bottom), then data traces (top)
        return traces + data_traces
    
    def _get_catred_data_points(self, manual_catred_data: Optional[Dict], existing_catred_traces: Optional[List]) -> Optional[List]:
        """Get all CATRED data points for proximity-based enhancement."""
        all_points = []

        # Clear bounds cache when getting new CATRED data (important for multiple renders)
        if hasattr(self, '_catred_bounds_cache'):
            delattr(self, '_catred_bounds_cache')
            print("Debug: Cleared old CATRED bounds cache for new data")

        # Collect coordinates from manual CATRED data
        if manual_catred_data and manual_catred_data.get('ra'):
            for ra, dec in zip(manual_catred_data['ra'], manual_catred_data['dec']):
                all_points.append((ra, dec))
            print(f"Debug: Added {len(manual_catred_data['ra'])} points from manual CATRED data")

        # Collect coordinates from existing CATRED traces (passed from cache)
        if existing_catred_traces and len(existing_catred_traces) > 0:
            # CATRED traces exist, keep current stored data
            if hasattr(self, 'current_catred_data') and self.current_catred_data:
                for trace_name, catred_data in self.current_catred_data.items():
                    if catred_data and catred_data.get('ra'):
                        for ra, dec in zip(catred_data['ra'], catred_data['dec']):
                            all_points.append((ra, dec))
                        print(f"Debug: Added {len(catred_data['ra'])} points from existing trace '{trace_name}'")
        else:
            # No existing CATRED traces - clear stored CATRED data to revert markers
            if hasattr(self, 'current_catred_data'):
                self.current_catred_data = None
                print("Debug: CATRED data cleared - reverting marker enhancements")
            # Clear bounds cache as well
            if hasattr(self, '_catred_bounds_cache'):
                delattr(self, '_catred_bounds_cache')

        # If no CATRED data found, return None (no enhancement)
        if not all_points:
            print("Debug: No CATRED data points found - no enhancement will be applied")
            return None

        print(f"Debug: Found {len(all_points)} total CATRED data points for proximity-based enhancement")
        return all_points
    
    def clear_catred_data(self):
        """Explicitly clear stored CATRED data to revert marker enhancements."""
        if hasattr(self, 'current_catred_data'):
            self.current_catred_data = None
            print("Debug: TraceCreator CATRED data explicitly cleared")

        # Clear bounds cache as well
        if hasattr(self, '_catred_bounds_cache'):
            delattr(self, '_catred_bounds_cache')
            print("Debug: CATRED bounds cache cleared")
        if hasattr(self, '_subsampled_catred_cache'):
            delattr(self, '_subsampled_catred_cache')
            print("Debug: Subsampled CATRED cache cleared")

    def _get_subsampled_catred_points(self, catred_points: List) -> List:
        """Get subsampled CATRED points for proximity detection, with caching."""
        if not catred_points:
            return catred_points

        # Create a simple hash to detect changes in CATRED data
        catred_hash = hash(str(len(catred_points)) + str(catred_points[0] if catred_points else ""))
        
        # Check if we have cached subsampled points for this dataset
        if hasattr(self, '_subsampled_catred_cache'):
            cached_hash, cached_points = self._subsampled_catred_cache
            if cached_hash == catred_hash:
                return cached_points

        # For very large datasets, subsample CATRED points for proximity detection
        if len(catred_points) > 20000:  # Lower threshold for better performance
            import numpy as np
            # Use every 5th point for proximity detection to speed up calculation
            sampled_points = catred_points[::5]
            print(f"Debug: Subsampled {len(sampled_points)} from {len(catred_points)} CATRED points for proximity")
        else:
            sampled_points = catred_points
            
        # Cache the result
        self._subsampled_catred_cache = (catred_hash, sampled_points)
        return sampled_points
    
    def _is_point_near_catred_region(self, ra: float, dec: float, catred_points: List, proximity_threshold: float = 0.01) -> bool:
        """Check if a point is within proximity threshold of any CATRED data point."""
        if not catred_points:
            return False
        
        # Get cached subsampled points
        sampled_points = self._get_subsampled_catred_points(catred_points)
        
        # Create a simple hash of the sampled points to detect changes
        points_to_hash = sampled_points[:100] if len(sampled_points) > 100 else sampled_points
        catred_points_hash = hash(tuple(points_to_hash))

        # Pre-compute CATRED bounds for quick rejection (with validation)
        if not hasattr(self, '_catred_bounds_cache') or self._catred_bounds_cache.get('hash') != catred_points_hash:
            import numpy as np
            catred_array = np.array(sampled_points)
            self._catred_bounds_cache = {
                'ra_min': np.min(catred_array[:, 0]) - proximity_threshold,
                'ra_max': np.max(catred_array[:, 0]) + proximity_threshold,
                'dec_min': np.min(catred_array[:, 1]) - proximity_threshold,
                'dec_max': np.max(catred_array[:, 1]) + proximity_threshold,
                'hash': catred_points_hash
            }
            print(f"Debug: CATRED bounds cache created/updated - {len(sampled_points)} sampled points, hash: {catred_points_hash}")

        # Quick bounding box rejection
        bounds = self._catred_bounds_cache
        if not (bounds['ra_min'] <= ra <= bounds['ra_max'] and 
                bounds['dec_min'] <= dec <= bounds['dec_max']):
            return False
        
        # Only do expensive distance calculation if within bounding box (use sampled points)
        for catred_ra, catred_dec in sampled_points:
            distance_sq = (ra - catred_ra) ** 2 + (dec - catred_dec) ** 2
            if distance_sq <= proximity_threshold ** 2:  # Avoid sqrt
                return True
        
        return False
    
    def _apply_snr_filtering(self, merged_data: np.ndarray, snr_lower: Optional[float], 
                           snr_upper: Optional[float]) -> np.ndarray:
        """Apply SNR filtering to merged cluster data."""
        if snr_lower is None and snr_upper is None:
            return merged_data
        elif snr_lower is not None and snr_upper is not None:
            return merged_data[(merged_data['SNR_CLUSTER'] >= snr_lower) & 
                              (merged_data['SNR_CLUSTER'] <= snr_upper)]
        elif snr_upper is not None and snr_lower is None:
            return merged_data[merged_data['SNR_CLUSTER'] <= snr_upper]
        elif snr_lower is not None:
            return merged_data[merged_data['SNR_CLUSTER'] >= snr_lower]
        else:
            return merged_data
    
    def _check_zoom_threshold(self, relayout_data: Optional[Dict], show_mer_tiles: bool) -> bool:
        """Check if zoom level meets threshold for CATRED data display (< 2 degrees)."""
        if not relayout_data or not show_mer_tiles:
            print(f"Debug: Zoom check skipped - relayout_data: {relayout_data is not None}, show_mer_tiles: {show_mer_tiles}")
            return False
        
        print(f"Debug: Checking zoom threshold - relayout_data: {relayout_data}")
        
        # Extract zoom ranges
        ra_range = dec_range = None
        
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            ra_range = abs(relayout_data['xaxis.range[1]'] - relayout_data['xaxis.range[0]'])
        elif 'xaxis.range' in relayout_data:
            ra_range = abs(relayout_data['xaxis.range'][1] - relayout_data['xaxis.range'][0])
            
        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            dec_range = abs(relayout_data['yaxis.range[1]'] - relayout_data['yaxis.range[0]'])
        elif 'yaxis.range' in relayout_data:
            dec_range = abs(relayout_data['yaxis.range'][1] - relayout_data['yaxis.range'][0])
        
        print(f"Debug: Zoom ranges - RA: {ra_range}, Dec: {dec_range}")
        
        # Check threshold (< 2 degrees in both dimensions)
        if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
            print(f"Debug: Zoom threshold MET! RA: {ra_range:.3f}° < 2°, Dec: {dec_range:.3f}° < 2°")
            return True
        else:
            print(f"Debug: Zoom threshold NOT met. RA: {ra_range}, Dec: {dec_range}")
            return False
    
    def _add_existing_catred_traces(self, data_traces: List, existing_catred_traces: Optional[List]) -> None:
        """Add existing CATRED traces to preserve them across renders."""
        if existing_catred_traces:
            print(f"Debug: Adding {len(existing_catred_traces)} existing CATRED traces to bottom layer")
            data_traces.extend(existing_catred_traces)
    
    def _add_manual_catred_traces(self, data_traces: List, show_mer_tiles: bool, 
                              show_catred_mertile_data: bool, manual_catred_data: Optional[Dict],
                              zoom_threshold_met: bool) -> None:
        """Add manually loaded CATRED high-resolution data traces."""
        if not (show_mer_tiles and show_catred_mertile_data and manual_catred_data):
            if show_mer_tiles and show_catred_mertile_data and zoom_threshold_met:
                print(f"Debug: CATRED scatter conditions met but no manual data provided - use render button")
            else:
                print(f"Debug: CATRED scatter data conditions not met - show_mer_tiles: {show_mer_tiles}, "
                      f"show_catred_mertile_data: {show_catred_mertile_data}, manual_data: {manual_catred_data is not None}")
            return
        
        if not manual_catred_data.get('ra'):
            print("Debug: No CATRED scatter data available to display")
            return

        print(f"Debug: Using manually loaded CATRED scatter data")
        print(f"Debug: Creating CATRED scatter trace with {len(manual_catred_data['ra'])} points")

        # Generate unique trace name
        trace_count = self.catred_handler.get_traces_count() if self.catred_handler else 1
        trace_name = f'CATRED High-Res Data #{trace_count + 1}'

        # Create CATRED scatter trace
        catred_trace = go.Scattergl(
            x=manual_catred_data['ra'],
            y=manual_catred_data['dec'],
            mode='markers',
            marker=dict(size=4, symbol='circle', color='black', opacity=0.5),
            name=trace_name,
            text=self._format_catred_hover_text(manual_catred_data),
            hoverinfo='text',
            showlegend=True,
            customdata=list(range(len(manual_catred_data['ra'])))  # Add index for click tracking
        )
        data_traces.append(catred_trace)

        # Store CATRED data for click callbacks in multiple locations for better access
        if not hasattr(self, 'current_catred_data') or self.current_catred_data is None:
            self.current_catred_data = {}
        self.current_catred_data[trace_name] = manual_catred_data
        
        # Also store in CATRED handler if available
        if self.catred_handler:
            if not hasattr(self.catred_handler, 'current_catred_data') or self.catred_handler.current_catred_data is None:
                self.catred_handler.current_catred_data = {}
            self.catred_handler.current_catred_data[trace_name] = manual_catred_data
            print(f"Debug: Also stored CATRED data in catred_handler")

        print(f"Debug: Stored CATRED data for trace '{trace_name}' with {len(manual_catred_data['ra'])} points")
        print(f"Debug: PHZ_PDF sample length: {len(manual_catred_data['phz_pdf'][0]) if manual_catred_data['phz_pdf'] else 'No PHZ_PDF data'}")
        print(f"Debug: Current CATRED data keys: {list(self.current_catred_data.keys())}")
        print(f"Debug: TraceCreator.current_catred_data id: {id(self.current_catred_data)}")
        print(f"Debug: Trace name: '{trace_name}'")
        print("Debug: CATRED trace added to TOP LAYER (should be clickable)")
        print("Debug: About to return from _add_manual_catred_traces method")
    
    def _format_catred_hover_text(self, catred_data: Dict[str, List]) -> List[str]:
        """Format hover text for CATRED data points."""
        return [
            f'CATRED Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ_MODE_1: {p1:.3f}<br>'
            f'PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}'
            for x, y, p1, p70 in zip(catred_data['ra'], catred_data['dec'], 
                                   catred_data['phz_mode_1'], catred_data['phz_70_int'])
        ]
    
    def _create_glow_trace(self, x_coords, y_coords, size: int) -> go.Scattergl:
        """Create a glow effect trace for enhanced markers."""
        return go.Scattergl(
            x=x_coords,
            y=y_coords,
            mode='markers',
            marker=dict(
                size=size,  # Size passed from caller
                symbol='circle',
                color='yellow',
                opacity=0.3,  # Semi-transparent for glow effect
                line=dict(width=1, color='yellow')
            ),
            name='Enhanced Marker Glow',
            showlegend=False,  # Don't show in legend
            hoverinfo='skip'   # Don't show hover for glow layer
        )

    def _add_merged_cluster_trace(self, data_traces: List, datamod_merged: np.ndarray, algorithm: str, catred_points: Optional[List] = None) -> None:
        """Add merged cluster detection trace with proximity-based enhancement."""
        if catred_points is None:
            # No CATRED data - create single trace with normal markers
            merged_trace = go.Scattergl(
                x=datamod_merged['RIGHT_ASCENSION_CLUSTER'],
                y=datamod_merged['DECLINATION_CLUSTER'],
                mode='markers',
                marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
                name=f'Merged Data ({algorithm}) - {len(datamod_merged)} clusters',
                text=[
                    f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                    for snr, cz, ra, dec in zip(datamod_merged['SNR_CLUSTER'], 
                                              datamod_merged['Z_CLUSTER'], 
                                              datamod_merged['RIGHT_ASCENSION_CLUSTER'], 
                                              datamod_merged['DECLINATION_CLUSTER'])
                ],
                hoverinfo='text'
            )
            data_traces.append(merged_trace)
        else:
            # CATRED data present - create separate traces based on proximity to CATRED points
            near_catred_mask = np.array([
                self._is_point_near_catred_region(ra, dec, catred_points) 
                for ra, dec in zip(datamod_merged['RIGHT_ASCENSION_CLUSTER'], 
                                 datamod_merged['DECLINATION_CLUSTER'])
            ])
            
            away_from_catred_data = datamod_merged[~near_catred_mask]
            near_catred_data = datamod_merged[near_catred_mask]

            # Create trace for markers away from CATRED region (normal size)
            if len(away_from_catred_data) > 0:
                normal_trace = go.Scattergl(
                    x=away_from_catred_data['RIGHT_ASCENSION_CLUSTER'],
                    y=away_from_catred_data['DECLINATION_CLUSTER'],
                    mode='markers',
                    marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
                    name=f'Merged Data ({algorithm}) - {len(away_from_catred_data)} clusters',
                    text=[
                        f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                        for snr, cz, ra, dec in zip(away_from_catred_data['SNR_CLUSTER'], 
                                                  away_from_catred_data['Z_CLUSTER'], 
                                                  away_from_catred_data['RIGHT_ASCENSION_CLUSTER'], 
                                                  away_from_catred_data['DECLINATION_CLUSTER'])
                    ],
                    hoverinfo='text'
                )
                data_traces.append(normal_trace)

            # Create trace for markers near CATRED region (enhanced size with highlight)
            if len(near_catred_data) > 0:
                # Add glow effect trace first (background)
                glow_trace = self._create_glow_trace(
                    near_catred_data['RIGHT_ASCENSION_CLUSTER'],
                    near_catred_data['DECLINATION_CLUSTER'],
                    28
                )
                data_traces.append(glow_trace)
                
                # Add main enhanced trace (foreground)
                enhanced_trace = go.Scattergl(
                    x=near_catred_data['RIGHT_ASCENSION_CLUSTER'],
                    y=near_catred_data['DECLINATION_CLUSTER'],
                    mode='markers',
                    marker=dict(
                        size=20, 
                        symbol='square-open', 
                        line=dict(width=3, color='yellow'),  # Bright yellow highlight
                        color='black',
                        opacity=1.0
                    ),
                    name=f'Merged Data (Enhanced) - {len(near_catred_data)} clusters',
                    text=[
                        f"merged (enhanced)<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                        for snr, cz, ra, dec in zip(near_catred_data['SNR_CLUSTER'], 
                                                  near_catred_data['Z_CLUSTER'], 
                                                  near_catred_data['RIGHT_ASCENSION_CLUSTER'], 
                                                  near_catred_data['DECLINATION_CLUSTER'])
                    ],
                    hoverinfo='text'
                )
                data_traces.append(enhanced_trace)
                
                print(f"Debug: Enhanced {len(near_catred_data)} merged clusters near MER data, {len(away_from_catred_data)} normal")
    
    def _create_tile_traces_and_polygons(self, data: Dict[str, Any], polygon_traces: List,
                                        show_polygons: bool, show_mer_tiles: bool,
                                        snr_threshold_lower: Optional[float], 
                                        snr_threshold_upper: Optional[float],
                                        catred_points: Optional[List] = None) -> List:
        """Create individual tile traces with proximity-based enhancement."""
        tile_traces = []
        
        for tileid, value in data['tile_data'].items():
            tile_data = value['data']
            
            # Apply SNR filtering to tile data
            datamod = self._apply_snr_filtering(tile_data, snr_threshold_lower, snr_threshold_upper)
            
            if catred_points is None:
                # No CATRED data - create single trace with normal markers
                tile_trace = go.Scattergl(
                    x=datamod['RIGHT_ASCENSION_CLUSTER'],
                    y=datamod['DECLINATION_CLUSTER'],
                    mode='markers',
                    marker=dict(size=6, opacity=1, symbol='x', color=self.colors_list[int(tileid)]),
                    name=f'Tile {tileid}',
                    text=[
                        f"TileID: {tileid}<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                        for snr, cz, ra, dec in zip(datamod['SNR_CLUSTER'], datamod['Z_CLUSTER'], 
                                                  datamod['RIGHT_ASCENSION_CLUSTER'], datamod['DECLINATION_CLUSTER'])
                    ],
                    hoverinfo='text'
                )
                tile_traces.append(tile_trace)
            else:
                # CATRED data present - create separate traces based on proximity to CATRED points
                near_catred_mask = np.array([
                    self._is_point_near_catred_region(ra, dec, catred_points) 
                    for ra, dec in zip(datamod['RIGHT_ASCENSION_CLUSTER'], 
                                     datamod['DECLINATION_CLUSTER'])
                ])
                
                away_from_catred_data = datamod[~near_catred_mask]
                near_catred_data = datamod[near_catred_mask]

                # Create trace for markers away from CATRED region (normal size)
                if len(away_from_catred_data) > 0:
                    normal_trace = go.Scattergl(
                        x=away_from_catred_data['RIGHT_ASCENSION_CLUSTER'],
                        y=away_from_catred_data['DECLINATION_CLUSTER'],
                        mode='markers',
                        marker=dict(size=6, opacity=1, symbol='x', color=self.colors_list[int(tileid)]),
                        name=f'Tile {tileid}',
                        text=[
                            f"TileID: {tileid}<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                            for snr, cz, ra, dec in zip(away_from_catred_data['SNR_CLUSTER'], away_from_catred_data['Z_CLUSTER'], 
                                                      away_from_catred_data['RIGHT_ASCENSION_CLUSTER'], away_from_catred_data['DECLINATION_CLUSTER'])
                        ],
                        hoverinfo='text'
                    )
                    tile_traces.append(normal_trace)

                # Create trace for markers near CATRED region (enhanced size with highlight)
                if len(near_catred_data) > 0:
                    # Add glow effect trace first (background)
                    glow_trace = self._create_glow_trace(
                        near_catred_data['RIGHT_ASCENSION_CLUSTER'],
                        near_catred_data['DECLINATION_CLUSTER'],
                        23
                    )
                    tile_traces.append(glow_trace)
                    
                    # Add main enhanced trace (foreground)
                    enhanced_trace = go.Scattergl(
                        x=near_catred_data['RIGHT_ASCENSION_CLUSTER'],
                        y=near_catred_data['DECLINATION_CLUSTER'],
                        mode='markers',
                        marker=dict(
                            size=15, 
                            opacity=1, 
                            symbol='x', 
                            color=self.colors_list[int(tileid)],
                            line=dict(width=2, color='yellow')  # Yellow highlight for 'x' symbols
                        ),
                        name=f'Tile {tileid} (Enhanced)',
                        text=[
                            f"TileID: {tileid} (enhanced)<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                            for snr, cz, ra, dec in zip(near_catred_data['SNR_CLUSTER'], near_catred_data['Z_CLUSTER'], 
                                                      near_catred_data['RIGHT_ASCENSION_CLUSTER'], near_catred_data['DECLINATION_CLUSTER'])
                        ],
                        hoverinfo='text'
                    )
                    tile_traces.append(enhanced_trace)

                    print(f"Debug: Tile {tileid} - Enhanced {len(near_catred_data)} markers near CATRED data, {len(away_from_catred_data)} normal")

            # Create polygon traces for this tile
            
            # Create polygon traces for this tile
            self._create_tile_polygons(polygon_traces, data, tileid, value, show_polygons, show_mer_tiles)
        
        return tile_traces
    
    def _create_tile_polygons(self, polygon_traces: List, data: Dict[str, Any], tileid: str,
                             tile_value: Dict[str, Any], show_polygons: bool, show_mer_tiles: bool) -> None:
        """Create polygon traces for a single tile (LEV1, CORE, and optionally MER)."""
        # Load tile definition
        with open(os.path.join(data['data_dir'], tile_value['tilefile']), 'r') as f:
            tile = json.load(f)
        
        # LEV1 polygon (always outline)
        lev1_polygon = tile['LEV1']['POLYGON'][0]
        lev1_x = [p[0] for p in lev1_polygon] + [lev1_polygon[0][0]]
        lev1_y = [p[1] for p in lev1_polygon] + [lev1_polygon[0][1]]
        
        lev1_trace = go.Scatter(
            x=lev1_x, y=lev1_y,
            mode='lines',
            line=dict(width=2, color=self.colors_list[int(tileid)], dash='dash'),
            name=f'Tile {tileid} LEV1',
            showlegend=False,
            text=f'Tile {tileid} - LEV1 Polygon',
            hoverinfo='text'
        )
        polygon_traces.append(lev1_trace)
        
        # CORE polygon (outline + optional fill)
        core_polygon = tile['CORE']['POLYGON'][0]
        core_x = [p[0] for p in core_polygon] + [core_polygon[0][0]]
        core_y = [p[1] for p in core_polygon] + [core_polygon[0][1]]
        
        # Configure fill based on show_polygons setting
        if show_polygons:
            fillcolor = self.colors_list_transparent[int(tileid)]
            fill = 'toself'
        else:
            fillcolor = None
            fill = None
        
        core_trace = go.Scatter(
            x=core_x, y=core_y,
            fill=fill, fillcolor=fillcolor,
            mode='lines',
            line=dict(width=2, color=self.colors_list[int(tileid)]),
            name=f'Tile {tileid} CORE',
            showlegend=False,
            text=f'Tile {tileid} - CORE Polygon',
            hoverinfo='text'
        )
        polygon_traces.append(core_trace)
        
        # MER tile polygons (only when in outline mode and MER tiles requested)
        if show_mer_tiles and not show_polygons and not data['catred_info'].empty and 'polygon' in data['catred_info'].columns:
            self._create_mer_tile_polygons(polygon_traces, data, tile, tileid)
    
    def _create_mer_tile_polygons(self, polygon_traces: List, data: Dict[str, Any], 
                                 tile: Dict[str, Any], tileid: str) -> None:
        """Create MER tile polygon traces for a cluster tile."""
        for mertileid in tile['LEV1']['ID_INTERSECTED']:
            if mertileid in data['catred_info'].index:
                merpoly = data['catred_info'].at[mertileid, 'polygon']
                if merpoly is not None:
                    x, y = merpoly.exterior.xy
                    mertile_trace = go.Scatter(
                        x=list(x), y=list(y),
                        fill='toself',
                        fillcolor=self.colors_list_transparent[int(tileid)],
                        mode='lines',
                        line=dict(width=2, color=self.colors_list[int(tileid)], dash='dot'),
                        name=f'MerTile {mertileid}',
                        showlegend=False,
                        text=f'MerTile {mertileid} - CLtile {tileid}',
                        hoverinfo='text',
                        hoveron='fills+points'
                    )
                    polygon_traces.append(mertile_trace)
    
    def _get_default_colors(self) -> List[str]:
        """Get default color list for tile traces."""
        return [
            'red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray',
            'olive', 'cyan', 'magenta', 'yellow', 'darkred', 'darkblue', 'darkgreen'
        ] * 10  # Repeat to handle many tiles
    
    def _get_default_transparent_colors(self) -> List[str]:
        """Get default transparent color list for polygon fills."""
        base_colors = self._get_default_colors()
        return [f'rgba({color}, 0.3)' if ',' not in color else color.replace(')', ', 0.3)') 
                for color in base_colors]
