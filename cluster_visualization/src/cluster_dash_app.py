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
from shapely.geometry import Polygon as ShapelyPolygon, box
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
    from .config import get_config
    config = get_config()
    print("✓ Configuration loaded successfully")
    USE_CONFIG = True
except ImportError:
    # Try direct import if relative import fails
    try:
        from config import get_config
        config = get_config()
        print("✓ Configuration loaded successfully")
        USE_CONFIG = True
    except ImportError as e:
        print(f"⚠️  Configuration not found: {e}")
        print("   Using fallback hardcoded paths")
        USE_CONFIG = False

# Add local data modules path
data_modules_path = os.path.join(os.path.dirname(__file__), 'data')
if data_modules_path not in sys.path:
    sys.path.append(data_modules_path)

# Import data handling modules
try:
    from .data.loader import DataLoader
    from .data.mer_handler import MERHandler
    print("✓ Data modules loaded successfully")
except ImportError:
    # Try alternative import path
    try:
        sys.path.append(os.path.dirname(__file__))
        from data.loader import DataLoader
        from data.mer_handler import MERHandler
        print("✓ Data modules loaded successfully (alternative path)")
    except ImportError as e:
        print(f"⚠️  Error importing data modules: {e}")
        print("   Falling back to inline data handling")
        DataLoader = None
        MERHandler = None

# Import visualization modules
try:
    from .visualization.traces import TraceCreator
    from .visualization.figures import FigureManager
    print("✓ Visualization modules loaded successfully")
except ImportError:
    # Try alternative import path
    try:
        sys.path.append(os.path.dirname(__file__))
        from visualization.traces import TraceCreator
        from visualization.figures import FigureManager
        print("✓ Visualization modules loaded successfully (alternative path)")
    except ImportError as e:
        print(f"⚠️  Error importing visualization modules: {e}")
        print("   Falling back to inline visualization handling")
        TraceCreator = None
        FigureManager = None

# Import callback modules
try:
    from .callbacks.main_plot import MainPlotCallbacks
    from .callbacks.mer_callbacks import MERCallbacks
    from .callbacks.ui_callbacks import UICallbacks
    from .callbacks.phz_callbacks import PHZCallbacks
    print("✓ Callback modules loaded successfully")
except ImportError:
    # Try alternative import path
    try:
        sys.path.append(os.path.dirname(__file__))
        from callbacks.main_plot import MainPlotCallbacks
        from callbacks.mer_callbacks import MERCallbacks
        from callbacks.ui_callbacks import UICallbacks
        from callbacks.phz_callbacks import PHZCallbacks
        print("✓ Callback modules loaded successfully (alternative path)")
    except ImportError as e:
        print(f"⚠️  Error importing callback modules: {e}")
        print("   Falling back to inline callback handling")
        MainPlotCallbacks = None
        MERCallbacks = None
        UICallbacks = None
        PHZCallbacks = None

# Import UI and core modules
try:
    from .ui.layout import AppLayout
    print("✓ UI layout module loaded successfully")
except ImportError:
    # Try alternative import path
    try:
        sys.path.append(os.path.dirname(__file__))
        from ui.layout import AppLayout
        print("✓ UI layout module loaded successfully (alternative path)")
    except ImportError as e:
        print(f"⚠️  Error importing UI layout module: {e}")
        print("   Falling back to inline layout handling")
        AppLayout = None

try:
    from .core.app import ClusterVisualizationCore
    print("✓ Core module loaded successfully")
