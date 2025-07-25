#!/usr/bin/env python3
"""
Standalone Cluster Visualization
Generates an interactive HTML file with cluster detection data
"""

import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from astropy.io import fits
from shapely.geometry import Polygon as ShapelyPolygon

import plotly.graph_objs as go
import plotly.offline as pyo
import plotly.io as pio

# Add local utils path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils'))
from myutils import get_xml_element
from colordefinitions import colors_list, colors_list_transparent

def load_data(select_algorithm='PZWAV'):
    """Load and prepare all data for visualization"""
    print(f"Loading data for algorithm: {select_algorithm}")
    
    # Configuration
    snrthreshold = None
    snrthreshold_upper = None
    
    # Validate algorithm choice
    if select_algorithm not in ['PZWAV', 'AMICO']:
        print(f"Warning: Unknown algorithm '{select_algorithm}'. Using 'PZWAV' as default.")
        select_algorithm = 'PZWAV'
    
    # Paths
    mergedetcatdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/MergeDetCat/RR2_south/'
    mergedetcat_datadir = os.path.join(mergedetcatdir, 'data')
    mergedetcat_inputsdir = os.path.join(mergedetcatdir, 'inputs')
    mergedetcatoutputdir = os.path.join(mergedetcatdir, f'outvn_mergedetcat_rr2south_{select_algorithm}_3')
    
    rr2downloadsdir = '/sps/euclid/OU-LE3/CL/ial_workspace/workdir/RR2_downloads'
    
    # Load merged detection catalog
    det_xml = os.path.join(mergedetcatoutputdir, 'mergedetcat.xml')
    fitsfile = os.path.join(mergedetcat_datadir, 
                           get_xml_element(det_xml, 'Data/ClustersFile/DataContainer/FileName').text)
    
    print(f"Loading merged catalog from: {fitsfile}")
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
    indiv_detfiles_list = os.path.join(mergedetcatdir, f'detfiles_input_{select_algorithm.lower()}_3.json')
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
    
    # Load catred file info
    catred_fileinfo_csv = os.path.join(rr2downloadsdir, 'catred_fileinfo.csv')
    catred_fileinfo_df = pd.DataFrame()
    if os.path.exists(catred_fileinfo_csv):
        catred_fileinfo_df = pd.read_csv(catred_fileinfo_csv)
        catred_fileinfo_df.set_index('tileid', inplace=True)
        print("Loaded catred file info")
    else:
        print("Warning: catred_fileinfo.csv not found!")
    
    # Load catred polygons
    catred_polygon_pkl = os.path.join(rr2downloadsdir, 'catred_polygons_by_tileid.pkl')
    if os.path.exists(catred_polygon_pkl) and not catred_fileinfo_df.empty:
        with open(catred_polygon_pkl, 'rb') as f:
            catred_fileinfo_dict = pickle.load(f)
        catred_fileinfo_df['polygon'] = pd.Series(catred_fileinfo_dict)
        print("Loaded catred polygons")
    else:
        print("Warning: catred_polygons_by_tileid.pkl not found!")
    
    return {
        'merged_data': datamod_merged,
        'tile_data': data_by_tile,
        'catred_info': catred_fileinfo_df,
        'algorithm': select_algorithm,
        'snr_threshold': snrthreshold,
        'data_dir': mergedetcat_datadir
    }

