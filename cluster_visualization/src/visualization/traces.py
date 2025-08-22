"""
Trace creation module for cluster visualization.

This module handles the creation of all Plotly traces including:
- Cluster detection scatter traces (merged and individual tiles)
- Polygon traces (LEV1, CORE, MER tiles)
- MER high-resolution data traces
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
    
    def __init__(self, colors_list=None, colors_list_transparent=None, mer_handler=None):
        """
        Initialize TraceCreator with color schemes and MER handler.
        
        Args:
            colors_list: List of colors for tile traces
            colors_list_transparent: List of transparent colors for polygon fills
            mer_handler: MER handler instance for trace caching
        """
        self.colors_list = colors_list or self._get_default_colors()
        self.colors_list_transparent = colors_list_transparent or self._get_default_transparent_colors()
        self.mer_handler = mer_handler
        
        # For fallback when no MER handler is available
        self.current_mer_data = None
    
    def create_traces(self, data: Dict[str, Any], show_polygons: bool = True, 
                     show_mer_tiles: bool = False, relayout_data: Optional[Dict] = None,
                     show_catred_mertile_data: bool = False, manual_mer_data: Optional[Dict] = None,
                     existing_mer_traces: Optional[List] = None, snr_threshold_lower: Optional[float] = None,
                     snr_threshold_upper: Optional[float] = None) -> List:
        """
        Create all Plotly traces for the visualization.
        
        Args:
            data: Main data dictionary with cluster and tile information
            show_polygons: Whether to fill polygons or show outlines only
            show_mer_tiles: Whether to show MER tile polygons
            relayout_data: Current zoom/pan state for zoom threshold checking
            show_catred_mertile_data: Whether to show high-res MER data
            manual_mer_data: Manually loaded MER scatter data
            existing_mer_traces: Existing MER traces to preserve
            snr_threshold_lower: Lower SNR threshold for filtering
            snr_threshold_upper: Upper SNR threshold for filtering
            
        Returns:
            List of Plotly traces ordered for proper layering
        """
        traces = []  # Polygon traces (bottom layer)
        data_traces = []  # Data traces (top layer)
        
        # Apply SNR filtering to merged data
        datamod_merged = self._apply_snr_filtering(data['merged_data'], snr_threshold_lower, snr_threshold_upper)
        
        # Check zoom threshold for MER data display
        zoom_threshold_met = self._check_zoom_threshold(relayout_data, show_mer_tiles)
        
        # Get MER data points for proximity-based marker enhancement
        mer_points = self._get_mer_data_points(manual_mer_data, existing_mer_traces)
        
        # Create data traces in layered order: MER → Merged → Individual tiles
        self._add_existing_mer_traces(data_traces, existing_mer_traces)
        print("Debug: Finished adding existing MER traces")
        
        self._add_manual_mer_traces(data_traces, show_mer_tiles, show_catred_mertile_data, 
                                   manual_mer_data, zoom_threshold_met)
        print("Debug: Finished adding manual MER traces")
        
        self._add_merged_cluster_trace(data_traces, datamod_merged, data['algorithm'], mer_points)
        print("Debug: Finished adding merged cluster traces")
        
        # Create tile traces and polygons
        print("Debug: Starting tile traces and polygons creation")
        tile_traces = self._create_tile_traces_and_polygons(
            data, traces, show_polygons, show_mer_tiles, snr_threshold_lower, snr_threshold_upper, mer_points
        )
        print(f"Debug: Finished creating tile traces and polygons - {len(tile_traces)} tile traces created")
        
        # Add tile traces to top layer
        data_traces.extend(tile_traces)
        print(f"Debug: Final trace count - {len(traces)} polygon traces, {len(data_traces)} data traces")
        
        # Return combined traces: polygons first (bottom), then data traces (top)
        final_traces = traces + data_traces
        print(f"Debug: Returning {len(final_traces)} total traces to Dash")
        return final_traces
    
    def _get_mer_data_points(self, manual_mer_data: Optional[Dict], existing_mer_traces: Optional[List]) -> Optional[List]:
        """Get all MER data points for proximity-based enhancement."""
        all_points = []
        
        # Collect coordinates from manual MER data
        if manual_mer_data and manual_mer_data.get('ra'):
            for ra, dec in zip(manual_mer_data['ra'], manual_mer_data['dec']):
                all_points.append((ra, dec))
        
        # Collect coordinates from existing MER traces (passed from cache)
        if existing_mer_traces and len(existing_mer_traces) > 0:
            # MER traces exist, keep current stored data
            if hasattr(self, 'current_mer_data') and self.current_mer_data:
                for mer_data in self.current_mer_data.values():
                    if mer_data and mer_data.get('ra'):
                        for ra, dec in zip(mer_data['ra'], mer_data['dec']):
                            all_points.append((ra, dec))
        else:
            # No existing MER traces - clear stored MER data to revert markers
            if hasattr(self, 'current_mer_data'):
                self.current_mer_data = None
                print("Debug: MER data cleared - reverting marker enhancements")
            # Clear bounds cache as well
            if hasattr(self, '_mer_bounds_cache'):
                delattr(self, '_mer_bounds_cache')
        
        # If no MER data found, return None (no enhancement)
        if not all_points:
            return None
        
        print(f"Debug: Found {len(all_points)} MER data points for proximity-based enhancement")
        return all_points
    
    def clear_mer_data(self):
        """Explicitly clear stored MER data to revert marker enhancements."""
        if hasattr(self, 'current_mer_data'):
            self.current_mer_data = None
            print("Debug: TraceCreator MER data explicitly cleared")
        
        # Clear bounds cache as well
        if hasattr(self, '_mer_bounds_cache'):
            delattr(self, '_mer_bounds_cache')
            print("Debug: MER bounds cache cleared")
    
    def _is_point_near_mer_region(self, ra: float, dec: float, mer_points: List, proximity_threshold: float = 0.01) -> bool:
        """Check if a point is within proximity threshold of any MER data point."""
        if not mer_points:
            return False
        
        # Pre-compute MER bounds for quick rejection
        if not hasattr(self, '_mer_bounds_cache'):
            import numpy as np
            mer_array = np.array(mer_points)
            self._mer_bounds_cache = {
                'ra_min': np.min(mer_array[:, 0]) - proximity_threshold,
                'ra_max': np.max(mer_array[:, 0]) + proximity_threshold,
                'dec_min': np.min(mer_array[:, 1]) - proximity_threshold,
                'dec_max': np.max(mer_array[:, 1]) + proximity_threshold
            }
            print(f"Debug: MER bounds cache created - {len(mer_points)} points")
        
        # Quick bounding box rejection
        bounds = self._mer_bounds_cache
        if not (bounds['ra_min'] <= ra <= bounds['ra_max'] and 
                bounds['dec_min'] <= dec <= bounds['dec_max']):
            return False
        
        # Only do expensive distance calculation if within bounding box
        for mer_ra, mer_dec in mer_points:
            distance_sq = (ra - mer_ra) ** 2 + (dec - mer_dec) ** 2
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
        """Check if zoom level meets threshold for MER data display (< 2 degrees)."""
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
    
    def _add_existing_mer_traces(self, data_traces: List, existing_mer_traces: Optional[List]) -> None:
        """Add existing MER traces to preserve them across renders."""
        if existing_mer_traces:
            print(f"Debug: Adding {len(existing_mer_traces)} existing MER traces to bottom layer")
            data_traces.extend(existing_mer_traces)
    
    def _add_manual_mer_traces(self, data_traces: List, show_mer_tiles: bool, 
                              show_catred_mertile_data: bool, manual_mer_data: Optional[Dict],
                              zoom_threshold_met: bool) -> None:
        """Add manually loaded MER high-resolution data traces."""
        if not (show_mer_tiles and show_catred_mertile_data and manual_mer_data):
            if show_mer_tiles and show_catred_mertile_data and zoom_threshold_met:
                print(f"Debug: MER scatter conditions met but no manual data provided - use render button")
            else:
                print(f"Debug: MER scatter data conditions not met - show_mer_tiles: {show_mer_tiles}, "
                      f"show_catred_mertile_data: {show_catred_mertile_data}, manual_data: {manual_mer_data is not None}")
            return
        
        if not manual_mer_data.get('ra'):
            print("Debug: No MER scatter data available to display")
            return
        
        print(f"Debug: Using manually loaded MER scatter data")
        print(f"Debug: Creating MER scatter trace with {len(manual_mer_data['ra'])} points")
        
        # Generate unique trace name
        trace_count = self.mer_handler.get_traces_count() if self.mer_handler else 1
        trace_name = f'MER High-Res Data #{trace_count + 1}'
        
        # Create MER scatter trace
        mer_trace = go.Scattergl(
            x=manual_mer_data['ra'],
            y=manual_mer_data['dec'],
            mode='markers',
            marker=dict(size=4, symbol='circle', color='black', opacity=0.5),
            name=trace_name,
            text=self._format_mer_hover_text(manual_mer_data),
            hoverinfo='text',
            showlegend=True,
            customdata=list(range(len(manual_mer_data['ra'])))  # Add index for click tracking
        )
        data_traces.append(mer_trace)
        
        # Store MER data for click callbacks
        if not hasattr(self, 'current_mer_data') or self.current_mer_data is None:
            self.current_mer_data = {}
        self.current_mer_data[trace_name] = manual_mer_data
        
        print(f"Debug: Stored MER data for trace '{trace_name}' with {len(manual_mer_data['ra'])} points")
        print(f"Debug: PHZ_PDF sample length: {len(manual_mer_data['phz_pdf'][0]) if manual_mer_data['phz_pdf'] else 'No PHZ_PDF data'}")
        print(f"Debug: Current MER data keys: {list(self.current_mer_data.keys())}")
        print(f"Debug: TraceCreator.current_mer_data id: {id(self.current_mer_data)}")
        print("Debug: MER CATRED trace added to bottom layer")
        print("Debug: About to return from _add_manual_mer_traces method")
    
    def _format_mer_hover_text(self, mer_data: Dict[str, List]) -> List[str]:
        """Format hover text for MER data points."""
        return [
            f'MER Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ_MODE_1: {p1:.3f}<br>'
            f'PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}'
            for x, y, p1, p70 in zip(mer_data['ra'], mer_data['dec'], 
                                   mer_data['phz_mode_1'], mer_data['phz_70_int'])
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

    def _add_merged_cluster_trace(self, data_traces: List, datamod_merged: np.ndarray, algorithm: str, mer_points: Optional[List] = None) -> None:
        """Add merged cluster detection trace with proximity-based enhancement."""
        if mer_points is None:
            # No MER data - create single trace with normal markers
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
            # MER data present - create separate traces based on proximity to MER points
            near_mer_mask = np.array([
                self._is_point_near_mer_region(ra, dec, mer_points) 
                for ra, dec in zip(datamod_merged['RIGHT_ASCENSION_CLUSTER'], 
                                 datamod_merged['DECLINATION_CLUSTER'])
            ])
            
            away_from_mer_data = datamod_merged[~near_mer_mask]
            near_mer_data = datamod_merged[near_mer_mask]
            
            # Create trace for markers away from MER region (normal size)
            if len(away_from_mer_data) > 0:
                normal_trace = go.Scattergl(
                    x=away_from_mer_data['RIGHT_ASCENSION_CLUSTER'],
                    y=away_from_mer_data['DECLINATION_CLUSTER'],
                    mode='markers',
                    marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
                    name=f'Merged Data ({algorithm}) - {len(away_from_mer_data)} clusters',
                    text=[
                        f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                        for snr, cz, ra, dec in zip(away_from_mer_data['SNR_CLUSTER'], 
                                                  away_from_mer_data['Z_CLUSTER'], 
                                                  away_from_mer_data['RIGHT_ASCENSION_CLUSTER'], 
                                                  away_from_mer_data['DECLINATION_CLUSTER'])
                    ],
                    hoverinfo='text'
                )
                data_traces.append(normal_trace)
            
            # Create trace for markers near MER region (enhanced size with highlight)
            if len(near_mer_data) > 0:
                # Add glow effect trace first (background)
                glow_trace = self._create_glow_trace(
                    near_mer_data['RIGHT_ASCENSION_CLUSTER'],
                    near_mer_data['DECLINATION_CLUSTER'],
                    28
                )
                data_traces.append(glow_trace)
                
                # Add main enhanced trace (foreground)
                enhanced_trace = go.Scattergl(
                    x=near_mer_data['RIGHT_ASCENSION_CLUSTER'],
                    y=near_mer_data['DECLINATION_CLUSTER'],
                    mode='markers',
                    marker=dict(
                        size=20, 
                        symbol='square-open', 
                        line=dict(width=3, color='yellow'),  # Bright yellow highlight
                        color='black',
                        opacity=1.0
                    ),
                    name=f'Merged Data (Enhanced) - {len(near_mer_data)} clusters',
                    text=[
                        f"merged (enhanced)<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                        for snr, cz, ra, dec in zip(near_mer_data['SNR_CLUSTER'], 
                                                  near_mer_data['Z_CLUSTER'], 
                                                  near_mer_data['RIGHT_ASCENSION_CLUSTER'], 
                                                  near_mer_data['DECLINATION_CLUSTER'])
                    ],
                    hoverinfo='text'
                )
                data_traces.append(enhanced_trace)
                
                print(f"Debug: Enhanced {len(near_mer_data)} merged clusters near MER data, {len(away_from_mer_data)} normal")
    
    def _create_tile_traces_and_polygons(self, data: Dict[str, Any], polygon_traces: List,
                                        show_polygons: bool, show_mer_tiles: bool,
                                        snr_threshold_lower: Optional[float], 
                                        snr_threshold_upper: Optional[float],
                                        mer_points: Optional[List] = None) -> List:
        """Create individual tile traces with proximity-based enhancement."""
        tile_traces = []
        
        for tileid, value in data['tile_data'].items():
            tile_data = value['data']
            
            # Apply SNR filtering to tile data
            datamod = self._apply_snr_filtering(tile_data, snr_threshold_lower, snr_threshold_upper)
            
            if mer_points is None:
                # No MER data - create single trace with normal markers
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
                # MER data present - create separate traces based on proximity to MER points
                near_mer_mask = np.array([
                    self._is_point_near_mer_region(ra, dec, mer_points) 
                    for ra, dec in zip(datamod['RIGHT_ASCENSION_CLUSTER'], 
                                     datamod['DECLINATION_CLUSTER'])
                ])
                
                away_from_mer_data = datamod[~near_mer_mask]
                near_mer_data = datamod[near_mer_mask]
                
                # Create trace for markers away from MER region (normal size)
                if len(away_from_mer_data) > 0:
                    normal_trace = go.Scattergl(
                        x=away_from_mer_data['RIGHT_ASCENSION_CLUSTER'],
                        y=away_from_mer_data['DECLINATION_CLUSTER'],
                        mode='markers',
                        marker=dict(size=6, opacity=1, symbol='x', color=self.colors_list[int(tileid)]),
                        name=f'Tile {tileid}',
                        text=[
                            f"TileID: {tileid}<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                            for snr, cz, ra, dec in zip(away_from_mer_data['SNR_CLUSTER'], away_from_mer_data['Z_CLUSTER'], 
                                                      away_from_mer_data['RIGHT_ASCENSION_CLUSTER'], away_from_mer_data['DECLINATION_CLUSTER'])
                        ],
                        hoverinfo='text'
                    )
                    tile_traces.append(normal_trace)
                
                # Create trace for markers near MER region (enhanced size with highlight)
                if len(near_mer_data) > 0:
                    # Add glow effect trace first (background)
                    glow_trace = self._create_glow_trace(
                        near_mer_data['RIGHT_ASCENSION_CLUSTER'],
                        near_mer_data['DECLINATION_CLUSTER'],
                        23
                    )
                    tile_traces.append(glow_trace)
                    
                    # Add main enhanced trace (foreground)
                    enhanced_trace = go.Scattergl(
                        x=near_mer_data['RIGHT_ASCENSION_CLUSTER'],
                        y=near_mer_data['DECLINATION_CLUSTER'],
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
                            for snr, cz, ra, dec in zip(near_mer_data['SNR_CLUSTER'], near_mer_data['Z_CLUSTER'], 
                                                      near_mer_data['RIGHT_ASCENSION_CLUSTER'], near_mer_data['DECLINATION_CLUSTER'])
                        ],
                        hoverinfo='text'
                    )
                    tile_traces.append(enhanced_trace)
                    
                    print(f"Debug: Tile {tileid} - Enhanced {len(near_mer_data)} markers near MER data, {len(away_from_mer_data)} normal")
            
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
