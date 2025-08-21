#!/usr/bin/env python3
"""
Cluster Visualization Dash App

A self-contained Dash application for interactive cluster detection data visualization.
This app runs as a web server and automatically opens in browser without manual intervention.

Features:
- Algorithm switching (PZWAV/AMICO)
- Manual render control with interactive button
- Always-visible polygon outlines with fill toggle
- MER tile display (only available with outline polygons for better visibility)
- Configurable aspect ratio: free (flexible zoom, default) or equal (astronomical accuracy)
- Responsive plot sizing with 1200x900 dimensions

REQUIREMENTS:
- Must activate EDEN environment first: source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
- This provides required packages: astropy, plotly, pandas, numpy, shapely, dash
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from astropy.io import fits
from shapely.geometry import Polygon as ShapelyPolygon
import webbrowser
import threading
import time

import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objs as go
import dash_bootstrap_components as dbc

def check_environment():
    """Check if EDEN environment is activated and required modules are available"""
    # Check EDEN environment
    eden_path = "/cvmfs/euclid-dev.in2p3.fr/EDEN-3.1"
    eden_active = eden_path in os.environ.get('PATH', '')
    
    if not eden_active:
        print("⚠️  WARNING: EDEN environment not detected!")
        print("   For best compatibility, activate EDEN environment first:")
        print(f"   source {eden_path}/bin/activate")
        print("")
    
    # Check critical modules
    missing_modules = []
    try:
        import dash
        import dash_bootstrap_components
        import plotly
        print("✓ Dash modules available")
    except ImportError as e:
        missing_modules.append(f"Dash modules: {e}")
    
    try:
        import pandas
        import numpy
        print("✓ Data processing modules available")
    except ImportError as e:
        missing_modules.append(f"Data modules: {e}")
    
    try:
        from astropy.io import fits
        import shapely
        print("✓ Scientific modules available")
    except ImportError as e:
        missing_modules.append(f"Scientific modules: {e}")
    
    if missing_modules:
        print("⚠️  ERROR: Missing required modules!")
        for module in missing_modules:
            print(f"   - {module}")
        print("")
        print("   Solutions:")
        print("   1. Use virtual environment: ./cluster_visualization/scripts/run_dash_app_venv.sh")
        print("   2. Setup virtual environment: ./setup_venv.sh")
        print("   3. Install manually: pip install dash dash-bootstrap-components")
        print("")
        return False
    
    print("✓ All required modules available")
    return True

# Check environment before imports
if not check_environment():
    sys.exit(1)

# Add project root to path for configuration import
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import configuration
try:
    from config import get_config
    config = get_config()
    print("✓ Configuration loaded successfully")
    USE_CONFIG = True
except ImportError as e:
    print(f"⚠️  Configuration not found: {e}")
    print("   Using fallback hardcoded paths")
    USE_CONFIG = False

# Add local utils path
if USE_CONFIG:
    utils_path = config.utils_dir
else:
    # Fallback: look for mypackage in the user's home directory
    utils_path = os.path.join(os.path.expanduser('~'), 'mypackage')

if utils_path not in sys.path:
    sys.path.append(utils_path)

# Import utilities with error handling
try:
    from myutils import get_xml_element
    from colordefinitions import colors_list, colors_list_transparent
    print(f"✓ Utilities loaded from: {utils_path}")
except ImportError as e:
    print(f"⚠️  Error importing utilities: {e}")
    print(f"   Searched in: {utils_path}")
    print("   Please ensure myutils.py and colordefinitions.py are available")
    sys.exit(1)

class ClusterVisualizationApp:
    def __init__(self):
        self.app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
        self.data_cache = {}
        self.mer_traces_cache = []  # Store accumulated MER scatter traces
        self.setup_layout()
        self.setup_callbacks()
        
    def load_data(self, select_algorithm='PZWAV'):
        """Load and prepare all data for visualization"""
        if select_algorithm in self.data_cache:
            return self.data_cache[select_algorithm]
            
        print(f"Loading data for algorithm: {select_algorithm}")
        
        # Configuration
        snrthreshold_lower = None
        snrthreshold_upper = None
        
        # Validate algorithm choice
        if select_algorithm not in ['PZWAV', 'AMICO']:
            print(f"Warning: Unknown algorithm '{select_algorithm}'. Using 'PZWAV' as default.")
            select_algorithm = 'PZWAV'
        
        # Use configuration for paths if available, otherwise fallback to hardcoded paths
        if USE_CONFIG:
            mergedetcatdir = config.mergedetcat_dir
            mergedetcat_datadir = config.mergedetcat_data_dir
            mergedetcat_inputsdir = config.mergedetcat_inputs_dir
            mergedetcatoutputdir = config.get_output_dir(select_algorithm)
            rr2downloadsdir = config.rr2_downloads_dir
            print("✓ Using configuration-based paths")
        else:
            # Fallback to hardcoded paths
            mergedetcatdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/'
            mergedetcat_datadir = os.path.join(mergedetcatdir, 'data')
            mergedetcat_inputsdir = os.path.join(mergedetcatdir, 'inputs')
            mergedetcatoutputdir = os.path.join(mergedetcatdir, f'outvn_mergedetcat_rr2south_{select_algorithm}_3')
            rr2downloadsdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads'
            print("⚠️  Using fallback hardcoded paths")
        
        # Validate critical paths exist
        if not os.path.exists(mergedetcatoutputdir):
            raise FileNotFoundError(f"Output directory not found: {mergedetcatoutputdir}")
        if not os.path.exists(mergedetcat_datadir):
            raise FileNotFoundError(f"Data directory not found: {mergedetcat_datadir}")
        
        # Load merged detection catalog
        det_xml = os.path.join(mergedetcatoutputdir, 'mergedetcat.xml')
        if not os.path.exists(det_xml):
            raise FileNotFoundError(f"Merged detection XML not found: {det_xml}")
            
        fitsfile = os.path.join(mergedetcat_datadir, 
                               get_xml_element(det_xml, 'Data/ClustersFile/DataContainer/FileName').text)
        
        print(f"Loading merged catalog from: {os.path.basename(fitsfile)}")
        with fits.open(fitsfile) as hdul:
            data_merged = hdul[1].data
        
        print(f"Loaded {len(data_merged)} merged clusters")
        
        # Load individual detection files
        if USE_CONFIG:
            indiv_detfiles_list = config.get_detfiles_list(select_algorithm)
        else:
            indiv_detfiles_list = os.path.join(mergedetcatdir, f'detfiles_input_{select_algorithm.lower()}_3.json')
        
        if not os.path.exists(indiv_detfiles_list):
            raise FileNotFoundError(f"Detection files list not found: {indiv_detfiles_list}")
            
        with open(indiv_detfiles_list, 'r') as f:
            detfiles_list = json.load(f)
        
        data_by_tile = {}
        for file in detfiles_list:
            tile_file = get_xml_element(os.path.join(mergedetcat_inputsdir, file), 
                                      'Data/SpatialInformation/DataContainer/FileName').text
            tile_id = tile_file.split('TILE_')[1][3:5]
            fits_file = get_xml_element(os.path.join(mergedetcat_inputsdir, file), 
                                      'Data/ClustersFile/DataContainer/FileName').text
            
            data_by_tile[tile_id] = {
                'tilefile': tile_file,
                'fitsfilename': fits_file
            }
            
            with fits.open(os.path.join(mergedetcat_datadir, fits_file)) as hdul:
                data_by_tile[tile_id]['data'] = hdul[1].data
        
        data_by_tile = dict(sorted(data_by_tile.items()))
        print(f"Loaded {len(data_by_tile)} individual tiles")
        
        # Load catred file info using configuration
        if USE_CONFIG:
            catred_fileinfo_csv = config.get_catred_fileinfo_csv()
            catred_polygon_pkl = config.get_catred_polygons_pkl()
        else:
            catred_fileinfo_csv = os.path.join(rr2downloadsdir, 'catred_fileinfo.csv')
            catred_polygon_pkl = os.path.join(rr2downloadsdir, 'catred_polygons_by_tileid.pkl')
        
        catred_fileinfo_df = pd.DataFrame()
        if os.path.exists(catred_fileinfo_csv):
            catred_fileinfo_df = pd.read_csv(catred_fileinfo_csv)
            catred_fileinfo_df.set_index('tileid', inplace=True)
            print("Loaded catred file info")
        else:
            print(f"Warning: catred_fileinfo.csv not found at {catred_fileinfo_csv}")
        
        # Load catred polygons
        if os.path.exists(catred_polygon_pkl) and not catred_fileinfo_df.empty:
            with open(catred_polygon_pkl, 'rb') as f:
                catred_fileinfo_dict = pickle.load(f)
            catred_fileinfo_df['polygon'] = pd.Series(catred_fileinfo_dict)
            print("Loaded catred polygons")
        else:
            print(f"Warning: catred polygons not found at {catred_polygon_pkl}")
        
        data = {
            'merged_data': data_merged,  # Store raw unfiltered data
            'tile_data': data_by_tile,
            'catred_info': catred_fileinfo_df,
            'algorithm': select_algorithm,
            'snr_threshold_lower': snrthreshold_lower,
            'snr_threshold_upper': snrthreshold_upper,
            'data_dir': mergedetcat_datadir
        }
        
        # Cache the data
        self.data_cache[select_algorithm] = data
        return data

    def get_radec_mertile(self, mertileid, data):
        """Load CATRED data for a specific MER tile
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info
            
        Returns:
            tuple: (ra_coords, dec_coords) or ([], []) if unable to load
        """
        try:
            if isinstance(mertileid, str):
                mertileid = int(mertileid)
            
            # Check if we have the necessary data
            if 'catred_info' not in data or data['catred_info'].empty:
                print(f"Debug: No catred_info available for mertile {mertileid}")
                return [], []
            
            if mertileid not in data['catred_info'].index:
                print(f"Debug: MerTile {mertileid} not found in catred_info")
                return [], []
            
            mertile_row = data['catred_info'].loc[mertileid]
            
            # Check if fits_file column exists
            if 'fits_file' not in mertile_row or pd.isna(mertile_row['fits_file']):
                print(f"Debug: No fits_file for mertile {mertileid}, using polygon vertices as demo data")
                # Fallback: use polygon vertices as demonstration data
                if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
                    poly = mertile_row['polygon']
                    x_coords, y_coords = poly.exterior.xy
                    return list(x_coords), list(y_coords)
                else:
                    return [], []
            
            # Try to load actual FITS file
            fits_path = mertile_row['fits_file']
            if not os.path.exists(fits_path):
                print(f"Debug: FITS file not found at {fits_path}, using polygon vertices")
                # Fallback to polygon vertices
                if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
                    poly = mertile_row['polygon']
                    x_coords, y_coords = poly.exterior.xy
                    return list(x_coords), list(y_coords)
                else:
                    return [], []
            
            # Load actual FITS data
            with fits.open(fits_path) as hdul:
                fits_data = hdul[1].data
                return fits_data['RIGHT_ASCENSION'].tolist(), fits_data['DECLINATION'].tolist()
                
        except Exception as e:
            print(f"Debug: Error loading MER tile {mertileid}: {e}")
            # Fallback: try to use polygon vertices
            try:
                if mertileid in data['catred_info'].index:
                    mertile_row = data['catred_info'].loc[mertileid]
                    if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
                        poly = mertile_row['polygon']
                        x_coords, y_coords = poly.exterior.xy
                        print(f"Debug: Using polygon vertices for MER tile {mertileid} ({len(x_coords)} points)")
                        return list(x_coords), list(y_coords)
            except Exception as fallback_error:
                print(f"Debug: Fallback also failed for MER tile {mertileid}: {fallback_error}")
            
            return [], []

    def load_mer_scatter_data(self, data, relayout_data):
        """Load MER scatter data for the current zoom window
        
        Args:
            data: The main data dictionary
            relayout_data: Current zoom/pan state
            
        Returns:
            tuple: (mer_scatter_x, mer_scatter_y) lists of coordinates
        """
        mer_scatter_x = []
        mer_scatter_y = []
        
        if 'catred_info' not in data or data['catred_info'].empty or 'polygon' not in data['catred_info'].columns:
            print("Debug: No catred_info data available for MER scatter")
            return mer_scatter_x, mer_scatter_y
        
        if not relayout_data:
            print("Debug: No relayout data available for MER scatter")
            return mer_scatter_x, mer_scatter_y
        
        # Get current zoom ranges from relayout_data
        ra_min = ra_max = dec_min = dec_max = None
        
        if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            ra_min = relayout_data['xaxis.range[0]']
            ra_max = relayout_data['xaxis.range[1]']
        elif 'xaxis.range' in relayout_data:
            ra_min = relayout_data['xaxis.range'][0]
            ra_max = relayout_data['xaxis.range'][1]

        if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
            dec_min = relayout_data['yaxis.range[0]']
            dec_max = relayout_data['yaxis.range[1]']
        elif 'yaxis.range' in relayout_data:
            dec_min = relayout_data['yaxis.range'][0]
            dec_max = relayout_data['yaxis.range'][1]

        print(f"Debug: Loading MER data for zoom box - RA: [{ra_min}, {ra_max}], Dec: [{dec_min}, {dec_max}]")

        # Find mertileids whose polygons intersect with the current zoom box
        mertiles_to_load = []
        for mertileid, row in data['catred_info'].iterrows():
            poly = row['polygon']
            if poly is not None and ra_min is not None and ra_max is not None and dec_min is not None and dec_max is not None:
                x, y = poly.exterior.xy
                # Check if any vertex is inside the zoom box
                if any((ra_min <= px <= ra_max) and (dec_min <= py <= dec_max) for px, py in zip(x, y)):
                    mertiles_to_load.append(mertileid)

        print(f"Debug: Found {len(mertiles_to_load)} MER tiles in zoom area: {mertiles_to_load[:5]}{'...' if len(mertiles_to_load) > 5 else ''}")

        # Load data for each MER tile in the zoom area
        for mertileid in mertiles_to_load:
            ra_coords, dec_coords = self.get_radec_mertile(mertileid, data)
            if ra_coords and dec_coords:
                mer_scatter_x.extend(ra_coords)
                mer_scatter_y.extend(dec_coords)
                print(f"Debug: Added {len(ra_coords)} points from MER tile {mertileid}")
        
        print(f"Debug: Total MER scatter points loaded: {len(mer_scatter_x)}")
        return mer_scatter_x, mer_scatter_y

    def create_traces(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, show_catred_mertile_data=False, manual_mer_data=None, existing_mer_traces=None, snr_threshold_lower=None, snr_threshold_upper=None):
        """Create all Plotly traces
        
        Args:
            manual_mer_data: Tuple of (mer_scatter_x, mer_scatter_y) for manually loaded MER data
            existing_mer_traces: List of existing MER scatter traces to preserve
            snr_threshold_lower: Lower SNR threshold for filtering
            snr_threshold_upper: Upper SNR threshold for filtering
        """
        traces = []
        data_traces = []  # Keep data traces separate to add them last (top layer)
        
        # Apply SNR filtering to merged data
        if snr_threshold_lower is None and snr_threshold_upper is None:
            datamod_merged = data['merged_data']
        elif snr_threshold_lower is not None and snr_threshold_upper is not None:
            datamod_merged = data['merged_data'][(data['merged_data']['SNR_CLUSTER'] >= snr_threshold_lower) & 
                                                 (data['merged_data']['SNR_CLUSTER'] <= snr_threshold_upper)]
        elif snr_threshold_upper is not None and snr_threshold_lower is None:
            datamod_merged = data['merged_data'][data['merged_data']['SNR_CLUSTER'] <= snr_threshold_upper]
        elif snr_threshold_lower is not None:
            datamod_merged = data['merged_data'][data['merged_data']['SNR_CLUSTER'] >= snr_threshold_lower]
        else:
            datamod_merged = data['merged_data']
        
        # Check zoom level for high-resolution MER tiles data
        zoom_threshold_met = False
        if relayout_data and show_mer_tiles:
            print(f"Debug: Checking zoom threshold - relayout_data: {relayout_data}")
            # Extract zoom ranges from relayout_data
            ra_range = None
            dec_range = None
            
            if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                ra_range = abs(relayout_data['xaxis.range[1]'] - relayout_data['xaxis.range[0]'])
            elif 'xaxis.range' in relayout_data:
                ra_range = abs(relayout_data['xaxis.range'][1] - relayout_data['xaxis.range'][0])
                
            if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                dec_range = abs(relayout_data['yaxis.range[1]'] - relayout_data['yaxis.range[0]'])
            elif 'yaxis.range' in relayout_data:
                dec_range = abs(relayout_data['yaxis.range'][1] - relayout_data['yaxis.range'][0])
            
            print(f"Debug: Zoom ranges - RA: {ra_range}, Dec: {dec_range}")
            
            # Check if zoom level is less than 2 degrees in both RA and DEC
            if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
                zoom_threshold_met = True
                print(f"Debug: Zoom threshold MET! RA: {ra_range:.3f}° < 2°, Dec: {dec_range:.3f}° < 2°")
            else:
                print(f"Debug: Zoom threshold NOT met. RA: {ra_range}, Dec: {dec_range}")
        else:
            print(f"Debug: Zoom check skipped - relayout_data: {relayout_data is not None}, show_mer_tiles: {show_mer_tiles}")
        
        print(f"Debug: Final zoom_threshold_met: {zoom_threshold_met}, show_catred_mertile_data: {show_catred_mertile_data}")
        
        # Create data traces in the desired order: 1. MER traces (bottom), 2. merged trace (middle), 3. tile traces (top)
        
        # 1. BOTTOM LAYER: Add existing MER traces from previous renders
        if existing_mer_traces:
            print(f"Debug: Adding {len(existing_mer_traces)} existing MER traces to bottom layer")
            data_traces.extend(existing_mer_traces)

        # 2. BOTTOM LAYER: High-resolution MER tiles scatter data (manual render mode)
        if show_mer_tiles and show_catred_mertile_data and manual_mer_data:
            mer_scatter_x, mer_scatter_y = manual_mer_data
            print(f"Debug: Using manually loaded MER scatter data with {len(mer_scatter_x)} points")
            
            # Add the scatter trace if we have data
            if mer_scatter_x and mer_scatter_y:
                print(f"Debug: Creating MER scatter trace with {len(mer_scatter_x)} points")
                
                # Create unique name for this MER trace based on current number of existing traces
                trace_number = len(self.mer_traces_cache) + 1
                trace_name = f'MER High-Res Data #{trace_number}'
                
                mer_catred_trace = go.Scattergl(
                    x=mer_scatter_x,
                    y=mer_scatter_y,
                    mode='markers',
                    marker=dict(size=4, symbol='circle', color='black', opacity=0.5),
                    name=trace_name,
                    text=[f'MER Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}' 
                          for x, y in zip(mer_scatter_x, mer_scatter_y)],
                    hoverinfo='text',
                    showlegend=True
                )
                data_traces.append(mer_catred_trace)
                print("Debug: MER CATRED trace added to bottom layer")
            else:
                print("Debug: No MER scatter data available to display")
        elif show_mer_tiles and show_catred_mertile_data and zoom_threshold_met:
            print(f"Debug: MER scatter conditions met but no manual data provided - use render button")
        else:
            print(f"Debug: MER scatter data conditions not met - show_mer_tiles: {show_mer_tiles}, show_catred_mertile_data: {show_catred_mertile_data}, manual_data: {manual_mer_data is not None}")

        # 3. MIDDLE LAYER: Merged data trace
        merged_det_trace = go.Scattergl(
            x=datamod_merged['RIGHT_ASCENSION_CLUSTER'],
            y=datamod_merged['DECLINATION_CLUSTER'],
            mode='markers',
            marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
            name=f'Merged Data ({data["algorithm"]}) - {len(datamod_merged)} clusters',
            text=[
                f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                for snr, cz, ra, dec in zip(datamod_merged['SNR_CLUSTER'], 
                                          datamod_merged['Z_CLUSTER'], 
                                          datamod_merged['RIGHT_ASCENSION_CLUSTER'], 
                                          datamod_merged['DECLINATION_CLUSTER'])
            ],
            hoverinfo='text'
        )
        data_traces.append(merged_det_trace)
        
        # Store tile traces separately to add them as the top layer
        det_in_tile_trace = []
        
        # Individual tiles traces and polygons
        for tileid, value in data['tile_data'].items():
            tile_data = value['data']
            
            # Apply SNR filtering (same as merged data logic)
            if snr_threshold_lower is None and snr_threshold_upper is None:
                datamod = tile_data
            elif snr_threshold_lower is not None and snr_threshold_upper is not None:
                datamod = tile_data[(tile_data['SNR_CLUSTER'] >= snr_threshold_lower) & 
                                   (tile_data['SNR_CLUSTER'] <= snr_threshold_upper)]
            elif snr_threshold_upper is not None and snr_threshold_lower is None:
                datamod = tile_data[tile_data['SNR_CLUSTER'] <= snr_threshold_upper]
            elif snr_threshold_lower is not None:
                datamod = tile_data[tile_data['SNR_CLUSTER'] >= snr_threshold_lower]
            else:
                datamod = tile_data
            
            # 4. TOP LAYER: Tile data trace - will be added last for maximum visibility
            tile_trace = go.Scattergl(
                x=datamod['RIGHT_ASCENSION_CLUSTER'],
                y=datamod['DECLINATION_CLUSTER'],
                mode='markers',
                marker=dict(size=6, opacity=1, symbol='x', color=colors_list[int(tileid)]),
                name=f'Tile {tileid}',
                text=[
                    f"TileID: {tileid}<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                    for snr, cz, ra, dec in zip(datamod['SNR_CLUSTER'], datamod['Z_CLUSTER'], 
                                              datamod['RIGHT_ASCENSION_CLUSTER'], datamod['DECLINATION_CLUSTER'])
                ],
                hoverinfo='text'
            )
            det_in_tile_trace.append(tile_trace)  # Add to separate list for now
            
            # Always load tile definition and create polygons
            with open(os.path.join(data['data_dir'], value['tilefile']), 'r') as f:
                tile = json.load(f)
            
            # LEV1 polygon - always show outline
            poly = tile['LEV1']['POLYGON'][0]
            poly_x = [p[0] for p in poly] + [poly[0][0]]
            poly_y = [p[1] for p in poly] + [poly[0][1]]
            cltile_lev1_polygon_trace = go.Scatter(
                x=poly_x,
                y=poly_y,
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)], dash='dash'),
                name=f'Tile {tileid} LEV1',
                showlegend=False,
                text=f'Tile {tileid} - LEV1 Polygon',
                hoverinfo='text'
            )
            traces.append(cltile_lev1_polygon_trace)
            
            # CORE polygon
            poly2 = tile['CORE']['POLYGON'][0]
            poly_x2 = [p[0] for p in poly2] + [poly2[0][0]]
            poly_y2 = [p[1] for p in poly2] + [poly2[0][1]]
            
            # Always show polygon outline, toggle fill based on show_polygons
            if show_polygons:
                fillcolor = colors_list_transparent[int(tileid)]
                fill = 'toself'
            else:
                fillcolor = None
                fill = None
                
            cltile_core_polygon_trace = go.Scatter(
                x=poly_x2,
                y=poly_y2,
                fill=fill,
                fillcolor=fillcolor,
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)]),
                name=f'Tile {tileid} CORE',
                showlegend=False,
                text=f'Tile {tileid} - CORE Polygon',
                hoverinfo='text'
            )
            traces.append(cltile_core_polygon_trace)
            
            # MER tile polygons (only show when polygons are in outline mode and requested)
            if show_mer_tiles and not show_polygons and not data['catred_info'].empty and 'polygon' in data['catred_info'].columns:
                for mertileid in tile['LEV1']['ID_INTERSECTED']:
                    if mertileid in data['catred_info'].index:
                        merpoly = data['catred_info'].at[mertileid, 'polygon']
                        if merpoly is not None:
                            x, y = merpoly.exterior.xy
                            mertile_trace = go.Scatter(
                                x=list(x),
                                y=list(y),
                                fill='toself',
                                fillcolor=colors_list_transparent[int(tileid)],
                                mode='lines',
                                line=dict(width=2, color=colors_list[int(tileid)], dash='dot'),
                                name=f'MerTile {mertileid}',
                                showlegend=False,
                                text=f'MerTile {mertileid} - CLtile {tileid}',
                                hoverinfo='text',
                                hoveron='fills+points'
                            )
                            traces.append(mertile_trace)
        
        # 4. TOP LAYER: Add tile traces last for maximum visibility
        data_traces.extend(det_in_tile_trace)
        
        # Combine traces: polygon traces first (bottom layer), then data traces in order:
        # 1. MER CATRED traces (bottom)
        # 2. Merged detection trace (middle) 
        # 3. Detection in tile traces (top)
        return traces + data_traces

    def setup_layout(self):
        """Setup the Dash app layout"""
        self.app.layout = dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H1("Cluster Detection Visualization", className="text-center mb-4"),
                    html.Hr()
                ])
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Visualization Controls", className="card-title"),
                            html.P("Options update in real-time while preserving your current zoom level", 
                                   className="text-muted small mb-3"),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Algorithm:"),
                                    dcc.Dropdown(
                                        id='algorithm-dropdown',
                                        options=[
                                            {'label': 'PZWAV', 'value': 'PZWAV'},
                                            {'label': 'AMICO', 'value': 'AMICO'}
                                        ],
                                        value='PZWAV',
                                        clearable=False
                                    )
                                ], width=3),
                                
                                dbc.Col([
                                    html.Label("SNR Lower Threshold:"),
                                    dcc.Input(
                                        id='snr-lower-input',
                                        type='number',
                                        placeholder='Min SNR',
                                        value=None,
                                        step=0.1,
                                        className='form-control'
                                    ),
                                    html.Small("(Leave empty for no lower limit)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([
                                    html.Label("SNR Upper Threshold:"),
                                    dcc.Input(
                                        id='snr-upper-input',
                                        type='number',
                                        placeholder='Max SNR',
                                        value=None,
                                        step=0.1,
                                        className='form-control'
                                    ),
                                    html.Small("(Leave empty for no upper limit)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([
                                    html.Label("Polygon Fill:"),
                                    dbc.Switch(
                                        id="polygon-switch",
                                        label="Fill polygons",
                                        value=False,
                                    )
                                ], width=3)
                            ]),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Show MER Tiles:"),
                                    dbc.Switch(
                                        id="mer-switch",
                                        label="Show MER tiles",
                                        value=False,
                                    ),
                                    html.Small("(Only with outline polygons)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([
                                    html.Label("Aspect Ratio:"),
                                    dbc.Switch(
                                        id="aspect-ratio-switch",
                                        label="Free aspect ratio",
                                        value=True,
                                    ),
                                    html.Small("(Default: flexible zoom)", className="text-muted")
                                ], width=3),
                                dbc.Col([
                                    html.Label("Show CATRED MER Tile Data:"),
                                    dbc.Switch(
                                        id="catred-mertile-switch",
                                        label="High-res MER data",
                                        value=False,
                                    ),
                                    html.Small("(When zoomed < 2°)", className="text-muted")
                                ], width=3)
                            ]),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Manual MER Data Render:"),
                                    dbc.Button(
                                        "🔍 Render MER Data",
                                        id="mer-render-button",
                                        color="info",
                                        size="sm",
                                        className="w-100",
                                        n_clicks=0,
                                        disabled=True
                                    ),
                                    html.Small("(Zoom in first, then click)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([
                                    html.Label("Clear MER Data:"),
                                    dbc.Button(
                                        "🗑️ Clear All MER",
                                        id="mer-clear-button",
                                        color="warning",
                                        size="sm",
                                        className="w-100",
                                        n_clicks=0
                                    ),
                                    html.Small("(Remove all MER traces)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([], width=3),  # Empty column
                                dbc.Col([], width=3)   # Empty column
                            ]),
                            
                            html.Hr(),
                            
                            dbc.Row([
                                dbc.Col([
                                    dbc.Button(
                                        "� Initial Render",
                                        id="render-button",
                                        color="primary",
                                        size="lg",
                                        className="w-100 mt-2",
                                        n_clicks=0
                                    ),
                                    html.Small("After initial render, options update automatically", 
                                              className="text-muted d-block text-center mt-1")
                                ], width=12)
                            ])
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            dbc.Row([
                dbc.Col([
                    dcc.Loading(
                        id="loading",
                        children=[
                            dcc.Graph(
                                id='cluster-plot',
                                style={'height': '900px', 'width': '100%'},
                                config={
                                    'displayModeBar': True,
                                    'displaylogo': False,
                                    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                    'responsive': True
                                }
                            )
                        ],
                        type="circle"
                    )
                ])
            ]),
            
            dbc.Row([
                dbc.Col([
                    html.Div(id="status-info", className="mt-3")
                ])
            ])
            
        ], fluid=True)

    def setup_callbacks(self):
        """Setup Dash callbacks"""
        @self.app.callback(
            [Output('cluster-plot', 'figure'), Output('status-info', 'children')],
            [Input('render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-lower-input', 'value'),
             State('snr-upper-input', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData')]
        )
        def update_plot(n_clicks, algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data):
            # Only render if button has been clicked at least once
            if n_clicks == 0:
                # Initial empty figure
                initial_fig = go.Figure()
                
                # Configure aspect ratio based on setting
                if free_aspect_ratio:
                    # Free aspect ratio - no constraints
                    xaxis_config = dict(visible=False)
                    yaxis_config = dict(visible=False)
                else:
                    # Equal aspect ratio - astronomical accuracy
                    xaxis_config = dict(
                        scaleanchor="y",
                        scaleratio=1,
                        constrain="domain",
                        visible=False
                    )
                    yaxis_config = dict(
                        constrain="domain",
                        visible=False
                    )
                
                initial_fig.update_layout(
                    title='',
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True,
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Select your preferred algorithm and display options above,<br>then click the 'Render Visualization' button to generate the plot.",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=16, color="gray")
                        )
                    ]
                )
                
                initial_status = dbc.Alert([
                    html.H6("Ready to render", className="mb-1"),
                    html.P("Click 'Initial Render' to begin. After that, options will update automatically while preserving your zoom level.", className="mb-0")
                ], color="secondary", className="mt-2")
                
                return initial_fig, initial_status
            
            try:
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Reset MER traces cache for fresh render
                self.mer_traces_cache = []
                
                # Create traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = go.Figure(traces)
                
                # Configure aspect ratio based on setting
                if free_aspect_ratio:
                    # Free aspect ratio - no constraints, better for zooming
                    xaxis_config = dict(visible=True)
                    yaxis_config = dict(visible=True)
                else:
                    # Equal aspect ratio - astronomical accuracy
                    xaxis_config = dict(
                        scaleanchor="y",
                        scaleratio=1,
                        constrain="domain",
                        visible=True
                    )
                    yaxis_config = dict(
                        constrain="domain",
                        visible=True
                    )
                
                fig.update_layout(
                    title=f'Cluster Detection Visualization - {algorithm}',
                    xaxis_title='Right Ascension (degrees)',
                    yaxis_title='Declination (degrees)',
                    legend=dict(
                        title='Legend',
                        orientation='v',
                        xanchor='left',
                        x=1.02,
                        yanchor='top',
                        y=1
                    ),
                    hovermode='closest',
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True
                )
                
                # Preserve zoom state if available
                if relayout_data and any(key in relayout_data for key in ['xaxis.range[0]', 'xaxis.range[1]', 'yaxis.range[0]', 'yaxis.range[1]']):
                    # Extract zoom ranges from relayoutData
                    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                        fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
                    if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                        fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
                elif relayout_data and 'xaxis.range' in relayout_data:
                    # Handle different relayoutData format
                    fig.update_xaxes(range=relayout_data['xaxis.range'])
                    if 'yaxis.range' in relayout_data:
                        fig.update_yaxes(range=relayout_data['yaxis.range'])
                
                # Calculate filtered cluster counts for status
                if snr_lower is None and snr_upper is None:
                    filtered_merged_count = len(data['merged_data'])
                elif snr_lower is not None and snr_upper is not None:
                    filtered_merged_count = len(data['merged_data'][(data['merged_data']['SNR_CLUSTER'] >= snr_lower) & 
                                                                   (data['merged_data']['SNR_CLUSTER'] <= snr_upper)])
                elif snr_upper is not None and snr_lower is None:
                    filtered_merged_count = len(data['merged_data'][data['merged_data']['SNR_CLUSTER'] <= snr_upper])
                elif snr_lower is not None:
                    filtered_merged_count = len(data['merged_data'][data['merged_data']['SNR_CLUSTER'] >= snr_lower])
                else:
                    filtered_merged_count = len(data['merged_data'])
                
                # Status info
                mer_status = ""
                if show_mer_tiles and not show_polygons:
                    mer_status = " | MER tiles: ON"
                elif show_mer_tiles and show_polygons:
                    mer_status = " | MER tiles: OFF (fill mode)"
                else:
                    mer_status = " | MER tiles: OFF"
                
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                # Format SNR filter status
                snr_filter_text = "No SNR filtering"
                if snr_lower is not None and snr_upper is not None:
                    snr_filter_text = f"SNR: {snr_lower} ≤ SNR ≤ {snr_upper}"
                elif snr_lower is not None:
                    snr_filter_text = f"SNR ≥ {snr_lower}"
                elif snr_upper is not None:
                    snr_filter_text = f"SNR ≤ {snr_upper}"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {filtered_merged_count}/{len(data['merged_data'])} (filtered)", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
                    html.P(f"SNR Filter: {snr_filter_text}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"Rendered at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="success", className="mt-2")
                
                return fig, status
                
            except Exception as e:
                error_fig = go.Figure()
                error_fig.add_annotation(
                    text=f"Error loading data: {str(e)}",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, xanchor='center', yanchor='middle',
                    showarrow=False,
                    font=dict(size=16, color="red")
                )
                error_fig.update_layout(
                    title="Error Loading Visualization",
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    autosize=True
                )
                
                error_status = dbc.Alert(
                    f"Error: {str(e)}",
                    color="danger"
                )
                
                return error_fig, error_status

        # Callback to update button text based on current settings
        @self.app.callback(
            [Output('render-button', 'children'), Output('mer-render-button', 'children')],
            [Input('algorithm-dropdown', 'value'),
             Input('snr-lower-input', 'value'),
             Input('snr-upper-input', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value'),
             Input('render-button', 'n_clicks'),
             Input('mer-render-button', 'n_clicks')]
        )
        def update_button_texts(algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, mer_n_clicks):
            main_button_text = "🚀 Initial Render" if n_clicks == 0 else "✅ Live Updates Active"
            mer_button_text = f"� Render MER Data ({mer_n_clicks})" if mer_n_clicks > 0 else "🔍 Render MER Data"
            return main_button_text, mer_button_text

        # Callback to update clear button text
        @self.app.callback(
            Output('mer-clear-button', 'children'),
            [Input('mer-clear-button', 'n_clicks')]
        )
        def update_clear_button_text(clear_n_clicks):
            return f"🗑️ Clear All MER ({clear_n_clicks})" if clear_n_clicks > 0 else "🗑️ Clear All MER"

        # Callback for real-time option updates (preserves zoom)
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('algorithm-dropdown', 'value'),
             Input('snr-lower-input', 'value'),
             Input('snr-upper-input', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value')],
            [State('render-button', 'n_clicks'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def update_plot_options(algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, relayout_data, current_figure):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update
            
            try:
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Extract existing MER traces from current figure to preserve them
                existing_mer_traces = []
                if current_figure and 'data' in current_figure:
                    for trace in current_figure['data']:
                        # Look for existing MER traces by name pattern
                        if (isinstance(trace, dict) and 
                            'name' in trace and 
                            trace['name'] and 
                            ('MER High-Res Data' in trace['name'] or 'MER Tiles High-Res Data' in trace['name'])):
                            # Convert dict to Scattergl object for consistency
                            existing_trace = go.Scattergl(
                                x=trace.get('x', []),
                                y=trace.get('y', []),
                                mode=trace.get('mode', 'markers'),
                                marker=trace.get('marker', {}),
                                name=trace.get('name', 'MER Data'),
                                text=trace.get('text', []),
                                hoverinfo=trace.get('hoverinfo', 'text'),
                                showlegend=trace.get('showlegend', True)
                            )
                            existing_mer_traces.append(existing_trace)
                
                print(f"Debug: Options update - preserving {len(existing_mer_traces)} MER traces")
                
                # Create traces with existing MER traces preserved
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                                          existing_mer_traces=existing_mer_traces, snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = go.Figure(traces)
                
                # Configure aspect ratio based on setting
                if free_aspect_ratio:
                    # Free aspect ratio - no constraints, better for zooming
                    xaxis_config = dict(visible=True)
                    yaxis_config = dict(visible=True)
                else:
                    # Equal aspect ratio - astronomical accuracy
                    xaxis_config = dict(
                        scaleanchor="y",
                        scaleratio=1,
                        constrain="domain",
                        visible=True
                    )
                    yaxis_config = dict(
                        constrain="domain",
                        visible=True
                    )
                
                fig.update_layout(
                    title=f'Cluster Detection Visualization - {algorithm}',
                    xaxis_title='Right Ascension (degrees)',
                    yaxis_title='Declination (degrees)',
                    legend=dict(
                        title='Legend',
                        orientation='v',
                        xanchor='left',
                        x=1.02,
                        yanchor='top',
                        y=1
                    ),
                    hovermode='closest',
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True
                )
                
                # Preserve zoom state from current figure or relayoutData
                if relayout_data and any(key in relayout_data for key in ['xaxis.range[0]', 'xaxis.range[1]', 'yaxis.range[0]', 'yaxis.range[1]']):
                    # Extract zoom ranges from relayoutData
                    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                        fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
                    if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                        fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
                elif relayout_data and 'xaxis.range' in relayout_data:
                    # Handle different relayoutData format
                    fig.update_xaxes(range=relayout_data['xaxis.range'])
                    if 'yaxis.range' in relayout_data:
                        fig.update_yaxes(range=relayout_data['yaxis.range'])
                elif current_figure and 'layout' in current_figure:
                    # Fallback: try to preserve from current figure layout
                    current_layout = current_figure['layout']
                    if 'xaxis' in current_layout and 'range' in current_layout['xaxis']:
                        fig.update_xaxes(range=current_layout['xaxis']['range'])
                    if 'yaxis' in current_layout and 'range' in current_layout['yaxis']:
                        fig.update_yaxes(range=current_layout['yaxis']['range'])
                
                # Calculate filtered cluster counts for status
                if snr_lower is None and snr_upper is None:
                    filtered_merged_count = len(data['merged_data'])
                elif snr_lower is not None and snr_upper is not None:
                    filtered_merged_count = len(data['merged_data'][(data['merged_data']['SNR_CLUSTER'] >= snr_lower) & 
                                                                   (data['merged_data']['SNR_CLUSTER'] <= snr_upper)])
                elif snr_upper is not None and snr_lower is None:
                    filtered_merged_count = len(data['merged_data'][data['merged_data']['SNR_CLUSTER'] <= snr_upper])
                elif snr_lower is not None:
                    filtered_merged_count = len(data['merged_data'][data['merged_data']['SNR_CLUSTER'] >= snr_lower])
                else:
                    filtered_merged_count = len(data['merged_data'])
                
                # Status info
                mer_status = ""
                if show_mer_tiles and not show_polygons:
                    mer_status = " | MER tiles: ON"
                elif show_mer_tiles and show_polygons:
                    mer_status = " | MER tiles: OFF (fill mode)"
                else:
                    mer_status = " | MER tiles: OFF"
                
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                # Format SNR filter status
                snr_filter_text = "No SNR filtering"
                if snr_lower is not None and snr_upper is not None:
                    snr_filter_text = f"SNR: {snr_lower} ≤ SNR ≤ {snr_upper}"
                elif snr_lower is not None:
                    snr_filter_text = f"SNR ≥ {snr_lower}"
                elif snr_upper is not None:
                    snr_filter_text = f"SNR ≤ {snr_upper}"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {filtered_merged_count}/{len(data['merged_data'])} (filtered)", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
                    html.P(f"SNR Filter: {snr_filter_text}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"Updated at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="info", className="mt-2")
                
                return fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error updating: {str(e)}",
                    color="warning"
                )
                return dash.no_update, error_status

        # Callback to enable/disable MER render button based on zoom level
        @self.app.callback(
            Output('mer-render-button', 'disabled'),
            [Input('cluster-plot', 'relayoutData'),
             Input('mer-switch', 'value'),
             Input('catred-mertile-switch', 'value')],
            [State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def update_mer_button_state(relayout_data, show_mer_tiles, show_catred_mertile_data, n_clicks):
            # Only enable if main app has been rendered and conditions are met
            if n_clicks == 0:
                return True  # Disabled
            
            if not show_mer_tiles or not show_catred_mertile_data:
                return True  # Disabled - switches not turned on
            
            if not relayout_data:
                return True  # Disabled - no zoom data
            
            # Check zoom level
            ra_range = None
            dec_range = None
            
            if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                ra_range = abs(relayout_data['xaxis.range[1]'] - relayout_data['xaxis.range[0]'])
            elif 'xaxis.range' in relayout_data:
                ra_range = abs(relayout_data['xaxis.range'][1] - relayout_data['xaxis.range'][0])
                
            if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                dec_range = abs(relayout_data['yaxis.range[1]'] - relayout_data['yaxis.range[0]'])
            elif 'yaxis.range' in relayout_data:
                dec_range = abs(relayout_data['yaxis.range'][1] - relayout_data['yaxis.range'][0])
            
            # Enable button if zoomed in enough
            if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
                return False  # Enabled
            else:
                return True   # Disabled - not zoomed in enough

        # Callback for manual MER data rendering
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('mer-render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-lower-input', 'value'),
             State('snr-upper-input', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def manual_render_mer_data(mer_n_clicks, algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data, current_figure):
            if mer_n_clicks == 0:
                return dash.no_update, dash.no_update
            
            print(f"Debug: Manual MER render button clicked (click #{mer_n_clicks})")
            
            try:
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Load MER scatter data for current zoom window
                mer_scatter_x, mer_scatter_y = self.load_mer_scatter_data(data, relayout_data)
                
                # Extract existing MER traces from current figure to preserve them
                existing_mer_traces = []
                if current_figure and 'data' in current_figure:
                    for trace in current_figure['data']:
                        # Look for existing MER traces by name pattern
                        if (isinstance(trace, dict) and 
                            'name' in trace and 
                            trace['name'] and 
                            ('MER High-Res Data' in trace['name'] or 'MER Tiles High-Res Data' in trace['name'])):
                            # Convert dict to Scattergl object for consistency
                            existing_trace = go.Scattergl(
                                x=trace.get('x', []),
                                y=trace.get('y', []),
                                mode=trace.get('mode', 'markers'),
                                marker=trace.get('marker', {}),
                                name=trace.get('name', 'MER Data'),
                                text=trace.get('text', []),
                                hoverinfo=trace.get('hoverinfo', 'text'),
                                showlegend=trace.get('showlegend', True)
                            )
                            existing_mer_traces.append(existing_trace)
                            print(f"Debug: Preserved existing MER trace: {trace['name']}")
                
                print(f"Debug: Found {len(existing_mer_traces)} existing MER traces to preserve")
                
                # Create traces with the manually loaded MER data and existing traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data, 
                                          manual_mer_data=(mer_scatter_x, mer_scatter_y), existing_mer_traces=existing_mer_traces,
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Update the MER traces cache with the new trace count
                if mer_scatter_x and mer_scatter_y:
                    self.mer_traces_cache.extend(existing_mer_traces)
                    # Add the new trace placeholder (actual trace is created in create_traces)
                    self.mer_traces_cache.append(None)  # Placeholder for the new trace
                
                # Create figure
                fig = go.Figure(traces)
                
                # Configure aspect ratio based on setting
                if free_aspect_ratio:
                    xaxis_config = dict(visible=True)
                    yaxis_config = dict(visible=True)
                else:
                    xaxis_config = dict(
                        scaleanchor="y",
                        scaleratio=1,
                        constrain="domain",
                        visible=True
                    )
                    yaxis_config = dict(
                        constrain="domain",
                        visible=True
                    )
                
                fig.update_layout(
                    title=f'Cluster Detection Visualization - {algorithm}',
                    xaxis_title='Right Ascension (degrees)',
                    yaxis_title='Declination (degrees)',
                    legend=dict(
                        title='Legend',
                        orientation='v',
                        xanchor='left',
                        x=1.02,
                        yanchor='top',
                        y=1
                    ),
                    hovermode='closest',
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True
                )
                
                # Preserve zoom state
                if relayout_data:
                    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                        fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
                    elif 'xaxis.range' in relayout_data:
                        fig.update_xaxes(range=relayout_data['xaxis.range'])
                        
                    if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                        fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
                    elif 'yaxis.range' in relayout_data:
                        fig.update_yaxes(range=relayout_data['yaxis.range'])
                
                # Status info
                total_mer_traces = len(existing_mer_traces) + (1 if mer_scatter_x and mer_scatter_y else 0)
                mer_status = f" | MER high-res data: {len(mer_scatter_x)} points in {total_mer_traces} regions"
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['merged_data'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"MER data rendered at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="success", className="mt-2")
                
                return fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error rendering MER data: {str(e)}",
                    color="danger"
                )
                return dash.no_update, error_status

        # Callback for clearing all MER data
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('mer-clear-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-lower-input', 'value'),
             State('snr-upper-input', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('render-button', 'n_clicks')],
            prevent_initial_call=True
        )
        def clear_mer_data(clear_n_clicks, algorithm, snr_lower, snr_upper, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data, render_n_clicks):
            if clear_n_clicks == 0 or render_n_clicks == 0:
                return dash.no_update, dash.no_update
            
            print(f"Debug: Clear MER data button clicked (click #{clear_n_clicks})")
            
            try:
                # Clear MER traces cache
                self.mer_traces_cache = []
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Create traces without any MER data
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Create figure
                fig = go.Figure(traces)
                
                # Configure aspect ratio based on setting
                if free_aspect_ratio:
                    xaxis_config = dict(visible=True)
                    yaxis_config = dict(visible=True)
                else:
                    xaxis_config = dict(
                        scaleanchor="y",
                        scaleratio=1,
                        constrain="domain",
                        visible=True
                    )
                    yaxis_config = dict(
                        constrain="domain",
                        visible=True
                    )
                
                fig.update_layout(
                    title=f'Cluster Detection Visualization - {algorithm}',
                    xaxis_title='Right Ascension (degrees)',
                    yaxis_title='Declination (degrees)',
                    legend=dict(
                        title='Legend',
                        orientation='v',
                        xanchor='left',
                        x=1.02,
                        yanchor='top',
                        y=1
                    ),
                    hovermode='closest',
                    height=900,
                    width=1200,
                    margin=dict(l=60, r=200, t=60, b=60),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True
                )
                
                # Preserve zoom state
                if relayout_data:
                    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                        fig.update_xaxes(range=[relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']])
                    elif 'xaxis.range' in relayout_data:
                        fig.update_xaxes(range=relayout_data['xaxis.range'])
                        
                    if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                        fig.update_yaxes(range=[relayout_data['yaxis.range[0]'], relayout_data['yaxis.range[1]']])
                    elif 'yaxis.range' in relayout_data:
                        fig.update_yaxes(range=relayout_data['yaxis.range'])
                
                # Status info
                mer_status = " | MER high-res data: cleared"
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['merged_data'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"MER data cleared at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="warning", className="mt-2")
                
                return fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error clearing MER data: {str(e)}",
                    color="danger"
                )
                return dash.no_update, error_status

    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""
        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f'http://localhost:{port}')
        
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host='localhost', port=8050, debug=False, auto_open=True, external_access=False):
        """Run the Dash app"""
        # If external_access is True, bind to all interfaces and don't auto-open browser
        if external_access:
            host = '0.0.0.0'
            auto_open = False
        
        if auto_open:
            self.open_browser(port)
        
        print("=== Cluster Visualization Dash App ===")
        if external_access:
            print(f"Starting server for external access on port {port}")
            print("Access from your local machine using:")
            print(f"  - SSH tunnel: ssh -L {port}:localhost:{port} username@this-server")
            print(f"  - Then open: http://localhost:{port} in your local browser")
            print("NOTE: Keep the SSH connection alive while using the app")
        else:
            print(f"Starting server at: http://{host}:{port}")
        print("Loading data and setting up visualization...")
        print("Press Ctrl+C to stop the server")
        print("")
        
        self.app.run_server(
            host=host,
            port=port,
            debug=debug,
            dev_tools_hot_reload=False,
            dev_tools_ui=False,
            dev_tools_props_check=False
        )

def main():
    """Main function to run the app"""
    import sys
    
    # Check for external access flag
    external_access = '--external' in sys.argv or '--remote' in sys.argv
    
    app = ClusterVisualizationApp()
    
    # Example: Set high-resolution MER tiles scatter data
    # You can call this method with your x,y coordinates like this:
    # app.set_mer_tiles_scatter_data(
    #     x_coords=[12.345, 12.346, 12.347],  # RIGHT_ASCENSION coordinates
    #     y_coords=[0.123, 0.124, 0.125]     # DECLINATION coordinates
    # )
    
    # Try different ports if default is busy
    for port in [8050, 8051, 8052]:
        try:
            app.run(port=port, debug=False, auto_open=False, external_access=external_access)
            break
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"Port {port} is busy, trying next port...")
                continue
            else:
                raise e

if __name__ == '__main__':
    main()