def create_traces(data):
    """Create all Plotly traces"""
    print("Creating visualization traces...")
    
    # Merged data trace
    merged_trace = go.Scattergl(
        x=data['merged_data']['RIGHT_ASCENSION_CLUSTER'],
        y=data['merged_data']['DECLINATION_CLUSTER'],
        mode='markers',
        marker=dict(size=10, symbol='square-open', line=dict(width=2), color='black'),
        name=f'Merged Data (SNR > {data["snr_threshold"]})',
        text=[
            f"merged<br>SNR_CLUSTER: {snr}<br>Z_CLUSTER: {cz}<br>RA: {ra:.6f}<br>Dec: {dec:.6f}"
            for snr, cz, ra, dec in zip(data['merged_data']['SNR_CLUSTER'], 
                                      data['merged_data']['Z_CLUSTER'], 
                                      data['merged_data']['RIGHT_ASCENSION_CLUSTER'], 
                                      data['merged_data']['DECLINATION_CLUSTER'])
        ],
        hoverinfo='text'
    )
    
    # Individual tiles traces and polygons
    tile_traces = []
    level1_polygon_traces = []
    core_polygon_traces = []
    core_polygon_traces_filled = []
    mertile_traces = []
    
    for tileid, value in data['tile_data'].items():
        tile_data = value['data']
        
        # Apply SNR filtering (same as merged data logic)
        if data['snr_threshold'] is None:
            datamod = tile_data
        else:
            datamod = tile_data[tile_data['SNR_CLUSTER'] > data['snr_threshold']]
        
        # Tile data trace
        tile_traces.append(
            go.Scattergl(
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
        )
        
        # Load tile definition
        with open(os.path.join(data['data_dir'], value['tilefile']), 'r') as f:
            tile = json.load(f)
        
        # LEV1 polygon
        poly = tile['LEV1']['POLYGON'][0]
        poly_x = [p[0] for p in poly] + [poly[0][0]]
        poly_y = [p[1] for p in poly] + [poly[0][1]]
        level1_polygon_traces.append(
            go.Scatter(
                x=poly_x,
                y=poly_y,
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)], dash='dash'),
                name=f'Tile {tileid} LEV1',
                showlegend=False,
                text=f'Tile {tileid} - LEV1 Polygon',
                hoverinfo='text'
            )
        )
        
        # CORE polygon
        poly2 = tile['CORE']['POLYGON'][0]
        poly_x2 = [p[0] for p in poly2] + [poly2[0][0]]
        poly_y2 = [p[1] for p in poly2] + [poly2[0][1]]
        core_polygon_traces.append(
            go.Scatter(
                x=poly_x2,
                y=poly_y2,
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)]),
                name=f'Tile {tileid} CORE',
                showlegend=False,
                text=f'Tile {tileid} - CORE Polygon',
                hoverinfo='text'
            )
        )

        core_polygon_traces_filled.append(
            go.Scatter(
                x=poly_x2,
                y=poly_y2,
                fill='toself',
                fillcolor=colors_list_transparent[int(tileid)],
                mode='lines',
                line=dict(width=2, color=colors_list[int(tileid)]),
                name=f'Tile {tileid} CORE',
                showlegend=False,
                text=f'Tile {tileid} - CORE Polygon',
                hoverinfo='text'
            )
        )
        
        # MER tile polygons
        if not data['catred_info'].empty and 'polygon' in data['catred_info'].columns:
            for mertileid in tile['LEV1']['ID_INTERSECTED']:
                if mertileid in data['catred_info'].index:
                    merpoly = data['catred_info'].at[mertileid, 'polygon']
                    if merpoly is not None:
                        x, y = merpoly.exterior.xy
                        mertile_traces.append(
                            go.Scatter(
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
                        )
    
    return {
        'merged': merged_trace,
        'tiles': tile_traces,
        'level1 polygons': level1_polygon_traces,
        'core polygons': core_polygon_traces,
        'core polygons filled': core_polygon_traces_filled,
        'mertiles': mertile_traces
    }

def create_interactive_html(traces_pzwav, traces_amico, data_pzwav, data_amico):
    """Create interactive HTML file with algorithm selection and zoom-based MER tile display"""
    
    # Create traces for both algorithms
    # PZWAV traces
    traces_pzwav_basic = traces_pzwav['level1 polygons'] + traces_pzwav['core polygons'] + [traces_pzwav['merged']] + traces_pzwav['tiles']
    traces_pzwav_basic_polyfilled = traces_pzwav['level1 polygons'] + traces_pzwav['core polygons filled'] + [traces_pzwav['merged']] + traces_pzwav['tiles']
    traces_pzwav_with_mer = traces_pzwav['level1 polygons'] + traces_pzwav['core polygons'] + traces_pzwav['mertiles'] + [traces_pzwav['merged']] + traces_pzwav['tiles']

    # AMICO traces
    traces_amico_basic = traces_amico['level1 polygons'] + traces_amico['core polygons'] + [traces_amico['merged']] + traces_amico['tiles']
    traces_amico_basic_polyfilled = traces_amico['level1 polygons'] + traces_amico['core polygons filled'] + [traces_amico['merged']] + traces_amico['tiles']
    traces_amico_with_mer = traces_amico['level1 polygons'] + traces_amico['core polygons'] + traces_amico['mertiles'] + [traces_amico['merged']] + traces_amico['tiles']

    # Create figures for PZWAV
    fig_pzwav_basic = go.Figure(traces_pzwav_basic)
    fig_pzwav_basic.update_layout(
        title='Cluster Detection Visualization - PZWAV (Basic View)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )

    fig_pzwav_basic_polyfilled = go.Figure(traces_pzwav_basic_polyfilled)
    fig_pzwav_basic_polyfilled.update_layout(
        title='Cluster Detection Visualization - PZWAV (Basic View)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )

    fig_pzwav_with_mer = go.Figure(traces_pzwav_with_mer)
    fig_pzwav_with_mer.update_layout(
        title='Cluster Detection Visualization - PZWAV (With MER Tiles)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )
    
    # Create figures for AMICO
    fig_amico_basic = go.Figure(traces_amico_basic)
    fig_amico_basic.update_layout(
        title='Cluster Detection Visualization - AMICO (Basic View)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )
    
    fig_amico_basic_polyfilled = go.Figure(traces_amico_basic_polyfilled)
    fig_amico_basic_polyfilled.update_layout(
        title='Cluster Detection Visualization - AMICO (Basic View)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )

    fig_amico_with_mer = go.Figure(traces_amico_with_mer)
    fig_amico_with_mer.update_layout(
        title='Cluster Detection Visualization - AMICO (With MER Tiles)',
        xaxis_title='Right Ascension (degrees)',
        yaxis_title='Declination (degrees)',
        legend=dict(title='Legend', orientation='v', xanchor='left', x=1.02),
        hovermode='closest',
        width=1200,
        height=900,
        margin=dict(r=150, l=50, t=80, b=50)
    )
    
    # Create HTML content
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Cluster Detection Visualization</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; max-width: 100%; overflow-x: auto; }}
        .plot-container {{ margin-bottom: 30px; width: 100%; }}
        .controls {{ margin-bottom: 20px; padding: 15px; background-color: #f0f0f0; border-radius: 5px; display: flex; flex-wrap: wrap; gap: 10px; }}
        .algorithm-controls {{ margin-bottom: 15px; padding: 15px; background-color: #e8f4fd; border-radius: 5px; display: flex; flex-wrap: wrap; gap: 10px; }}
        button {{ padding: 8px 15px; background-color: #007cba; color: white; border: none; border-radius: 3px; cursor: pointer; white-space: nowrap; }}
        button:hover {{ background-color: #005a8b; }}
        button.active {{ background-color: #005a8b; font-weight: bold; }}
        .info {{ margin-bottom: 20px; padding: 10px; background-color: #e8f4fd; border-radius: 5px; }}
        .instructions {{ margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 5px; }}
        #plot1 {{ border: 1px solid #ddd; border-radius: 5px; }}
        .status {{ margin-bottom: 10px; padding: 8px; background-color: #fff3cd; border-radius: 3px; font-size: 14px; }}
    </style>
</head>
<body>
    <h1>Cluster Detection Visualization</h1>
    <div class="info">
        <strong>Comparison View:</strong> Switch between PZWAV and AMICO algorithms<br>
        <strong>PZWAV Clusters:</strong> {len(data_pzwav["merged_data"])} merged clusters from {len(data_pzwav["tile_data"])} tiles<br>
        <strong>AMICO Clusters:</strong> {len(data_amico["merged_data"])} merged clusters from {len(data_amico["tile_data"])} tiles<br>
        <strong>MER Tiles:</strong> {len(traces_pzwav["mertiles"])} available
    </div>
    
    <div class="algorithm-controls">
        <strong>Algorithm Selection:</strong>
        <button id="btn-pzwav" onclick="selectAlgorithm('PZWAV')" class="active">PZWAV (Photometric Redshift WAV)</button>
        <button id="btn-amico" onclick="selectAlgorithm('AMICO')">AMICO (Adaptive Matched Identifier)</button>
    </div>
    
    <div class="controls">
        <button onclick="showBasic()">Show Basic View (Fast)</button>
        <button onclick="showWithMER()">Show with MER Tiles (Detailed)</button>
        <button onclick="resetZoom()">Reset Zoom</button>
        <button onclick="toggleAspectRatio()">Toggle Aspect Ratio</button>
        <button onclick="togglePolygonFill()">Toggle Polygon Fill</button>
        <button onclick="adjustSize('larger')">Larger Plot</button>
        <button onclick="adjustSize('smaller')">Smaller Plot</button>
    </div>
    
    <div class="status">
        <strong>Current Algorithm:</strong> <span id="current-algorithm">PZWAV</span> | 
        <strong>Plot Status:</strong> <span id="status-text">Free aspect ratio (stretches to fit)</span> | 
        <strong>Polygon Fill:</strong> <span id="polygon-fill-status">Off</span> | 
        <strong>Size:</strong> <span id="size-text">900px height</span>
    </div>
    
    <div class="plot-container">
        <div id="plot1" style="width:100%;height:900px;"></div>
    </div>
    
    <div class="instructions">
        <h3>Instructions:</h3>
        <ul>
            <li><strong>Algorithm Selection:</strong> Choose between PZWAV and AMICO detection algorithms</li>
            <li><strong>Basic View:</strong> Shows cluster data and tile boundaries (faster rendering)</li>
            <li><strong>Detailed View:</strong> Shows everything including MER tile polygons (slower but complete)</li>
            <li><strong>Zoom/Pan:</strong> Use mouse wheel to zoom, click and drag to pan</li>
            <li><strong>Aspect Ratio:</strong> Toggle between equal aspect ratio (RA/Dec proportional) and free aspect ratio (stretches to fit)</li>
            <li><strong>Polygon Fill:</strong> Toggle fill on/off for CORE tile polygons (works in Basic View only)</li>
            <li><strong>Plot Size:</strong> Use Larger/Smaller buttons to adjust plot height (400px - 1200px)</li>
            <li><strong>Hover:</strong> Hover over points and polygons to see detailed information</li>
            <li><strong>Legend:</strong> Click items in the legend to hide/show data series</li>
            <li><strong>Colors:</strong> Each tile has a unique color for easy identification</li>
        </ul>
        <p><strong>Performance Tip:</strong> Start with Basic View for overview, then use Detailed View for specific regions.</p>
        <p><strong>Algorithm Comparison:</strong> PZWAV typically finds fewer but more reliable clusters, while AMICO may detect more candidates including lower-significance ones.</p>
    </div>

    <script>
        var plotDiv = document.getElementById('plot1');
        
        // Store all figure data
        var figures = {{
            'PZWAV': {{
                'basic': {fig_pzwav_basic.to_json()},
                'basicFilled': {fig_pzwav_basic_polyfilled.to_json()},
                'withMER': {fig_pzwav_with_mer.to_json()}
            }},
            'AMICO': {{
                'basic': {fig_amico_basic.to_json()},
                'basicFilled': {fig_amico_basic_polyfilled.to_json()},
                'withMER': {fig_amico_with_mer.to_json()}
            }}
        }};
        
        var currentAlgorithm = 'PZWAV';
        var currentView = 'basic';
        var aspectRatioFixed = false;
        var polygonFillEnabled = false;
        var currentHeight = 900;
        
        function showBasic() {{
            currentView = 'basic';
            var viewKey = polygonFillEnabled ? 'basicFilled' : 'basic';
            var fig = figures[currentAlgorithm][viewKey];
            Plotly.newPlot(plotDiv, fig.data, fig.layout, {{responsive: true}});
        }}
        
        function showWithMER() {{
            currentView = 'withMER';
            var fig = figures[currentAlgorithm]['withMER'];
            Plotly.newPlot(plotDiv, fig.data, fig.layout, {{responsive: true}});
        }}
        
        function selectAlgorithm(algorithm) {{
            currentAlgorithm = algorithm;
            document.getElementById('current-algorithm').textContent = algorithm;
            
            // Update button states
            document.getElementById('btn-pzwav').classList.toggle('active', algorithm === 'PZWAV');
            document.getElementById('btn-amico').classList.toggle('active', algorithm === 'AMICO');
            
            // Refresh current view with new algorithm
            if (currentView === 'basic') {{
                showBasic();
            }} else {{
                showWithMER();
            }}
        }}
        
        function resetZoom() {{
            Plotly.relayout(plotDiv, {{
                'xaxis.autorange': true,
                'yaxis.autorange': true
            }});
        }}
        
        function togglePolygonFill() {{
            polygonFillEnabled = !polygonFillEnabled;
            document.getElementById('polygon-fill-status').textContent = polygonFillEnabled ? 'On' : 'Off';
            
            // Only refresh if we're in basic view (MER view doesn't have filled polygons implemented yet)
            if (currentView === 'basic') {{
                showBasic();
            }}
        }}
        
        function toggleAspectRatio() {{
            aspectRatioFixed = !aspectRatioFixed;
            var updateLayout = {{}};
            
            if (aspectRatioFixed) {{
                updateLayout = {{
                    'xaxis.scaleanchor': 'y',
                    'xaxis.scaleratio': 1,
                    'yaxis.constrain': 'domain'
                }};
                document.getElementById('status-text').textContent = 'Equal aspect ratio (RA/Dec proportional)';
            }} else {{
                updateLayout = {{
                    'xaxis.scaleanchor': null,
                    'xaxis.scaleratio': null,
                    'yaxis.constrain': null
                }};
                document.getElementById('status-text').textContent = 'Free aspect ratio (stretches to fit)';
            }}
            
            Plotly.relayout(plotDiv, updateLayout);
        }}
        
        function adjustSize(direction) {{
            if (direction === 'larger') {{
                currentHeight = Math.min(currentHeight + 100, 1200);
            }} else {{
                currentHeight = Math.max(currentHeight - 100, 400);
            }}
            
            plotDiv.style.height = currentHeight + 'px';
            document.getElementById('size-text').textContent = currentHeight + 'px height';
            
            Plotly.relayout(plotDiv, {{
                'height': currentHeight
            }});
        }}
        
        // Start with PZWAV basic view
        showBasic();
    </script>
</body>
</html>
"""
    
    return html_content

def main():
    """Main function to generate the visualization"""
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Generate interactive cluster visualization HTML')
    parser.add_argument('--algorithm', '-a', choices=['PZWAV', 'AMICO', 'BOTH'], default='BOTH',
                       help='Algorithm to use for detection (default: BOTH for comparison)')
    parser.add_argument('--output', '-o', default='cluster_visualization_comparison.html',
                       help='Output HTML filename (default: cluster_visualization_comparison.html)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive mode: prompt for algorithm selection')
    
    args = parser.parse_args()
    
    # Determine output directory based on script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(os.path.dirname(script_dir), 'output', 'current')
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    args = parser.parse_args()
    
    # Interactive algorithm selection if requested
    if args.interactive:
        print("Available algorithms:")
        print("1. PZWAV")
        print("2. AMICO")
        print("3. BOTH (comparison)")
        while True:
            try:
                choice = input("Select algorithm (1, 2, or 3): ").strip()
                if choice == '1':
                    selected_algorithm = 'PZWAV'
                    break
                elif choice == '2':
                    selected_algorithm = 'AMICO'
                    break
                elif choice == '3':
                    selected_algorithm = 'BOTH'
                    break
                else:
                    print("Please enter 1, 2, or 3")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return
    else:
        selected_algorithm = args.algorithm
    
    try:
        if selected_algorithm == 'BOTH':
            print("Generating comparison visualization for both algorithms...")
            
            # Load data for both algorithms
            print("Loading PZWAV data...")
            data_pzwav = load_data('PZWAV')
            print("Loading AMICO data...")
            data_amico = load_data('AMICO')
            
            # Create traces for both algorithms
            print("Creating PZWAV traces...")
            traces_pzwav = create_traces(data_pzwav)
            print("Creating AMICO traces...")
            traces_amico = create_traces(data_amico)
            
            # Generate HTML
            print("Generating interactive comparison HTML...")
            html_content = create_interactive_html(traces_pzwav, traces_amico, data_pzwav, data_amico)
            
            # Save HTML file
            output_file = os.path.join(output_dir, args.output)
            with open(output_file, 'w') as f:
                f.write(html_content)
            
            print(f"✓ Interactive comparison visualization saved as: {output_file}")
            print("✓ Algorithms included: PZWAV and AMICO")
            print(f"✓ Open {output_file} in your web browser to view the visualization")
            print("✓ The visualization includes:")
            print(f"  - PZWAV: {len(data_pzwav['merged_data'])} merged clusters")
            print(f"  - AMICO: {len(data_amico['merged_data'])} merged clusters")
            print(f"  - {len(data_pzwav['tile_data'])} individual tiles")
            print(f"  - {len(traces_pzwav['mertiles'])} MER tile polygons")
            print("✓ Use the algorithm buttons to switch between PZWAV and AMICO views")
            
        else:
            # Single algorithm mode (backward compatibility)
            print(f"Generating visualization for algorithm: {selected_algorithm}")
            
            # Load data
            data = load_data(selected_algorithm)
            
            # Create traces
            traces = create_traces(data)
            
            # Generate HTML (single algorithm version - create a simple wrapper)
            print("Generating interactive HTML...")
            if selected_algorithm == 'PZWAV':
                data_amico = load_data('AMICO')  # Load AMICO for comparison
                traces_amico = create_traces(data_amico)
                html_content = create_interactive_html(traces, traces_amico, data, data_amico)
            else:
                data_pzwav = load_data('PZWAV')  # Load PZWAV for comparison
                traces_pzwav = create_traces(data_pzwav)
                html_content = create_interactive_html(traces_pzwav, traces, data_pzwav, data)
            
            # Save HTML file
            output_file = os.path.join(output_dir, args.output)
            with open(output_file, 'w') as f:
                f.write(html_content)
            
            print(f"✓ Interactive visualization saved as: {output_file}")
            print(f"✓ Primary algorithm: {selected_algorithm}")
            print(f"✓ Open {output_file} in your web browser to view the visualization")
            print("✓ The visualization includes:")
            print(f"  - {len(data['merged_data'])} merged clusters")
            print(f"  - {len(data['tile_data'])} individual tiles")
            print(f"  - {len(traces['mertiles'])} MER tile polygons")
            print("✓ Use the buttons in the interface to switch between views")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
