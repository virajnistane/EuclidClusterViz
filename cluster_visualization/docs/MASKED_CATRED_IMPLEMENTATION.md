# Masked CATRED Implementation Summary

## Overview
Successfully implemented masked CATRED functionality based on notebook cell 31, providing a 3-way toggle between no CATRED data, unmasked CATRED data, and masked CATRED data using effective coverage masks.

## Key Components Added

### 1. Mask Class (`src/data/catred_handler.py`)
- **Purpose**: Handles HEALPix effective coverage mask operations
- **Key Methods**:
  - `__init__(in_file)`: Initialize mask from FITS file
  - `read_msk()`: Read HEALPix mask from FITS file using WEIGHT field
  - `radec_to_hpcell(ra, dec)`: Convert RA/Dec coordinates to HEALPix cell indices
- **Dependencies**: `astropy.io.fits`, `healpy`, `numpy`

### 2. get_masked_catred Function (`src/data/catred_handler.py`)
- **Purpose**: Filter CATRED sources based on effective coverage threshold
- **Parameters**:
  - `mertileid`: MER tile identifier
  - `effcovmask_fileinfo_df`: DataFrame with effective coverage mask file info
  - `catred_fileinfo_df`: DataFrame with CATRED file info  
  - `threshold`: Effective coverage threshold (default 0.8)
- **Returns**: Filtered CATRED data table with only sources above threshold

### 3. Enhanced CATREDHandler Methods

#### New Methods:
- `get_radec_mertile_masked()`: Load masked CATRED data for specific MER tile
- `update_catred_data_masked()`: Update masked CATRED data for zoom window
- `_load_tile_data_masked()`: Load masked data for multiple MER tiles
- `load_catred_scatter_data()`: Main method to load CATRED data based on mode
- `_extract_zoom_data_from_relayout()`: Extract zoom parameters from relayout data

## UI Updates

### 3-Way Radio Button (`ui/layout.py`)
- **Component**: `catred-mode-radio` 
- **Options**:
  - `"none"`: No CATRED data
  - `"unmasked"`: Unmasked CATRED data (original functionality)
  - `"masked"`: Masked CATRED data (new functionality)
- **Default**: `"unmasked"`

## Callback Updates

### 1. Main Plot Callbacks (`callbacks/main_plot.py`)
- **Updated**: `catred-mertile-switch` → `catred-mode-radio`
- **Parameter**: `show_catred_mertile_data` → `catred_mode`
- **Both callbacks updated**: main render and options update

### 2. CATRED Callbacks (`callbacks/catred_callbacks.py`)
- **Updated**: Button state callback to use radio instead of switch
- **Updated**: Manual render callback to handle 3-way mode
- **Enhanced**: `load_catred_scatter_data()` method to accept `catred_mode` parameter

### 3. Trace Creator (`src/visualization/traces.py`)
- **Updated**: `create_traces()` method signature
- **Parameter**: `show_catred_mertile_data` → `catred_mode`
- **Enhanced**: `_add_manual_catred_traces()` to handle mode-specific trace naming
- **Updated**: Trace names to include "Masked" or "Unmasked" labels

## Data Flow

### Masked CATRED Process:
1. User selects "Masked CATRED data" from radio button
2. Zoom into region < 2° to enable render button
3. Click "🔍 Render CATRED Data" button
4. System loads effective coverage mask for each MER tile
5. Converts CATRED source positions to HEALPix cells
6. Filters sources based on effective coverage threshold (≥0.8)
7. Displays filtered sources as "CATRED Masked Data" traces

### Unmasked CATRED Process:
1. User selects "Unmasked CATRED data" from radio button
2. Same zoom and render process as before
3. All CATRED sources displayed without filtering
4. Traces labeled as "CATRED Unmasked Data"

## Key Features

### 1. Threshold-Based Filtering
- Default threshold: 0.8 (80% effective coverage)
- Configurable through function parameters
- Uses HEALPix WEIGHT field from effective coverage masks

### 2. Seamless Integration
- Preserves existing functionality for unmasked mode
- Same UI controls and workflow
- Backward compatible with existing traces

### 3. Error Handling
- Graceful fallback when mask files unavailable
- Clear debug messages for troubleshooting
- Proper validation of required data sources

## Required Data Sources

### For Masked Mode:
1. **CATRED files**: Individual MER tile FITS files with source catalogs
2. **Effective coverage masks**: HEALPix masks with WEIGHT field
3. **File info DataFrames**: 
   - `catred_info`: Links MER tile IDs to CATRED FITS files
   - `effcovmask_info`: Links MER tile IDs to effective coverage mask files

### Dependencies Added:
- `astropy.io.fits` (already imported via myutils)
- `astropy.table.Table`
- `healpy as hp`
- `numpy as np`

## Testing Status
✅ All modules import successfully  
✅ Mask class instantiates correctly  
✅ CATREDHandler has all new methods  
✅ UI radio button implemented  
✅ Callbacks updated for 3-way mode  
✅ Trace creator handles mode parameter  

## Usage
1. Launch the Dash application
2. Select algorithm and render initial view
3. Toggle "High-res CATRED data" radio to desired mode
4. Zoom into region of interest (< 2°)
5. Click "🔍 Render CATRED Data" to load high-resolution data
6. Switch between modes as needed - data will be filtered appropriately

## Benefits
- **Scientific Value**: Filter out sources in regions with poor observational coverage
- **Performance**: Reduces data volume in regions with incomplete coverage
- **Flexibility**: Easy toggle between filtered and unfiltered views
- **Reproducibility**: Consistent threshold-based filtering methodology
