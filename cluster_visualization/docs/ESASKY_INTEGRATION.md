# ESASky API Integration

## Overview

The application now uses **ESASky** (ESA's astronomy visualization tool) instead of Aladin Lite for sky viewing functionality. ESASky provides a more comprehensive set of astronomical surveys and integrated ESA mission data.

## Key Features

- **Interactive Sky Atlas**: Browse the sky with multiple survey options
- **Click Synchronization**: Click on clusters in the main plot to center ESASky view
- **Overlay Mode**: Toggle ESASky as a semi-transparent overlay on the cluster plot
- **Real-time Zoom Sync**: ESASky automatically matches your cluster plot zoom level
- **Multi-Survey Support**: DSS2, PanSTARRS, 2MASS, SDSS, AllWISE, Herschel, and more

## Implementation

### Technology

ESASky is embedded as an iframe and controlled via the postMessage API:
- **API Documentation**: https://www.cosmos.esa.int/web/esdc/esasky-javascript-api
- **Communication**: Uses window.postMessage() for cross-origin iframe control
- **Base URL**: https://sky.esa.int/esasky/

### API Events Used

1. **goToRaDec**: Navigate to specific coordinates
   ```javascript
   iframe.postMessage({
       event: 'goToRaDec',
       content: { ra: '10.68', dec: '41.27' }
   }, '*');
   ```

2. **setFov**: Set field of view in degrees
   ```javascript
   iframe.postMessage({
       event: 'setFov',
       content: { fov: '0.5' }
   }, '*');
   ```

3. **setHiPS**: Change sky survey
   ```javascript
   iframe.postMessage({
       event: 'setHiPS',
       content: { hipsName: 'DSS2 color' }
   }, '*');
   ```

## User Interface

### Tab View (🔭 Aladin Sky Tab)
- Full ESASky interface in the right panel
- Survey selector dropdown
- Manual FOV control input
- Automatically centers on clicked clusters

### Overlay Mode (Toggle Sky Overlay Button)
- Translucent ESASky view over cluster plot
- Synchronized zoom and pan with plot
- Quick toggle on/off
- Maintains plot interactivity underneath

## Available Sky Surveys

- **DSS2 color**: Digitized Sky Survey (optical)
- **PanSTARRS DR1 color**: Pan-STARRS optical survey
- **2MASS**: Two Micron All Sky Survey (infrared)
- **SDSS9 color**: Sloan Digital Sky Survey
- **AllWISE color**: Wide-field Infrared Survey Explorer
- **Herschel color**: Herschel Space Observatory (far-infrared)

## Usage Tips

1. **Navigate**: Click any cluster to instantly center ESASky on that position
2. **Zoom Sync**: When overlay is active, zoom/pan in cluster plot updates ESASky
3. **Survey Selection**: Choose different surveys to see various wavelengths
4. **FOV Control**: Manually adjust field of view from 0.01° to 180°
5. **Overlay Toggle**: Click button to show/hide sky view while keeping cluster plot visible

## Differences from Aladin Lite

| Feature | Aladin Lite | ESASky |
|---------|-------------|---------|
| Implementation | JavaScript library | iframe with postMessage API |
| Initialization | Direct DOM manipulation | iframe communication |
| Surveys | HiPS identifiers (P/DSS2/color) | Survey names (DSS2 color) |
| ESA Integration | None | Native ESA missions data |
| Catalogs | Yes | Yes (built-in) |
| Performance | Lower memory | Higher memory (full app) |

## Troubleshooting

**ESASky not responding:**
- Check browser console for postMessage errors
- Ensure iframe has loaded (may take a few seconds)
- Verify network connectivity to sky.esa.int

**Overlay not syncing:**
- Toggle overlay off and on to reinitialize
- Check that cluster plot has valid zoom ranges
- Ensure browser allows cross-origin iframe communication

**Survey changes not working:**
- Some surveys may not be available for all coordinates
- Check console for ESASky API responses
- Try a different survey option

## Technical Notes

- ESASky URL includes `hide_welcome=true&hide_banner_info=true` for cleaner embed
- Default coordinate frame is J2000 (ICRS)
- postMessage uses wildcard origin ('*') for iframe communication
- Overlay opacity set to 0.95 for optimal visibility balance
