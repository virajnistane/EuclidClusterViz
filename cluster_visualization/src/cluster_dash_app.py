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
        self.setup_layout()
        self.setup_callbacks()
        
    def load_data(self, select_algorithm='PZWAV'):
        """Load and prepare all data for visualization"""
        if select_algorithm in self.data_cache:
            return self.data_cache[select_algorithm]
            
        print(f"Loading data for algorithm: {select_algorithm}")
        
        # Configuration
        snrthreshold = None
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
        
        # Apply SNR filtering
        if snrthreshold is None and snrthreshold_upper is None:
            datamod_merged = data_merged
        elif snrthreshold is not None and snrthreshold_upper is not None:
            datamod_merged = data_merged[(data_merged['SNR_CLUSTER'] > snrthreshold) & 
                                         (data_merged['SNR_CLUSTER'] < snrthreshold_upper)]
        elif snrthreshold_upper is not None and snrthreshold is None:
            datamod_merged = data_merged[data_merged['SNR_CLUSTER'] < snrthreshold_upper]
        elif snrthreshold is not None:
            datamod_merged = data_merged[data_merged['SNR_CLUSTER'] > snrthreshold]
        
        print(f"Loaded {len(datamod_merged)} merged clusters")
        
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
            'merged_data': datamod_merged,
            'tile_data': data_by_tile,
            'catred_info': catred_fileinfo_df,
            'algorithm': select_algorithm,
            'snr_threshold': snrthreshold,
            'data_dir': mergedetcat_datadir
        }
        
        # Cache the data
        self.data_cache[select_algorithm] = data
        return data

    def get_radec_mertile(self, mertileid):
        """Load CATRED data"""
        if isinstance(mertileid, str):
            mertileid = int(mertileid)
        with fits.open(self.data_cache['catred_info'].loc[mertileid]['fits_file']) as hdul:
            data = hdul[1].data
        return data['RIGHT_ASCENSION'], data['DECLINATION']

    # def set_mer_tiles_scatter_data(self, x_coords, y_coords):
    #     """Set the x,y coordinates for high-resolution MER tiles scatter data
        
    #     Args:
    #         x_coords (list): List of RIGHT_ASCENSION coordinates
    #         y_coords (list): List of DECLINATION coordinates
    #     """
    #     if len(x_coords) != len(y_coords):
    #         raise ValueError("x_coords and y_coords must have the same length")
        
    #     self.data_cache['mer_scatter_x'] = x_coords
    #     self.data_cache['mer_scatter_y'] = y_coords
    #     print(f"✓ MER tiles scatter data set: {len(x_coords)} data points")

    def create_traces(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, show_catred_mertile_data=False):
        """Create all Plotly traces"""
        traces = []
        data_traces = []  # Keep data traces separate to add them last (top layer)
        
        # Check zoom level for high-resolution MER tiles data
        zoom_threshold_met = False
        if relayout_data and show_mer_tiles:
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
            
            # Check if zoom level is less than 2 degrees in both RA and DEC
            if ra_range is not None and dec_range is not None and ra_range < 2.0 and dec_range < 2.0:
                zoom_threshold_met = True
        
        # Merged data trace - will be added to top layer
        merged_trace = go.Scattergl(
            x=data['merged_data']['RIGHT_ASCENSION_CLUSTER'],
            y=data['merged_data']['DECLINATION_CLUSTER'],
            mode='markers',
            marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
            name=f'Merged Data ({data["algorithm"]})',
            text=[
                f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
                for snr, cz, ra, dec in zip(data['merged_data']['SNR_CLUSTER'], 
                                          data['merged_data']['Z_CLUSTER'], 
                                          data['merged_data']['RIGHT_ASCENSION_CLUSTER'], 
                                          data['merged_data']['DECLINATION_CLUSTER'])
            ],
            hoverinfo='text'
        )
        data_traces.append(merged_trace)
        
        # Individual tiles traces and polygons
        for tileid, value in data['tile_data'].items():
            tile_data = value['data']
            
            # Apply SNR filtering (same as merged data logic)
            if data['snr_threshold'] is None:
                datamod = tile_data
            else:
                datamod = tile_data[tile_data['SNR_CLUSTER'] > data['snr_threshold']]
            
            # Tile data trace - will be added to top layer
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
            data_traces.append(tile_trace)
            
            # Always load tile definition and create polygons
            with open(os.path.join(data['data_dir'], value['tilefile']), 'r') as f:
                tile = json.load(f)
            
            # LEV1 polygon - always show outline
            poly = tile['LEV1']['POLYGON'][0]
            poly_x = [p[0] for p in poly] + [poly[0][0]]
            poly_y = [p[1] for p in poly] + [poly[0][1]]
            level1_trace = go.Scatter(
                x=poly_x,
                y=poly_y,
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)], dash='dash'),
                name=f'Tile {tileid} LEV1',
                showlegend=False,
                text=f'Tile {tileid} - LEV1 Polygon',
                hoverinfo='text'
            )
            traces.append(level1_trace)
            
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
                
            core_trace = go.Scatter(
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
            traces.append(core_trace)
            
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
        
        # High-resolution MER tiles scatter data (when zoomed in < 2 degrees)
        if show_mer_tiles and zoom_threshold_met and show_catred_mertile_data:
            # Get high-resolution scatter data from cache if available
            
            mer_scatter_x = []
            mer_scatter_y = []

            if 'catred_info' in data and not data['catred_info'].empty and 'polygon' in data['catred_info'].columns:
                # Get current zoom ranges
                if relayout_data:
                    if 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
                        ra_min = relayout_data['xaxis.range[0]']
                        ra_max = relayout_data['xaxis.range[1]']
                    elif 'xaxis.range' in relayout_data:
                        ra_min = relayout_data['xaxis.range'][0]
                        ra_max = relayout_data['xaxis.range'][1]
                    else:
                        ra_min = None
                        ra_max = None

                    if 'yaxis.range[0]' in relayout_data and 'yaxis.range[1]' in relayout_data:
                        dec_min = relayout_data['yaxis.range[0]']
                        dec_max = relayout_data['yaxis.range[1]']
                    elif 'yaxis.range' in relayout_data:
                        dec_min = relayout_data['yaxis.range'][0]
                        dec_max = relayout_data['yaxis.range'][1]
                    else:
                        dec_min = None
                        dec_max = None

                    # Find mertileids whose polygons are within the current zoom box
                    for mertileid, row in data['catred_info'].iterrows():
                        poly = row['polygon']
                        if poly is not None:
                            x, y = poly.exterior.xy
                            # Check if any vertex is inside the zoom box
                            if ra_min is not None and ra_max is not None and dec_min is not None and dec_max is not None:
                                if any((ra_min <= px <= ra_max) and (dec_min <= py <= dec_max) for px, py in zip(x, y)):
                                    # Add all vertices of this polygon to scatter data
                                    # mertiles_in_zoom = data['catred_info'].loc[mertileid]
                                    ra_coords, dec_coords = self.get_radec_mertile(mertileid)
                                    mer_scatter_x.extend(ra_coords)
                                    mer_scatter_y.extend(dec_coords)
                                    
                                
            
            if mer_scatter_x and mer_scatter_y:  # Only add trace if data is available
                mer_scatter_trace = go.Scattergl(
                    x=mer_scatter_x,
                    y=mer_scatter_y,
                    mode='markers',
                    marker=dict(size=4, symbol='circle', color='red', opacity=0.7),
                    name='MER Tiles High-Res Data',
                    # text=[f'MER Data Point {i+1}<br>RA: {x:.6f}<br>Dec: {y:.6f}' 
                    #       for i, (x, y) in enumerate(zip(mer_scatter_x, mer_scatter_y))],
                    # hoverinfo='text',
                    showlegend=True
                )
                data_traces.append(mer_scatter_trace)

        # Combine traces: polygon traces first (bottom layer), then data traces (top layer)
        # This ensures data points and their hover info are always visible on top
        return traces + data_traces
        


        # Combine traces: polygon traces first (bottom layer), then data traces (top layer)
        # This ensures data points and their hover info are always visible on top
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
                                    html.Label("Polygon Fill:"),
                                    dbc.Switch(
                                        id="polygon-switch",
                                        label="Fill polygons",
                                        value=True,
                                    )
                                ], width=3),
                                
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
                                ], width=3)
                            ]),
                            
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Show CATRED MER Tile Data:"),
                                    dbc.Switch(
                                        id="catred-mertile-switch",
                                        label="High-res MER data",
                                        value=False,
                                    ),
                                    html.Small("(When zoomed < 2°)", className="text-muted")
                                ], width=3),
                                
                                dbc.Col([], width=9)  # Empty columns to maintain layout
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
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData')]
        )
        def update_plot(n_clicks, algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data):
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
                
                # Create traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data)
                
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
                
                # Status info
                mer_status = ""
                if show_mer_tiles and not show_polygons:
                    mer_status = " | MER tiles: ON"
                elif show_mer_tiles and show_polygons:
                    mer_status = " | MER tiles: OFF (fill mode)"
                else:
                    mer_status = " | MER tiles: OFF"
                
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['merged_data'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
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
            Output('render-button', 'children'),
            [Input('algorithm-dropdown', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value'),
             Input('render-button', 'n_clicks')]
        )
        def update_button_text(algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks):
            if n_clicks == 0:
                return "🚀 Initial Render"
            else:
                return "✅ Live Updates Active"

        # Callback for real-time option updates (preserves zoom)
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('algorithm-dropdown', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value')],
            [State('render-button', 'n_clicks'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def update_plot_options(algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, relayout_data, current_figure):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update
            
            try:
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Create traces
                traces = self.create_traces(data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data)
                
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
                
                # Status info
                mer_status = ""
                if show_mer_tiles and not show_polygons:
                    mer_status = " | MER tiles: ON"
                elif show_mer_tiles and show_polygons:
                    mer_status = " | MER tiles: OFF (fill mode)"
                else:
                    mer_status = " | MER tiles: OFF"
                
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['merged_data'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
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
