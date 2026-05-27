## Aladin Lite v3 View Guide

## Overview

Aladin Lite v3 is an interactive sky viewer developed by the CDS (Centre de Données astronomiques de Strasbourg). ClusterViz embeds it as a secondary view mode alongside the standard Plotly scatter plot. When active, Aladin Lite replaces the Plotly panel and shows a real DSS/HiPS sky image centered on the selected cluster, with catalog overlay markers drawn for detected clusters and CATRED sources.

Key properties of the integration:

- The Aladin JS library is **not bundled** — it is lazy-loaded from the CDS CDN on first use.
- All Aladin interaction (initialization, catalog overlays, click handling) runs as **clientside JavaScript** inside Dash clientside callbacks; no round-trip to the Python server is required after the initial data push.
- A skeleton loading animation covers the viewer while the sky tiles are loading.

The implementation lives across two modules:

- `cluster_visualization/ui/aladin_view.py` — Dash layout component (`create_aladin_view`)
- `cluster_visualization/callbacks/aladin_callbacks.py` — `AladinCallbacks` class (server-side overlay data push)
- `cluster_visualization/callbacks/ui_callbacks.py` — clientside JS bridge (lazy-load, init, catalog overlays, click poll)

---

## Switching to Aladin View Mode

Two UI entry points control the view mode.

### Header toggle buttons

A `dbc.ButtonGroup` is placed in the page header (defined in `cluster_visualization/ui/esasky_view.py`):

- **Standard View** (`view-mode-plotly-btn`) — shows the Plotly RA/Dec scatter plot. Active (filled) by default.
- **Aladin View** (`view-mode-aladin-btn`) — shows the Aladin Lite sky viewer. Disabled (greyed out) until exactly one cluster is in the viewport; a tooltip reads "Zoom to exactly 1 cluster to enable Aladin view".

Clicking either button writes `'plotly'` or `'aladin'` to the `view-mode-store` `dcc.Store`. A single clientside callback watches that store and toggles `display` on `#plotly-view-container` and `#aladin-view-container`.

### Mosaic sidebar radio

Inside the Mosaic sidebar section (defined in `cluster_visualization/ui/data_controls.py`) a `dcc.RadioItems` with id `image-source-radio` offers:

- `"MER Mosaic"` — standard Plotly view with mosaic overlay
- `"Aladin Sky"` — identical to clicking the Aladin View header button

Selecting `"Aladin Sky"` writes `'aladin'` to `view-mode-store` via a second clientside callback. The radio value is kept in sync whenever `view-mode-store` changes.

---

## Single-Cluster Constraint

Aladin view is only available when **exactly one** cluster point is visible in the current Plotly viewport.

This constraint is enforced by a clientside callback that runs on every `relayoutData` (zoom/pan) event and on figure updates. The callback iterates the Plotly traces, counts cluster points whose `(x, y)` coordinates fall inside the current axis ranges, and:

- Sets `view-mode-aladin-btn.disabled = (count !== 1)`.
- Writes the count and viewport bounds to `viewport-cluster-count-store` so the server-side overlay push callback (`push_overlay_data`) can read the exact RA/Dec ranges without re-parsing the figure.
- Updates `image-source-radio.options` to disable the `"Aladin Sky"` option when `count !== 1`.

**Why one cluster?** Aladin Lite is a sky viewer centered on a single (RA, Dec) point. Displaying multiple clusters simultaneously would require panning between them manually. The single-cluster gate ensures the viewer always opens at the correct sky position and FOV for the selected cluster, providing a meaningful image context.

---

## Available Sky Surveys

The survey is selected from a `dcc.Dropdown` with id `aladin-survey-dropdown` (visible only in Aladin mode). Changing the dropdown calls a clientside callback that calls `window._aladinInstance.setImageSurvey(survey)` immediately, without a server round-trip.

| Label | HiPS ID | Notes |
|---|---|---|
| DSS2 Color | `P/DSS2/color` | Default. Digitized Sky Survey 2 color composite; broad sky coverage. |
| Euclid VIS Q1 | `CDS/P/Euclid/Q1/VIS` | Euclid Q1 visible-band imaging. High resolution; coverage limited to Q1 footprint. |
| Euclid NIR Q1 (color) | `CDS/P/Euclid/Q1/NIR` | Euclid Q1 near-infrared color composite (Y/J/H). |
| 2MASS H | `P/2MASS/H` | 2 Micron All-Sky Survey H-band; full-sky near-infrared coverage. |
| WISE W1 | `P/allWISE/color` | AllWISE color composite; useful for identifying galaxies and clusters at mid-infrared wavelengths. |