except ImportError:
    # Try alternative import path
    try:
        sys.path.append(os.path.dirname(__file__))
        from core.app import ClusterVisualizationCore
        print("✓ Core module loaded successfully (alternative path)")
    except ImportError as e:
        print(f"⚠️  Error importing core module: {e}")
        print("   Falling back to inline core functionality")
        ClusterVisualizationCore = None

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
        
        # Always initialize fallback attributes since we're using fallback callbacks
        self.data_cache = {}
        self.mer_traces_cache = []
        self.current_mer_data = None
        
        # Initialize data handling modules
        if USE_CONFIG and DataLoader and MERHandler:
            self.data_loader = DataLoader(config, USE_CONFIG)
            self.mer_handler = MERHandler()
            print("✓ Using modular data handlers")
        else:
            # Fallback to inline data handling
            self.data_loader = None
            self.mer_handler = None
            print("⚠️  Using fallback inline data handling")
        
        # Initialize visualization modules
        if TraceCreator and FigureManager:
            self.trace_creator = TraceCreator(colors_list, colors_list_transparent, self.mer_handler)
            self.figure_manager = FigureManager()
            print("✓ Using modular visualization handlers")
        else:
            # Fallback to inline visualization handling
            self.trace_creator = None
            self.figure_manager = None
            print("⚠️  Using fallback inline visualization handling")
        
        # Initialize UI layout
        if AppLayout:
            self.app.layout = AppLayout.create_layout()
            print("✓ Using modular UI layout")
        else:
            self.setup_layout()
            print("⚠️  Using fallback inline layout")
        
        # Initialize callbacks
        self.setup_callbacks()
        
        # Initialize core application manager
        if ClusterVisualizationCore:
            self.core = ClusterVisualizationCore(self.app)
            print("✓ Using modular core manager")
        else:
            self.core = None
            print("⚠️  Using fallback core functionality")
        
    def load_data(self, select_algorithm='PZWAV'):
        """Load and prepare all data for visualization"""
        if self.data_loader:
            # Use modular data loader
            return self.data_loader.load_data(select_algorithm)
        else:
            # Fallback to original inline implementation
            return self._load_data_fallback(select_algorithm)
    
    def create_traces(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, 
                     show_catred_mertile_data=False, manual_mer_data=None, existing_mer_traces=None, 
                     snr_threshold_lower=None, snr_threshold_upper=None):
        """Create all Plotly traces - delegates to trace creator"""
        if self.trace_creator:
            return self.trace_creator.create_traces(
                data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                manual_mer_data, existing_mer_traces, snr_threshold_lower, snr_threshold_upper
            )
        else:
            # Fallback to original implementation
            return self._create_traces_fallback(
                data, show_polygons, show_mer_tiles, relayout_data, show_catred_mertile_data,
                manual_mer_data, existing_mer_traces, snr_threshold_lower, snr_threshold_upper
            )
    
    def _create_traces_fallback(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, 
                               show_catred_mertile_data=False, manual_mer_data=None, existing_mer_traces=None, 
                               snr_threshold_lower=None, snr_threshold_upper=None):
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
        
        # Calculate SNR min/max for slider bounds
        snr_min = float(data_merged['SNR_CLUSTER'].min())
        snr_max = float(data_merged['SNR_CLUSTER'].max())
        print(f"SNR range: {snr_min:.3f} to {snr_max:.3f}")
        
        data = {
            'merged_data': data_merged,  # Store raw unfiltered data
            'tile_data': data_by_tile,
            'catred_info': catred_fileinfo_df,
            'algorithm': select_algorithm,
            'snr_threshold_lower': snrthreshold_lower,
            'snr_threshold_upper': snrthreshold_upper,
            'snr_min': snr_min,
            'snr_max': snr_max,
            'data_dir': mergedetcat_datadir
        }
        
        # Cache the data
        self.data_cache[select_algorithm] = data
        return data

    def get_radec_mertile(self, mertileid, data):
        """Load CATRED data for a specific MER tile - delegates to MER handler"""
        if self.mer_handler:
            return self.mer_handler.get_radec_mertile(mertileid, data)
        else:
            # Fallback to original implementation
            return self._get_radec_mertile_fallback(mertileid, data)
    
    def load_mer_scatter_data(self, data, relayout_data):
        """Load MER scatter data for the current zoom window - delegates to MER handler"""
        if self.mer_handler:
            return self.mer_handler.load_mer_scatter_data(data, relayout_data)
        else:
            # Fallback to original implementation
            return self._load_mer_scatter_data_fallback(data, relayout_data)
    
    def _get_radec_mertile_fallback(self, mertileid, data):
        """Load CATRED data for a specific MER tile
        
        Args:
            mertileid: The MER tile ID
            data: The data dictionary containing catred_info
            
        Returns:
            dict: Dictionary with keys 'RIGHT_ASCENSION', 'DECLINATION', 'PHZ_MODE_1', 'PHZ_70_INT', 'PHZ_PDF'
                  or empty dict {} if unable to load
        """
        try:
            if isinstance(mertileid, str):
                mertileid = int(mertileid)
            
            # Check if we have the necessary data
            if 'catred_info' not in data or data['catred_info'].empty:
                print(f"Debug: No catred_info available for mertile {mertileid}")
                return {}
            
            if mertileid not in data['catred_info'].index:
                print(f"Debug: MerTile {mertileid} not found in catred_info")
                return {}
            
            mertile_row = data['catred_info'].loc[mertileid]
            
            # Check if fits_file column exists
            if 'fits_file' not in mertile_row or pd.isna(mertile_row['fits_file']):
                print(f"Debug: No fits_file for mertile {mertileid}, using polygon vertices as demo data")
                # Fallback: use polygon vertices as demonstration data
                if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
                    poly = mertile_row['polygon']
                    x_coords, y_coords = poly.exterior.xy
                    return {
                        'RIGHT_ASCENSION': list(x_coords),
                        'DECLINATION': list(y_coords),
                        'PHZ_MODE_1': [0.0] * len(x_coords),  # Dummy scalar values
                        'PHZ_70_INT': [[0.0, 0.0]] * len(x_coords),  # Dummy interval pairs
                        'PHZ_PDF': [[0.0] * 10] * len(x_coords)      # Dummy PDF vectors
                    }
                else:
                    return {}
            
            # Try to load actual FITS file
            fits_path = mertile_row['fits_file']
            if not os.path.exists(fits_path):
                print(f"Debug: FITS file not found at {fits_path}, using polygon vertices")
                # Fallback to polygon vertices
                if 'polygon' in mertile_row and mertile_row['polygon'] is not None:
                    poly = mertile_row['polygon']
                    x_coords, y_coords = poly.exterior.xy
                    return {
                        'RIGHT_ASCENSION': list(x_coords),
                        'DECLINATION': list(y_coords),
                        'PHZ_MODE_1': [0.0] * len(x_coords),  # Dummy scalar values
                        'PHZ_70_INT': [[0.0, 0.0]] * len(x_coords),  # Dummy interval pairs
                        'PHZ_PDF': [[0.0] * 10] * len(x_coords)      # Dummy PDF vectors
                    }
                else:
                    return {}
            
            # Load actual FITS data
            with fits.open(fits_path) as hdul:
                fits_data = hdul[1].data
                
                # Extract the required columns
                result = {
                    'RIGHT_ASCENSION': fits_data['RIGHT_ASCENSION'].tolist(),
                    'DECLINATION': fits_data['DECLINATION'].tolist()
                }
                
                # Add photometric redshift columns if they exist
                for col in ['PHZ_MODE_1', 'PHZ_70_INT', 'PHZ_PDF']:
                    if col in fits_data.columns.names:
                        col_data = fits_data[col]
                        # Handle different column types
                        if col == 'PHZ_PDF':
                            # Keep PHZ_PDF as raw vectors - don't process
                            result[col] = [row.tolist() if hasattr(row, 'tolist') else row for row in col_data]
                        elif col == 'PHZ_70_INT':
                            # For PHZ_70_INT, store the raw vectors for difference calculation
                            if col_data.ndim > 1:
                                result[col] = [row.tolist() if hasattr(row, 'tolist') else row for row in col_data]
                            else:
                                # If it's scalar, convert to list format for consistency
                                result[col] = [[float(val), float(val)] for val in col_data]
                        else:
                            # For PHZ_MODE_1 and other scalar columns
                            if col_data.ndim > 1:
                                # Take first element if it's a vector
                                result[col] = [float(row[0]) if len(row) > 0 else 0.0 for row in col_data]
                            else:
                                # Scalar column
                                result[col] = col_data.tolist()
                    else:
                        # Provide dummy values if column doesn't exist
                        print(f"Debug: Column {col} not found in {fits_path}, using dummy values")
                        if col == 'PHZ_PDF':
                            result[col] = [[0.0] * 10] * len(result['RIGHT_ASCENSION'])  # Dummy vector
                        elif col == 'PHZ_70_INT':
                            result[col] = [[0.0, 0.0]] * len(result['RIGHT_ASCENSION'])  # Dummy interval
                        else:
                            result[col] = [0.0] * len(result['RIGHT_ASCENSION'])
                
                return result
                
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
                        return {
                            'RIGHT_ASCENSION': list(x_coords),
                            'DECLINATION': list(y_coords),
                            'PHZ_MODE_1': [0.0] * len(x_coords),  # Dummy scalar values
                            'PHZ_70_INT': [[0.0, 0.0]] * len(x_coords),  # Dummy interval pairs
                            'PHZ_PDF': [[0.0] * 10] * len(x_coords)      # Dummy PDF vectors
                        }
            except Exception as fallback_error:
                print(f"Debug: Fallback also failed for MER tile {mertileid}: {fallback_error}")
            
            return {}

    def load_mer_scatter_data(self, data, relayout_data):
        """Load MER scatter data for the current zoom window
        
        Args:
            data: The main data dictionary
            relayout_data: Current zoom/pan state
            
        Returns:
            dict: Dictionary with keys 'ra', 'dec', 'phz_mode_1', 'phz_70_int', 'phz_pdf'
        """
        mer_scatter_data = {
            'ra': [],
            'dec': [],
            'phz_mode_1': [],
            'phz_70_int': [],
            'phz_pdf': []
        }

        if 'catred_info' not in data or data['catred_info'].empty or 'polygon' not in data['catred_info'].columns:
            print("Debug: No catred_info data available for MER scatter")
            return mer_scatter_data
        
        if not relayout_data:
            print("Debug: No relayout data available for MER scatter")
            return mer_scatter_data
        
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
        if ra_min is not None and ra_max is not None and dec_min is not None and dec_max is not None:
            # Create a zoom box polygon for proper intersection testing
            zoom_box = box(ra_min, dec_min, ra_max, dec_max)
            
            for mertileid, row in data['catred_info'].iterrows():
                poly = row['polygon']
                if poly is not None:
                    # Use proper geometric intersection: checks if polygons overlap in any way
                    # This handles cases where zoom box is inside polygon, polygon is inside zoom box,
                    # or they partially overlap
                    if poly.intersects(zoom_box):
                        mertiles_to_load.append(mertileid)

        print(f"Debug: Found {len(mertiles_to_load)} MER tiles in zoom area: {mertiles_to_load[:5]}{'...' if len(mertiles_to_load) > 5 else ''}")

        # Load data for each MER tile in the zoom area
        for mertileid in mertiles_to_load:
            tile_data = self.get_radec_mertile(mertileid, data)
            if tile_data and 'RIGHT_ASCENSION' in tile_data:
                mer_scatter_data['ra'].extend(tile_data['RIGHT_ASCENSION'])
                mer_scatter_data['dec'].extend(tile_data['DECLINATION'])
                mer_scatter_data['phz_mode_1'].extend(tile_data['PHZ_MODE_1'])
                mer_scatter_data['phz_70_int'].extend(tile_data['PHZ_70_INT'])
                mer_scatter_data['phz_pdf'].extend(tile_data['PHZ_PDF'])
                print(f"Debug: Added {len(tile_data['RIGHT_ASCENSION'])} points from MER tile {mertileid}")
        
        print(f"Debug: Total MER scatter points loaded: {len(mer_scatter_data['ra'])}")
        return mer_scatter_data

    def _create_traces_fallback(self, data, show_polygons=True, show_mer_tiles=False, relayout_data=None, show_catred_mertile_data=False, manual_mer_data=None, existing_mer_traces=None, snr_threshold_lower=None, snr_threshold_upper=None):
        """Create all Plotly traces - fallback implementation
        
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
            print(f"Debug: Using manually loaded MER scatter data")
            
            # Add the scatter trace if we have data
            if manual_mer_data and 'ra' in manual_mer_data and manual_mer_data['ra']:
                print(f"Debug: Creating MER scatter trace with {len(manual_mer_data['ra'])} points")
                
                # Create unique name for this MER trace based on current number of existing traces
                trace_number = len(self.mer_traces_cache) + 1
                trace_name = f'MER High-Res Data #{trace_number}'
                
                # def format_hover_text(x, y, p1, p70):
                #     """Safely format hover text for MER data points, handling potential vector values"""
                #     try:
                #         # Ensure PHZ_MODE_1 is scalar
                #         p1_val = float(p1) if np.isscalar(p1) else float(p1[0]) if hasattr(p1, '__len__') and len(p1) > 0 else 0.0
                        
                #         # For PHZ_70_INT, calculate the difference between the two values (confidence interval width)
                #         if hasattr(p70, '__len__') and len(p70) >= 2:
                #             p70_diff = abs(float(p70[1]) - float(p70[0]))
                #         elif np.isscalar(p70):
                #             p70_diff = 0.0  # No interval if scalar
                #         else:
                #             p70_diff = 0.0
                        
                #         return f'MER Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ_MODE_1: {p1_val:.3f}<br>PHZ_70_INT: {p70_diff:.3f}'
                #     except Exception as e:
                #         return f'MER Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ Data: Error formatting'
                
                mer_catred_trace = go.Scattergl(
                    x=manual_mer_data['ra'],
                    y=manual_mer_data['dec'],
                    mode='markers',
                    marker=dict(size=4, symbol='circle', color='black', opacity=0.5),
                    name=trace_name,
                    text=[f'MER Data Point<br>RA: {x:.6f}<br>Dec: {y:.6f}<br>PHZ_MODE_1: {p1:.3f}<br>PHZ_70_INT: {abs(float(p70[1]) - float(p70[0])):.3f}'
                          for x, y, p1, p70 in zip(manual_mer_data['ra'], manual_mer_data['dec'], 
                                                   manual_mer_data['phz_mode_1'], manual_mer_data['phz_70_int'])],
                    hoverinfo='text',
                    showlegend=True,
                    customdata=list(range(len(manual_mer_data['ra'])))  # Add index for click tracking
                )
                data_traces.append(mer_catred_trace)
                
                # Store MER data for click callbacks
                if not hasattr(self, 'current_mer_data') or self.current_mer_data is None:
                    self.current_mer_data = {}
                self.current_mer_data[trace_name] = manual_mer_data
                
                print(f"Debug: Stored MER data for trace '{trace_name}' with {len(manual_mer_data['ra'])} points")
                print(f"Debug: PHZ_PDF sample length: {len(manual_mer_data['phz_pdf'][0]) if manual_mer_data['phz_pdf'] else 'No PHZ_PDF data'}")
                print(f"Debug: Current MER data keys: {list(self.current_mer_data.keys())}")
                
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
        """Setup the Dash app layout with side-by-side plots and compact controls"""
        self.app.layout = dbc.Container([
            # Header row
            dbc.Row([
                dbc.Col([
                    html.H1("Cluster Detection Visualization", className="text-center mb-3"),
                ])
            ], className="mb-3"),
            
            # Main horizontal layout: Controls sidebar + Plot area
            dbc.Row([
                # Left sidebar with controls
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.H5("Visualization Controls", className="mb-0 text-center")
                        ]),
                        dbc.CardBody([
                            html.P("Options update in real-time while preserving zoom", 
                                   className="text-muted small mb-3 text-center"),
                            
                            # Algorithm selection
                            html.Div([
                                html.Label("Algorithm:", className="fw-bold mb-2"),
                                dcc.Dropdown(
                                    id='algorithm-dropdown',
                                    options=[
                                        {'label': 'PZWAV', 'value': 'PZWAV'},
                                        {'label': 'AMICO', 'value': 'AMICO'}
                                    ],
                                    value='PZWAV',
                                    clearable=False
                                )
                            ], className="mb-4"),
                            
                            # SNR Filtering section
                            html.Div([
                                html.Label("SNR Filtering:", className="fw-bold mb-2"),
                                html.Div(id="snr-range-display", className="text-center mb-2"),
                                dcc.RangeSlider(
                                    id='snr-range-slider',
                                    min=0,  # Will be updated dynamically
                                    max=100,  # Will be updated dynamically
                                    step=0.1,
                                    marks={},  # Will be updated dynamically
                                    value=[0, 100],  # Will be updated dynamically
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    allowCross=False
                                ),
                                dbc.Button(
                                    "Apply SNR Filter",
                                    id="snr-render-button",
                                    color="secondary",
                                    size="sm",
                                    className="w-100 mt-2",
                                    n_clicks=0,
                                    disabled=True
                                )
                            ], className="mb-4"),
                            
                            # Display options
                            html.Div([
                                html.Label("Display Options:", className="fw-bold mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="polygon-switch",
                                        label="Fill polygons",
                                        value=False,
                                    )
                                ], className="mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="mer-switch",
                                        label="Show MER tiles",
                                        value=False,
                                    ),
                                    html.Small("(Only with outline polygons)", className="text-muted")
                                ], className="mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="aspect-ratio-switch",
                                        label="Free aspect ratio",
                                        value=True,
                                    ),
                                    html.Small("(Default: maintain astronomical aspect)", className="text-muted")
                                ], className="mb-2"),
                                
                                html.Div([
                                    dbc.Switch(
                                        id="catred-mertile-switch",
                                        label="High-res MER data",
                                        value=False,
                                    ),
                                    html.Small("(When zoomed < 2°)", className="text-muted")
                                ], className="mb-3"),
                            ], className="mb-4"),
                            
                            # MER Data controls
                            html.Div([
                                html.Label("MER Data Controls:", className="fw-bold mb-2"),
                                
                                html.Div([
                                    dbc.Button(
                                        "🔍 Render MER Data",
                                        id="mer-render-button",
                                        color="info",
                                        size="sm",
                                        className="w-100 mb-2",
                                        n_clicks=0,
                                        disabled=True
                                    ),
                                    html.Small("(Zoom in first, then click)", className="text-muted d-block text-center mb-3")
                                ]),
                                
                                html.Div([
                                    dbc.Button(
                                        "🗑️ Clear All MER",
                                        id="mer-clear-button",
                                        color="warning",
                                        size="sm",
                                        className="w-100 mb-2",
                                        n_clicks=0
                                    ),
                                    html.Small("(Remove all MER traces)", className="text-muted d-block text-center")
                                ])
                            ], className="mb-4"),
                            
                            html.Hr(),
                            
                            # Main render button
                            html.Div([
                                dbc.Button(
                                    "🚀 Initial Render",
                                    id="render-button",
                                    color="primary",
                                    size="lg",
                                    className="w-100 mb-2",
                                    n_clicks=0
                                ),
                                html.Small("After initial render, options update automatically", 
                                          className="text-muted d-block text-center")
                            ])
                        ])
                    ], className="h-100")
                ], width=2, className="pe-2"),
                
                # Right side: Plot area and status
                dbc.Col([
                    # Main plots area - side by side
                    dbc.Row([
                        # Main cluster plot
                        dbc.Col([
                            dcc.Loading(
                                id="loading",
                                children=[
                                    dcc.Graph(
                                        id='cluster-plot',
                                        style={'height': '75vh', 'width': '100%', 'min-height': '500px'},
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
                        ], width=8),
                        
                        # PHZ_PDF plot
                        dbc.Col([
                            dcc.Loading(
                                id="loading-phz",
                                children=[
                                    dcc.Graph(
                                        id='phz-pdf-plot',
                                        style={'height': '75vh', 'width': '100%', 'min-height': '500px'},
                                        config={
                                            'displayModeBar': True,
                                            'displaylogo': False,
                                            'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'pan2d', 'zoom2d', 'autoScale2d', 'resetScale2d'],
                                            'responsive': True
                                        }
                                    )
                                ],
                                type="circle"
                            )
                        ], width=4)
                    ]),
                    
                    # Status info row
                    dbc.Row([
                        dbc.Col([
                            html.Div(id="status-info", className="mt-2")
                        ])
                    ])
                ], width=10)
            ], className="g-0")  # Remove gutters for tighter layout
            
        ], fluid=True, className="px-3")

    def setup_callbacks(self):
        """Setup Dash callbacks using modular or fallback approach"""
        # Force fallback callbacks temporarily to use the working PHZ implementation
        print("⚠️  Using fallback inline callbacks (forced for PHZ fix)")
        self._setup_fallback_callbacks()
        
        # Original modular approach - commented out temporarily
        # if MainPlotCallbacks and MERCallbacks and UICallbacks and PHZCallbacks:
        #     # Use modular callback setup
        #     print("✓ Setting up modular callbacks")
        #     
        #     # Initialize callback handlers
        #     self.main_plot_callbacks = MainPlotCallbacks(
        #         self.app, self.data_loader, self.mer_handler, 
        #         self.trace_creator, self.figure_manager
        #     )
        #     
        #     self.mer_callbacks = MERCallbacks(
        #         self.app, self.data_loader, self.mer_handler, 
        #         self.trace_creator, self.figure_manager
        #     )
        #     
        #     self.ui_callbacks = UICallbacks(self.app)
        #     
        #     self.phz_callbacks = PHZCallbacks(self.app, self.mer_handler, self, self.trace_creator)
        #     
        #     print("✓ All modular callbacks initialized")
        #     
        # else:
        #     # Fallback to inline callback setup
        #     print("⚠️  Using fallback inline callbacks")
        #     self._setup_fallback_callbacks()
    
    def _setup_fallback_callbacks(self):
        """Fallback callback setup - contains the original inline callbacks"""
        print("⚠️  Setting up fallback callbacks (original implementation)")
        # This contains all the original callback code for backward compatibility
        
        # Callback to initialize SNR slider when algorithm changes
        @self.app.callback(
            [Output('snr-range-slider', 'min'),
             Output('snr-range-slider', 'max'),
             Output('snr-range-slider', 'value'),
             Output('snr-range-slider', 'marks'),
             Output('snr-range-display', 'children')],
            [Input('algorithm-dropdown', 'value')],
            prevent_initial_call=False
        )
        def update_snr_slider(algorithm):
            try:
                # Load data to get SNR range
                data = self.load_data(algorithm)
                snr_min = data['snr_min']
                snr_max = data['snr_max']
                
                # Create marks at key points
                marks = {
                    snr_min: f'{snr_min:.1f}',
                    snr_max: f'{snr_max:.1f}',
                    (snr_min + snr_max) / 2: f'{(snr_min + snr_max) / 2:.1f}'
                }
                
                # Default to full range
                default_value = [snr_min, snr_max]
                
                display_text = html.Div([
                    html.Small(f"SNR Range: {snr_min:.2f} to {snr_max:.2f}", className="text-muted"),
                    html.Small(" | Move sliders to set filter range", className="text-muted")
                ])
                
                return snr_min, snr_max, default_value, marks, display_text
                
            except Exception as e:
                # Fallback values if data loading fails
                return 0, 100, [0, 100], {0: '0', 100: '100'}, html.Small("SNR data not available", className="text-muted")
        
        @self.app.callback(
            [Output('cluster-plot', 'figure'), Output('phz-pdf-plot', 'figure'), Output('status-info', 'children')],
            [Input('render-button', 'n_clicks'), Input('snr-render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData')]
        )
        def update_plot(n_clicks, snr_n_clicks, algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data):
            # Only render if button has been clicked at least once
            if n_clicks == 0 and snr_n_clicks == 0:
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
                    
                    margin=dict(l=40, r=20, t=40, b=40),
                    xaxis=xaxis_config,
                    yaxis=yaxis_config,
                    autosize=True,
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Select your preferred algorithm and display options from the sidebar,<br>then click the 'Initial Render' button to generate the plot.",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=16, color="gray")
                        )
                    ]
                )
                
                # Initial empty PHZ_PDF plot
                initial_phz_fig = go.Figure()
                initial_phz_fig.update_layout(
                    title='',
                    xaxis_title='',
                    yaxis_title='',
                    margin=dict(l=40, r=20, t=20, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Click on a MER data point above to view its PHZ_PDF",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="gray")
                        )
                    ]
                )
                
                initial_status = dbc.Alert([
                    html.H6("Ready to render", className="mb-1"),
                    html.P("Click 'Initial Render' to begin. After that, options will update automatically while preserving your zoom level.", className="mb-0")
                ], color="secondary", className="mt-2")
                
                return initial_fig, initial_phz_fig, initial_status
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Reset MER traces cache for fresh render
                if self.mer_handler:
                    self.mer_handler.clear_traces_cache()
                else:
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
                        x=1.01,
                        yanchor='top',
                        y=1,
                        font=dict(size=10)
                    ),
                    hovermode='closest',
                    
                    margin=dict(l=40, r=120, t=60, b=40),
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
                
                # Create empty PHZ_PDF plot for normal render
                empty_phz_fig = go.Figure()
                empty_phz_fig.update_layout(
                    title='PHZ_PDF Plot',
                    xaxis_title='Redshift',
                    yaxis_title='Probability Density',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Click on a MER data point to view its PHZ_PDF",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="gray")
                        )
                    ]
                )
                
                return fig, empty_phz_fig, status
                
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
                    
                    margin=dict(l=40, r=120, t=60, b=40),
                    autosize=True
                )
                
                error_status = dbc.Alert(
                    f"Error: {str(e)}",
                    color="danger"
                )
                
                # Error PHZ_PDF plot
                error_phz_fig = go.Figure()
                error_phz_fig.update_layout(
                    title='PHZ_PDF Plot',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Error loading data",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="red")
                        )
                    ]
                )
                
                return error_fig, error_phz_fig, error_status

        # Callback to update button text based on current settings
        @self.app.callback(
            [Output('render-button', 'children'), Output('mer-render-button', 'children'), Output('snr-render-button', 'children')],
            [Input('algorithm-dropdown', 'value'),
             Input('snr-range-slider', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value'),
             Input('render-button', 'n_clicks'),
             Input('mer-render-button', 'n_clicks'),
             Input('snr-render-button', 'n_clicks')]
        )
        def update_button_texts(algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, mer_n_clicks, snr_n_clicks):
            main_button_text = "🚀 Initial Render" if n_clicks == 0 else "✅ Live Updates Active"
            mer_button_text = f"🔍 Render MER Data ({mer_n_clicks})" if mer_n_clicks > 0 else "🔍 Render MER Data"
            snr_button_text = f"Apply SNR Filter ({snr_n_clicks})" if snr_n_clicks > 0 else "Apply SNR Filter"
            return main_button_text, mer_button_text, snr_button_text

        # Callback to enable SNR render button after initial render
        @self.app.callback(
            Output('snr-render-button', 'disabled'),
            [Input('render-button', 'n_clicks')],
            prevent_initial_call=False
        )
        def enable_snr_button(n_clicks):
            # Disable SNR button until initial render is clicked
            return n_clicks == 0

        # Callback to update clear button text
        @self.app.callback(
            Output('mer-clear-button', 'children'),
            [Input('mer-clear-button', 'n_clicks')]
        )
        def update_clear_button_text(clear_n_clicks):
            return f"🗑️ Clear All MER ({clear_n_clicks})" if clear_n_clicks > 0 else "🗑️ Clear All MER"

        # Callback for real-time option updates (preserves zoom) - excludes SNR which has its own button
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('phz-pdf-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('algorithm-dropdown', 'value'),
             Input('polygon-switch', 'value'),
             Input('mer-switch', 'value'),
             Input('aspect-ratio-switch', 'value'),
             Input('catred-mertile-switch', 'value')],
            [State('render-button', 'n_clicks'),
             State('snr-range-slider', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def update_plot_options(algorithm, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, n_clicks, snr_range, relayout_data, current_figure):
            # Only update if render button has been clicked at least once
            if n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
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
                        x=1.01,
                        yanchor='top',
                        y=1,
                        font=dict(size=10)
                    ),
                    hovermode='closest',
                    
                    margin=dict(l=40, r=120, t=60, b=40),
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
                
                # Create empty PHZ_PDF plot for options update
                empty_phz_fig = go.Figure()
                empty_phz_fig.update_layout(
                    title='PHZ_PDF Plot',
                    xaxis_title='Redshift',
                    yaxis_title='Probability Density',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Click on a MER data point to view its PHZ_PDF",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="gray")
                        )
                    ]
                )
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error updating: {str(e)}",
                    color="warning"
                )
                return dash.no_update, dash.no_update, error_status

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
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('phz-pdf-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
            [Input('mer-render-button', 'n_clicks')],
            [State('algorithm-dropdown', 'value'),
             State('snr-range-slider', 'value'),
             State('polygon-switch', 'value'),
             State('mer-switch', 'value'),
             State('aspect-ratio-switch', 'value'),
             State('catred-mertile-switch', 'value'),
             State('cluster-plot', 'relayoutData'),
             State('cluster-plot', 'figure')],
            prevent_initial_call=True
        )
        def manual_render_mer_data(mer_n_clicks, algorithm, snr_range, show_polygons, show_mer_tiles, free_aspect_ratio, show_catred_mertile_data, relayout_data, current_figure):
            if mer_n_clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"Debug: Manual MER render button clicked (click #{mer_n_clicks})")
            
            try:
                # Extract SNR values from range slider
                snr_lower = snr_range[0] if snr_range and len(snr_range) == 2 else None
                snr_upper = snr_range[1] if snr_range and len(snr_range) == 2 else None
                
                # Load data for selected algorithm
                data = self.load_data(algorithm)
                
                # Load MER scatter data for current zoom window
                mer_scatter_data = self.load_mer_scatter_data(data, relayout_data)
                
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
                                          manual_mer_data=mer_scatter_data, existing_mer_traces=existing_mer_traces,
                                          snr_threshold_lower=snr_lower, snr_threshold_upper=snr_upper)
                
                # Update the MER traces cache with the new trace count
                if mer_scatter_data and mer_scatter_data['ra']:
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
                        x=1.01,
                        yanchor='top',
                        y=1,
                        font=dict(size=10)
                    ),
                    hovermode='closest',
                    
                    
                    margin=dict(l=40, r=120, t=60, b=40),
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
                total_mer_traces = len(existing_mer_traces) + (1 if mer_scatter_data and mer_scatter_data['ra'] else 0)
                mer_points_count = len(mer_scatter_data['ra']) if mer_scatter_data and mer_scatter_data['ra'] else 0
                mer_status = f" | MER high-res data: {mer_points_count} points in {total_mer_traces} regions"
                aspect_mode = "Free aspect ratio" if free_aspect_ratio else "Equal aspect ratio"
                
                status = dbc.Alert([
                    html.H6(f"Algorithm: {algorithm}", className="mb-1"),
                    html.P(f"Merged clusters: {len(data['merged_data'])}", className="mb-1"),
                    html.P(f"Individual tiles: {len(data['tile_data'])}", className="mb-1"),
                    html.P(f"Polygon mode: {'Filled' if show_polygons else 'Outline'}{mer_status}", className="mb-1"),
                    html.P(f"Aspect ratio: {aspect_mode}", className="mb-1"),
                    html.Small(f"MER data rendered at: {pd.Timestamp.now().strftime('%H:%M:%S')}", className="text-muted")
                ], color="success", className="mt-2")
                
                # Create empty PHZ_PDF plot for MER render
                empty_phz_fig = go.Figure()
                empty_phz_fig.update_layout(
                    title='PHZ_PDF Plot',
                    xaxis_title='Redshift',
                    yaxis_title='Probability Density',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="Click on a MER data point to view its PHZ_PDF",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="gray")
                        )
                    ]
                )
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error rendering MER data: {str(e)}",
                    color="danger"
                )
                return dash.no_update, dash.no_update, error_status

        # Callback for clearing all MER data
        @self.app.callback(
            [Output('cluster-plot', 'figure', allow_duplicate=True), Output('phz-pdf-plot', 'figure', allow_duplicate=True), Output('status-info', 'children', allow_duplicate=True)],
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
                return dash.no_update, dash.no_update, dash.no_update
            
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
                        x=1.01,
                        yanchor='top',
                        y=1,
                        font=dict(size=10)
                    ),
                    hovermode='closest',
                    
                    
                    margin=dict(l=40, r=120, t=60, b=40),
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
                
                # Create empty PHZ_PDF plot for clear action
                empty_phz_fig = go.Figure()
                empty_phz_fig.update_layout(
                    title='PHZ_PDF Plot',
                    xaxis_title='Redshift',
                    yaxis_title='Probability Density',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text="MER data cleared - Click on a MER data point to view its PHZ_PDF",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=14, color="gray")
                        )
                    ]
                )
                
                return fig, empty_phz_fig, status
                
            except Exception as e:
                error_status = dbc.Alert(
                    f"Error clearing MER data: {str(e)}",
                    color="danger"
                )
                return dash.no_update, dash.no_update, error_status

        # Callback for handling clicks on MER data points to show PHZ_PDF
        @self.app.callback(
            Output('phz-pdf-plot', 'figure', allow_duplicate=True),
            [Input('cluster-plot', 'clickData')],
            prevent_initial_call=True
        )
        def update_phz_pdf_plot(clickData):
            print(f"Debug: Click callback triggered with clickData: {clickData}")
            
            if not clickData:
                print("Debug: No clickData received")
                return dash.no_update
            
            # Try to get current MER data from multiple sources
            current_mer_data = None
            
            # First try the main app's stored data
            if hasattr(self, 'current_mer_data') and self.current_mer_data:
                current_mer_data = self.current_mer_data
                print("Debug: Using current_mer_data from main app")
            
            # If not found, try the trace_creator's stored data
            elif hasattr(self, 'trace_creator') and self.trace_creator and hasattr(self.trace_creator, 'current_mer_data') and self.trace_creator.current_mer_data:
                current_mer_data = self.trace_creator.current_mer_data
                print("Debug: Using current_mer_data from trace_creator")
            
            # If not found, try the mer_handler's stored data
            elif hasattr(self, 'mer_handler') and self.mer_handler and hasattr(self.mer_handler, 'current_mer_data') and self.mer_handler.current_mer_data:
                current_mer_data = self.mer_handler.current_mer_data
                print("Debug: Using current_mer_data from mer_handler")
            
            if not current_mer_data:
                print(f"Debug: No current_mer_data available from any source")
                print(f"  - self.current_mer_data: {getattr(self, 'current_mer_data', None)}")
                print(f"  - trace_creator.current_mer_data: {getattr(self.trace_creator, 'current_mer_data', None) if hasattr(self, 'trace_creator') and self.trace_creator else 'No trace_creator'}")
                print(f"  - mer_handler.current_mer_data: {getattr(self.mer_handler, 'current_mer_data', None) if hasattr(self, 'mer_handler') and self.mer_handler else 'No mer_handler'}")
                return dash.no_update
            
            try:
                # Extract click information
                clicked_point = clickData['points'][0]
                print(f"Debug: Clicked point: {clicked_point}")
                
                # Get trace name from the clicked point - this is key for identifying MER traces
                curve_number = clicked_point.get('curveNumber', None)
                trace_name = None
                
                # Try to get trace name from the clickData if available
                if 'data' in clickData:
                    # This won't work as clickData doesn't contain trace names
                    pass
                
                # Check if this click is on a MER trace by looking at customdata
                custom_data = clicked_point.get('customdata', None)
                print(f"Debug: Custom data: {custom_data}")
                
                # Get coordinates for matching
                clicked_x = clicked_point.get('x')
                clicked_y = clicked_point.get('y')
                print(f"Debug: Clicked coordinates: ({clicked_x}, {clicked_y})")
                
                # Search through stored MER data to find the matching trace
                found_mer_data = None
                point_index = None
                
                print(f"Debug: Available MER data traces: {list(current_mer_data.keys())}")
                
                for trace_name, mer_data in current_mer_data.items():
                    print(f"Debug: Checking trace: {trace_name}")
                    if 'MER High-Res Data' in trace_name:
                        print(f"Debug: Found MER trace with {len(mer_data['ra'])} points")
                        
                        # If we have custom data (point index), use it directly
                        if custom_data is not None and isinstance(custom_data, int) and custom_data < len(mer_data['ra']):
                            found_mer_data = mer_data
                            point_index = custom_data
                            print(f"Debug: Using custom data index: {point_index}")
                            break
                        
                        # Otherwise, find the point index by matching coordinates (less reliable but fallback)
                        if clicked_x is not None and clicked_y is not None:
                            for i, (x, y) in enumerate(zip(mer_data['ra'], mer_data['dec'])):
                                if abs(x - clicked_x) < 1e-6 and abs(y - clicked_y) < 1e-6:
                                    found_mer_data = mer_data
                                    point_index = i
                                    print(f"Debug: Found matching point by coordinates at index: {point_index}")
                                    break
                        
                        if found_mer_data:
                            break
                
                if found_mer_data and point_index is not None:
                    print(f"Debug: Successfully found MER data for point index: {point_index}")
                    
                    # Get PHZ_PDF data for this point
                    phz_pdf = found_mer_data['phz_pdf'][point_index]
                    ra = found_mer_data['ra'][point_index]
                    dec = found_mer_data['dec'][point_index]
                    phz_mode_1 = found_mer_data['phz_mode_1'][point_index]
                    
                    print(f"Debug: PHZ_PDF length: {len(phz_pdf)}, PHZ_MODE_1: {phz_mode_1}")
                    
                    # Create redshift bins (assuming typical range for photometric redshift)
                    z_bins = np.linspace(0, 3, len(phz_pdf))
                    
                    # Create PHZ_PDF plot
                    phz_fig = go.Figure()
                    
                    phz_fig.add_trace(go.Scatter(
                        x=z_bins,
                        y=phz_pdf,
                        mode='lines+markers',
                        name='PHZ_PDF',
                        line=dict(color='blue', width=2),
                        marker=dict(size=4),
                        fill='tonexty'
                    ))
                    
                    # Add vertical line for PHZ_MODE_1
                    phz_fig.add_vline(
                        x=phz_mode_1,
                        line=dict(color='red', width=2, dash='dash'),
                        annotation_text=f"PHZ_MODE_1: {phz_mode_1:.3f}",
                        annotation_position="top"
                    )
                    
                    phz_fig.update_layout(
                        title=f'PHZ_PDF for MER Point at RA: {ra:.6f}, Dec: {dec:.6f}',
                        xaxis_title='Redshift (z)',
                        yaxis_title='Probability Density',
                        margin=dict(l=40, r=20, t=60, b=40),
                        showlegend=True,
                        hovermode='x unified'
                    )
                    
                    print(f"Debug: Created PHZ_PDF plot for point at RA: {ra:.6f}, Dec: {dec:.6f}")
                    return phz_fig
                else:
                    print("Debug: Click was not on a MER data point")
                
                # If we get here, the click wasn't on a MER point
                return dash.no_update
                
            except Exception as e:
                print(f"Debug: Error creating PHZ_PDF plot: {e}")
                import traceback
                print(f"Debug: Traceback: {traceback.format_exc()}")
                
                # Return error plot
                error_fig = go.Figure()
                error_fig.update_layout(
                    title='PHZ_PDF Plot - Error',
                    xaxis_title='Redshift',
                    yaxis_title='Probability Density',
                    margin=dict(l=40, r=20, t=40, b=40),
                    showlegend=False,
                    annotations=[
                        dict(
                            text=f"Error loading PHZ_PDF data: {str(e)}",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5, xanchor='center', yanchor='middle',
                            showarrow=False,
                            font=dict(size=12, color="red")
                        )
                    ]
                )
                return error_fig

    def open_browser(self, port=8050, delay=1.5):
        """Open browser after a short delay"""
        def open_browser_delayed():
            time.sleep(delay)
            webbrowser.open(f'http://localhost:{port}')
        
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()

    def run(self, host='localhost', port=8050, debug=False, auto_open=True, external_access=False):
        """Run the Dash app using modular or fallback core"""
        if self.core:
            # Use modular core
            return self.core.run(host, port, debug, auto_open, external_access)
        else:
            # Fallback to inline implementation
            return self._run_fallback(host, port, debug, auto_open, external_access)
    
    def _run_fallback(self, host='localhost', port=8050, debug=False, auto_open=True, external_access=False):
        """Fallback run implementation"""
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
    
    # Check for external access flag using modular core if available
    if ClusterVisualizationCore:
        external_access = ClusterVisualizationCore.check_command_line_args()
    else:
        external_access = '--external' in sys.argv or '--remote' in sys.argv
    
    app = ClusterVisualizationApp()
    
    # Try different ports if default is busy using modular core if available
    if app.core:
        app.core.try_multiple_ports(ports=[8050, 8051, 8052], debug=False, auto_open=False, external_access=external_access)
    else:
        # Fallback implementation
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
