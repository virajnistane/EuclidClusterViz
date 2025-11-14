# Cluster Analysis Tab - Feature Guide

## Overview

The Cluster Analysis tab provides dedicated tools for in-depth analysis of individual clusters. This tab allows you to generate cutouts, view high-resolution catalog data, and visualize coverage information centered on selected clusters.

## Quick Start

1. **Select a Cluster**: Click any cluster point in the main visualization plot
2. **Switch to Cluster Analysis Tab**: Click the "Cluster Analysis" tab
3. **View Cluster Information**: Selected cluster details appear at the top
4. **Choose Analysis Type**: Use one of three analysis tools (cutout, CATRED box, or mask)
5. **Configure Parameters**: Click the action button to expand options
6. **Generate Visualization**: Click the action button again to create the overlay
7. **Manage Traces**: Use Hide/Show and Clear buttons to control visibility

## Features

### 1. **Mosaic Cutouts**

Generate MER mosaic image cutouts centered on the selected cluster.

#### **How to Use**
1. Select a cluster in the main plot
2. In Cluster Analysis tab, find the "Cutout Generation" section
3. Click "Generate Cutout" to expand options (or generate with defaults)
4. Configure parameters:
   - **Size**: Cutout size in arcminutes (default: 5.0)
   - **Opacity**: Image transparency 0.0-1.0 (default: 0.8)
   - **Colorscale**: Choose from Greys, Viridis, Plasma, etc.
5. Click "Generate Cutout" to create the overlay
6. Use "Hide Cutouts"/"Show Cutouts" to toggle visibility
7. Use "Clear All Cutouts" to remove all cutout traces

#### **Use Cases**
- Visual inspection of cluster environments
- Identifying optical counterparts
- Assessing image quality in cluster regions
- Comparing multiple clusters by generating sequential cutouts

#### **Technical Notes**
- Cutouts are rendered as image overlays at cluster coordinates
- Multiple cutouts can be displayed simultaneously
- Traces are named 'MER-Mosaic cutout' for identification
- Cutouts persist across algorithm switches and data updates

### 2. **CATRED Box Views**

Load high-resolution catalog data (CATRED) in a box around the selected cluster.

#### **How to Use**
1. Select a cluster in the main plot
2. In Cluster Analysis tab, find the "CATRED Box View" section
3. Click "View CATRED Box" to expand options
4. Configure parameters:
   - **Box Size**: Area size in degrees (default: 0.1°)
   - **Redshift Bin Width**: z-space tolerance (default: 0.05)
   - **Mask Threshold**: Effective coverage minimum (default: 0.05)
   - **Magnitude Limit**: Maximum VIS magnitude (default: 25.0)
   - **Marker Size Mode**: Constant or KRON_RADIUS-based
   - **Marker Size**: Size in pixels (default: 3)
   - **Marker Color**: Choose color for catalog points
5. Click "View CATRED Box" to load the data
6. Use "Hide CATRED Boxes"/"Show CATRED Boxes" to toggle visibility
7. Use "Clear All CATRED Boxes" to remove all box traces

#### **Use Cases**
- Detailed photometric analysis around clusters
- Galaxy population studies in cluster regions
- Photometric redshift distribution analysis
- Cross-matching with cluster member candidates

#### **Technical Notes**
- CATRED data is loaded from HEALPix-based catalog files
- Masked mode applies effective coverage thresholding
- Traces are named 'CATRED {mode} - Boxed' for identification
- Click individual CATRED points to view PHZ probability distributions
- Data persists across zoom/pan operations

### 3. **Mask Cutouts**

Generate HEALPix effective coverage cutouts showing survey footprint around clusters.

#### **How to Use**
1. Select a cluster in the main plot
2. In Cluster Analysis tab, find the "Mask Cutout" section
3. Click "Generate Mask Cutout" to expand options
4. Configure parameters:
   - **Size**: Cutout size in degrees (default: 0.2°)
   - **Opacity**: Mask transparency 0.0-1.0 (default: 0.6)
5. Click "Generate Mask Cutout" to create the overlay
6. Use "Hide Mask Cutouts"/"Show Mask Cutouts" to toggle visibility
7. Use "Clear All Mask Cutouts" to remove all mask traces

#### **Use Cases**
- Assessing survey coverage quality in cluster regions
- Identifying edge effects or coverage gaps
- Understanding completeness for cluster member detection
- Comparing coverage across different clusters

#### **Technical Notes**
- Displays HEALPix pixels (NSIDE=16384) showing effective weight
- Color-coded by coverage quality (viridis colormap)
- Traces are named 'Mask overlay (cutout)' for identification
- Independent from global mask overlay controls

## Workflow Best Practices

### **Single Cluster Deep Dive**
1. Select cluster of interest
2. Generate mosaic cutout for visual context
3. Load CATRED box for photometric analysis
4. Generate mask cutout to check coverage
5. Click CATRED points to view PHZ distributions
6. Use trace management to show/hide layers as needed

### **Comparative Analysis**
1. Select first cluster, generate all three analysis types
2. Hide all traces to clean view
3. Select second cluster, generate analysis types
4. Toggle visibility to compare clusters side-by-side
5. Clear traces when finished to start fresh