The survey value is also included in the overlay JSON pushed to `aladin-overlay-data-store`, so the correct survey is applied when the viewer first initializes (not just when the dropdown changes post-init).

---

## SNR and Redshift Filter Pass-Through

The server-side callback `push_overlay_data` in `AladinCallbacks` respects the SNR and redshift sliders that are also used by the main Plotly view. It reads:

- `snr-range-slider-pzwav.value` (PZWAV algorithm) or `snr-range-slider-amico.value` (AMICO algorithm) — whichever matches the selected algorithm.
- `redshift-range-slider.value` — applied to the `Z_CLUSTER` column.

Filtering is applied after the 2×FOV spatial cut:

```python
snr_mask = (snr_sub >= snr_range[0]) & (snr_sub <= snr_range[1])
z_mask   = (z_sub  >= redshift_range[0]) & (z_sub  <= redshift_range[1])
```

Only clusters that pass both filters are included in the `"clusters"` list pushed to `aladin-overlay-data-store`. This means the Aladin catalog overlay always reflects the same population shown in the Plotly view — adjusting the SNR or redshift slider will re-trigger `push_overlay_data` and refresh the overlay markers.

The spatial 2×FOV pre-filter clips to a circle of radius `2 × FOV` around the viewport center using the helper `_filter_within_2fov_vectorized`, which avoids sending the entire catalog to the browser on large datasets.

---

## Skeleton Loading UX

A dark shimmer overlay (`id="aladin-skeleton"`, CSS class `aladin-skeleton-overlay`) covers `#aladin-div` while the viewer is initializing. It contains three animated circles of decreasing size (`.skeleton-star`) and a label "Loading sky view...".

The animation is defined in `cluster_visualization/ui/enhanced_styles.css`:

```css
.skeleton-star {
    background: linear-gradient(90deg, #1a1a3a 25%, #2a2a5a 50%, #1a1a3a 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}
```

**When the skeleton appears:** A clientside callback watching `view-mode-store` sets `aladin-skeleton.style.display = 'flex'` immediately when the mode switches to `'aladin'`. This gives visual feedback before the CDN scripts finish loading.

**When the skeleton hides:** Inside the JS `setupCatalogs` function, as soon as `A.aladin()` has returned and the viewer is positioned, the code runs:

```javascript
var sk = document.getElementById('aladin-skeleton');
if (sk) sk.style.display = 'none';
```

The skeleton disappears at the moment the viewer is ready to show tiles, even before all catalog sources have been added (those are injected on the next animation frame via `requestAnimationFrame`).

---

## Clientside JS Architecture

### CDN lazy-load

Aladin Lite v3 is loaded from the CDS CDN on the first call to the JS bridge callback:

```
https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.min.css
https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js
```

The bridge checks for `document.getElementById('aladin-css')` and `document.getElementById('aladin-js')` before creating `<link>` and `<script>` tags. If the script tag is being freshly added, the bridge defers `doAladinInit()` to the `script.onload` handler and returns `no_update` to Dash. On subsequent calls (script already loaded), `doAladinInit()` is called synchronously.

A preload `dcc.Interval` (`id="aladin-preload-interval"`, interval 3 000 ms, `max_intervals=1`) is defined in the layout for future use as a background pre-init trigger. It is created with `disabled=True` and is not wired to the view-mode-store callback, so it does not fire automatically in the current implementation.

### Viewer initialization

`A.aladin('#aladin-div', {...})` is called only after the `#aladin-div` element has a non-zero layout size. A `tryInit()` retry loop polls `divEl.offsetWidth` every 50 ms (up to 40 attempts, i.e. 2 seconds) to handle the case where the container is still hidden or animating into view. Once created, the instance is stored at `window._aladinInstance`.

Options passed at init time:

```javascript
{
    target: ra + ' ' + dec,
    fov: fov,
    survey: survey,
    cooFrame: 'J2000',
    showReticle: false,
    showZoomControl: false,
    showLayersControl: true,
    showFrame: false,
    showGotoControl: false,
    showShareControl: false,
    showProjectionControl: false
}
```

On subsequent mode switches (when `window._aladinInstance` already exists), the bridge calls `gotoRaDec`, `setFov`, and `setImageSurvey` on the existing instance instead of creating a new one.

### Catalog overlays

After init, `setupCatalogs(aladin)` is called. It:

1. Calls `aladin.removeLayers()` to clear stale overlays from previous data pushes.
2. Hides the skeleton overlay.
3. Creates three `A.catalog()` objects: `PZWAV Clusters` (orange `×` markers), `AMICO Clusters` (orange `+` markers), and `CATRED` (cyan `○` markers).
4. Sorts incoming cluster entries into PZWAV or AMICO buckets by inspecting `r.name.toUpperCase()` for the string `'AMICO'`.
5. Adds sources and catalogs to Aladin in two `requestAnimationFrame` passes so that sky tile loading is not blocked by JS source insertion.

The data pushed to `aladin-overlay-data-store` has this shape:

```json
{
    "clusters": [{"ra": 180.0, "dec": 0.0, "name": "PZWAV_0001", "SNR": 4.5, "Z": 0.3}],
    "catred":   [{"ra": 180.1, "dec": 0.1, "name": "CATRED"}],
    "viewport": {"ra": 180.0, "dec": 0.0, "fov": 0.5},
    "survey":   "P/DSS2/color"
}
```

### HEALPix detection mask

The HEALPix detection mask is added as a HiPS overlay image layer (no server-side data transfer):

```javascript
var maskHips = inst.createImageSurvey(
    'mask_detcl', 'Detection Mask',
    'https://erass-cluster-inspector.com/euclid/hips/mask_detcl/',
    'equatorial', 5, {imgFormat: 'png'}
);
inst.setOverlayImageLayer(maskHips, 'mask_detcl');
window._aladinMaskLayer.setOpacity(0.3);
```

Errors from this block are caught and logged as warnings; a missing mask does not prevent the viewer from loading.

### Click bridge

When the user clicks on a catalog source in Aladin, the `objectsSelected` event stores click data at `window._aladinPendingClick`. A `dcc.Interval` (`id="aladin-click-poll-interval"`, 500 ms, enabled only in Aladin mode) polls this variable via a clientside callback and forwards it to `aladin-click-store` for downstream server-side handling.

---

## Troubleshooting

### CDN blocked — no sky imagery or blank viewer

**Symptom:** The skeleton never disappears, or the viewer loads but shows a black/empty canvas with no sky tiles.

**Cause:** The Aladin Lite JS/CSS is fetched from `aladin.cds.unistra.fr` at runtime. If the ClusterViz server runs in an air-gapped environment or behind a firewall that blocks outbound HTTPS to that host, the script tag will fail silently and `A` will remain undefined.

**Diagnosis:** Open the browser developer console. Look for network errors on requests to `aladin.cds.unistra.fr`, or a JS error such as `ReferenceError: A is not defined`.

**Workaround:** Download the Aladin Lite v3 bundle (`aladin.js` and `aladin.min.css`) and serve them from a local HTTP server or from the Dash `assets/` folder. Update the `href` and `src` strings in `_setup_view_mode_callbacks` inside `cluster_visualization/callbacks/ui_callbacks.py` to point to your local paths.

### Skeleton stuck — JS loaded but viewer blank

**Symptom:** The shimmer animation plays indefinitely; the skeleton never hides. The browser console shows no network errors.

**Cause:** This can happen if:

- `#aladin-div` is still hidden or has zero dimensions when `tryInit()` runs. The retry loop polls for 2 seconds; if the CSS transition takes longer the loop exits without calling `A.aladin()`.
- `A.init` (the Aladin v3 async-init promise) rejected.

**Diagnosis:** In the console, run `window._aladinInstance`. If `undefined`, initialization never completed. Check for `[Aladin] A.init failed:` in the console.

**Fix:** Manually call `document.getElementById('aladin-skeleton').style.display = 'none'` to dismiss the skeleton, then check whether a fresh page reload resolves the issue. If the `#aladin-div` size is the culprit (e.g. a CSS animation conflict), increase the retry limit by changing the hardcoded `40` in `if (attempts++ < 40)` inside the `tryInit` function in `_setup_view_mode_callbacks`.

### Catalog markers not showing

**Symptom:** The sky view loads and shows imagery correctly, but no cluster or CATRED markers appear.

**Cause:** The server-side `push_overlay_data` callback may not have fired, or it returned an empty `"clusters"` list.

**Diagnosis:** Check the Python server log for lines prefixed `[Aladin]`:

```
[Aladin] Viewport: RA=... Dec=... FOV=...
[Aladin] Pushed N cluster entries (2×FOV filter)
[Aladin] Pushed N CATRED entries (2×FOV filter)
```

If `N = 0`, the 2×FOV spatial filter excluded all sources. This can happen if the `viewport-cluster-count-store` RA/Dec ranges were stale or inverted. Pan/zoom slightly to re-trigger the viewport store, then switch to Aladin mode again.

If the `[Aladin]` lines do not appear at all, `push_overlay_data` was not triggered. Verify that `view-mode-store` received the `'aladin'` value (check the browser Dash DevTools store inspector) and that the callback registered without errors at startup.