### **Performance-Conscious Analysis**
1. Start with single analysis type (e.g., cutout only)
2. Verify results before adding more overlays
3. Use smaller box/cutout sizes for faster loading
4. Clear traces regularly to maintain performance
5. Use hide/show instead of regenerating when possible

## Smart UI Features

### **Mutual Exclusivity**
- Only one options section (cutout/CATRED box/mask) expands at a time
- Click any action button to collapse others automatically
- Cleaner interface with focused parameter controls

### **Parameter Synchronization**
- Main sidebar and Cluster Analysis tab share parameter values
- Changes in one location update the other
- Consistent analysis settings across the application

### **Automatic Button Management**
- Trace management buttons (Hide/Clear) enable when traces exist
- Buttons disable when no traces are present
- Hide button text toggles between "Hide" and "Show"
- Clear indication of available actions

### **Button Placement**
- Trace management controls directly below action buttons
- Intuitive workflow: Generate → Manage → Clear
- No need to hunt for controls in separate sections

## Technical Implementation

### **Trace Naming Conventions**
- **Mosaic cutouts**: `'MER-Mosaic cutout'`
- **CATRED boxes**: `'CATRED {masked/unmasked} - Boxed'`
- **Mask cutouts**: `'Mask overlay (cutout)'`

### **Trace Preservation**
All cluster analysis traces are preserved during:
- Algorithm switching (PZWAV ↔ AMICO ↔ BOTH)
- SNR/redshift filtering
- Global CATRED rendering/clearing
- Global mosaic/mask overlay operations
- Zoom/pan operations

### **Layer Ordering**
Cluster analysis traces render in proper order:
```
Bottom → Top:
1. Global mosaics
2. Global masks
3. Mosaic cutouts (cluster-centered)
4. Mask cutouts (cluster-centered)
5. Global CATRED
6. CATRED boxes (cluster-centered)
7. Clusters
```

### **Callback Architecture**
- Independent callbacks for each trace type
- Non-interfering with main plot updates
- Efficient state management using Dash patterns
- Client-side filtering compatibility

## Troubleshooting

### **No Cluster Selected**
**Issue**: Action buttons show "No cluster selected"
**Solution**: Click a cluster point in the main visualization plot

### **Empty Cutouts/Boxes**
**Issue**: Generated overlay shows no data
**Possible Causes**:
- Cluster outside available mosaic/CATRED coverage
- Box size too small (increase size parameter)
- Magnitude limit too restrictive (increase limit)
- Mask threshold too high (decrease threshold)

### **Slow Generation**
**Issue**: Cutout/box generation takes long time
**Solutions**:
- Reduce box/cutout size
- Increase mask threshold to filter more data
- Decrease magnitude limit for fewer objects
- Clear existing traces before generating new ones

### **Traces Not Visible**
**Issue**: Generated traces don't appear
**Check**:
- Opacity setting (should be > 0)
- Trace visibility (use Show button)
- Zoom level (may need to zoom to cluster region)
- Layer ordering (traces may be behind others)

### **Button States Not Updating**
**Issue**: Hide/Clear buttons remain disabled
**Solution**: 
- Generate at least one trace first
- Check browser console for errors
- Refresh page if state becomes inconsistent

## Integration with Other Features

### **PHZ Analysis**
- Click CATRED box points to view photometric redshift PDFs
- PHZ plot updates automatically with point information
- Uses `pointNumber` for accurate point identification
- Works for both global and box CATRED traces

### **Main Plot Filtering**
- SNR and redshift filters apply to cluster selection
- Filtered clusters remain selectable for analysis
- Analysis operates on raw data regardless of filters

### **Global Overlays**
- Cluster analysis traces independent from global controls
- Global mosaic/mask rendering doesn't affect analysis traces
- Can combine global and cluster-specific views
- Independent opacity controls for each layer type

## Advanced Usage

### **Multiple Cluster Comparison**
```
Workflow:
1. Select cluster A → Generate cutout
2. Select cluster B → Generate cutout
3. Select cluster C → Generate cutout
4. Toggle visibility to compare environments
5. Use "Clear All Cutouts" to start fresh
```

### **Coverage Quality Assessment**
```
Workflow:
1. Select cluster → Generate mask cutout
2. Note coverage values in region
3. Generate CATRED box with appropriate threshold
4. Verify data quality matches coverage
5. Document coverage for cluster analysis
```

### **Photometric Analysis Pipeline**
```
Workflow:
1. Select cluster → Generate CATRED box
2. Set narrow redshift bin (e.g., 0.02)
3. Apply strict magnitude limit (e.g., 23.0)
4. Click individual objects to check PHZ
5. Identify likely cluster members
6. Export analysis results
```

## Future Enhancements

Planned features for cluster analysis:
- Export cutouts as FITS files
- Save CATRED box data as catalogs
- Automated cluster member selection
- Cross-matching with external catalogs
- Statistical analysis of box populations
- Batch processing for multiple clusters

---

For more information, see:
- [Main README](../../../README.md) - Complete application documentation
- [USAGE.md](USAGE.md) - General usage guide
- [PHZ Analysis](../../../README.md#phz-photometric-redshift-analysis) - PHZ feature details
