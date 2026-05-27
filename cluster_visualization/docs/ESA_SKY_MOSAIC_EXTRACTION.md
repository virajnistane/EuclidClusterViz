# ESA Sky Mosaic Extraction

This document describes how the `MOSAICHandler` fetches, georeferences, and
renders mosaic imagery from the public [CDS hips2fits](https://alasky.cds.unistra.fr/hips-image-services/hips2fits)
service as an alternative to the local Euclid DpdMerBksMosaic.

---

## Overview

The extraction pipeline has six steps:

```
MER tile ID
    │
    ▼
1. _extract_tile_bounds()          — polygon → (ra_min, ra_max, dec_min, dec_max)
    │
    ▼
2. FOV calculation                 — fov_deg = max(RA_span, Dec_span) × 1.05
    │
    ▼
3. HTTP GET  hips2fits endpoint    — returns JPEG in astronomical orientation
    │
    ▼
4. FOV → coordinate bounds         — cos(dec) correction for RA extent
    │
    ▼
5. Orientation fix  [::-1, ::-1]  — North-up/East-left → Plotly convention
    │
    ▼
6. go.Heatmap trace                — x = RA coords, y = Dec coords, z = pixel values
```

---

## Step 1 — Tile bounds from catalogue polygon

`MOSAICHandler._extract_tile_bounds(data, mertileid)` looks up the Shapely
polygon stored in the catred catalogue for the requested MER tile ID and returns
the bounding box:

```python
(ra_min, ra_max, dec_min, dec_max)   # all in degrees
```

This defines the sky region that the local MER FITS tile covers and is used as
the anchor for both the FOV calculation and the alignment assertions in tests.

---

## Step 2 — Field-of-view calculation

`_load_esa_cutout_by_mertile` derives a square field of view that fully encloses
the tile polygon with a 5 % margin:

```python
fov_deg = max(abs(ra_max - ra_min), abs(dec_max - dec_min)) * 1.05
```

`fov_deg` is measured in **sky-angle degrees** — the angular distance on the
celestial sphere, not degrees of right-ascension coordinate.  The distinction
matters at high declinations (see Step 4).

---

## Step 3 — HTTP request to CDS hips2fits

The service is queried with the following parameters:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `hips` | e.g. `CDS/P/Euclid/Q1/VIS` | HiPS survey identifier |
| `ra` | tile centre RA (deg) | Image centre, right ascension |
| `dec` | tile centre Dec (deg) | Image centre, declination |
| `fov` | `fov_deg` | Sky-angle size of the square cutout |
| `width` / `height` | `esa_cutout_width` / `esa_cutout_height` (default 768) | Output pixel dimensions |
| `projection` | `TAN` | Gnomonic (tangent-plane) WCS projection |
| `format` | `jpg` | Return format |

The full URL is constructed with `urllib.parse.urlencode` and fetched with
`urllib.request.urlopen`.

### Astronomical orientation of the returned image

hips2fits returns images in **standard astronomical orientation**:

- **North up** — row 0 of the pixel array corresponds to maximum declination.
- **East left** — column 0 corresponds to maximum right ascension.

So `image_array[0][0]` = **(max Dec, max RA)** and
`image_array[-1][-1]` = **(min Dec, min RA)**.

---

## Step 4 — Converting FOV to coordinate bounds

The image covers `fov_deg × fov_deg` of **sky angle** centred at
`(center_ra, center_dec)`.  The Dec extent maps directly to coordinate degrees:

$$\Delta\text{Dec} = f_\text{ov}$$

However, lines of constant RA converge towards the celestial poles.  At
declination $\delta$, one sky-angle degree along RA corresponds to
$1 / |\cos\delta|$ degrees of RA coordinate.  Therefore the RA coordinate
half-extent is:

$$\Delta\text{RA}_\text{coord} = \frac{f_\text{ov}}{2\,|\cos\delta_0|}$$

where $\delta_0$ is the tile centre declination.  In code:

```python
center_dec_rad = np.radians(center_dec)
cos_dec        = np.abs(np.cos(center_dec_rad))
half_fov_ra    = fov_deg / (2.0 * cos_dec)   # RA coordinate degrees
half_fov_dec   = fov_deg / 2.0               # Dec degrees (unchanged)

img_ra_min  = center_ra  - half_fov_ra
img_ra_max  = center_ra  + half_fov_ra
img_dec_min = center_dec - half_fov_dec
img_dec_max = center_dec + half_fov_dec
```

### Why this matters

At Dec ≈ −50° (typical Euclid Q1 EDF-S field), $|\cos(-50°)| \approx 0.643$,
so the RA coordinate extent is roughly **1.56× wider** than the Dec extent for
the same sky-angle FOV.  Using the tile polygon edges directly (as was done
before the fix) gave equal widths to both axes, shifting the image ≈ 0.15° in
RA relative to the actual pixel content.

---

## Step 5 — Orientation fix

Plotly `go.Heatmap` maps `z[i][j]` to the point `(x[j], y[i])`.  With:

```python
x_coords = np.linspace(ra_min,  ra_max,  width)   # increasing RA →
y_coords = np.linspace(dec_min, dec_max, height)   # increasing Dec ↑
```

cell `z[0][0]` lands at `(ra_min, dec_min)` — the **bottom-left** of the plot.

The hips2fits JPEG has its `[0][0]` corner at **(max Dec, max RA)**, the
top-right in sky coordinates, which is the opposite corner.  A double flip
corrects this:

```python
processed_image = image_array[::-1, ::-1].copy()
# After flip: [0][0] = (min Dec, min RA)  ✓
```

This is exactly consistent with the local FITS path, which achieves the same
result via `PIL.Image.Transpose.FLIP_LEFT_RIGHT` followed by the bottom-row-first
storage convention of FITS data.

---

## Step 6 — Heatmap trace creation

`create_mosaic_image_trace` builds the final Plotly trace:

```python
height, width = processed_image.shape
x_coords = np.linspace(bounds["ra_min"],  bounds["ra_max"],  width)
y_coords = np.linspace(bounds["dec_min"], bounds["dec_max"], height)

trace = go.Heatmap(
    z=processed_image,
    x=x_coords,
    y=y_coords,
    opacity=opacity,
    colorscale=colorscale,
    showscale=False,
    name=f"Mosaic (ESA) {mertileid}",
    ...
)
```

The same convention is used for local FITS tiles, so both providers produce
traces that are directly comparable when placed in the same Plotly subplot or
overlaid on the cluster scatter plot.

---

## Configuration keys

All tunable parameters live in `config.ini` under the `[esa]` section:

| Key | Default | Description |
|-----|---------|-------------|
| `cutout_base_url` | *(required)* | hips2fits endpoint URL |
| `source_default` | `CDS/P/DSS2/color` | Default HiPS survey |
| `cutout_width` | `768` | Pixel width of fetched image |
| `cutout_height` | `768` | Pixel height of fetched image |
| `timeout_seconds` | `30` | HTTP request timeout |
| `source_cache_ttl_seconds` | `21600` | TTL for cached source list (6 h) |
| `mocserver_url` | *(optional)* | CDS MOC server for source discovery |

---

## Known HiPS survey IDs

| ID | Description |
|----|-------------|
| `CDS/P/Euclid/Q1/VIS` | Euclid Q1 VIS (default for MER comparison) |
| `CDS/P/Euclid/Q1/color` | Euclid Q1 colour composite |
| `CDS/P/Euclid/ERO/VIS` | Euclid Early Release Observations VIS |
| `CDS/P/DSS2/color` | DSS2 colour (wide-field context) |
| `CDS/P/2MASS/color` | 2MASS colour |
| `CDS/P/allWISE/color` | AllWISE colour |

Additional surveys are discovered at runtime via the MOC server if
`esa.mocserver_url` is configured; the list above is used as the fallback.

---

## ESA Sky Interactive View Mode

This section describes the **ESA Sky view mode**, which is distinct from the
mosaic extraction pipeline above.  The mosaic pipeline fetches HiPS cutout
images and renders them as Plotly `go.Heatmap` traces inside the standard
scatter plot.  The ESA Sky view mode replaces the entire plot area with a
live-updated iframe embedding the public ESA Sky web application at
`https://sky.esa.int`.

### What it is

ESA Sky is an interactive sky atlas provided by the European Space Agency.
When the app switches to ESA Sky mode the `cluster-plot` Plotly graph is hidden
and the iframe is shown in its place, occupying the same 75 vh canvas.  The
viewer gives the analyst full access to ESA's multi-wavelength survey archive
without leaving the ClusterViz interface.

### How it differs from mosaic extraction

| Aspect | Mosaic extraction | ESA Sky view mode |
|--------|-------------------|--------------------|
| Renderer | Plotly `go.Heatmap` inside Dash | ESA Sky iframe (external JS app) |
| Data path | `MOSAICHandler` → hips2fits HTTP → pixel array | Dash pushes viewport + catalog JSON → `postMessage` → iframe |
| Interactivity | Zoom / pan via Plotly; Python callbacks | Native ESA Sky UI inside iframe |
| Catalog overlays | Plotly scatter traces | ESA Sky's own overlay API |
| Offline use | Works if hips2fits endpoint is reachable | Requires network access to `sky.esa.int` |

### Activating ESA Sky view mode

The active view is controlled by `view-mode-store` (a `dcc.Store` with string
value).  Setting this store to `"esasky"` hides the Plotly container and shows
the iframe.  The header toggle created by `create_view_mode_toggle` in
`ui/esasky_view.py` manages switching between `"plotly"`, `"aladin"`, and
`"esasky"` modes.

> **Note**: the current production toggle only exposes `"plotly"` and `"aladin"`
> buttons.  ESA Sky mode can be enabled programmatically by writing `"esasky"`
> to `view-mode-store`, or by extending `create_view_mode_toggle`.

### postMessage API

All communication from the Dash app to the ESA Sky iframe goes through the
browser's `window.postMessage` API, using ESA Sky's official scripting
interface.  Two commands are used:

| Command | Purpose |
|---------|---------|
| `goToRaDec` | Pan the ESA Sky view to a given RA/Dec centre |
| `setFov` | Set the field of view (degrees) |

A clientside JS bridge in `callbacks/ui_callbacks.py` watches
`esasky-overlay-data-store` and fires these commands as soon as the store is
populated.  The bridge also calls ESA Sky's catalog overlay API to draw
cluster, CATRED, and HEALPix mask tile centroid markers on top of the sky
imagery.

### Catalog overlay support

When `view-mode-store` changes to `"esasky"` the server-side callback
`ESASkyCallbacks.push_overlay_data` (defined in
`callbacks/esasky_callbacks.py`) builds an overlay payload and writes it to
`esasky-overlay-data-store`.  The payload contains:

- **`clusters`** — all merged-catalog entries for the selected algorithm, each
  with `ra`, `dec`, `name` (cluster ID), `SNR`, and `Z` fields.
- **`catred`** — CATRED source positions (`ra`, `dec`) currently loaded in the
  sidebar.
- **`mask`** — centroid RA/Dec for each HEALPix mask tile cached in
  `mosaic_handler.traces_cache`.
- **`viewport`** — RA/Dec centre and FOV derived from the current Plotly figure
  axes, used to position the ESA Sky camera on first load.

The payload format is plain JSON so that the clientside JS bridge can pass it
to ESA Sky without a server round-trip for subsequent interactions.

### Interaction model

ESA Sky runs entirely inside its iframe.  All pan, zoom, and source inspection
are handled by the ESA Sky application's own UI.  The Dash app does **not**
receive click or selection events back from the iframe — there is no
`postMessage` return channel.  If you need to act on a source selected in ESA
Sky you must note its coordinates and re-enter them in the Dash sidebar.

### When to use each view mode

| Situation | Recommended mode |
|-----------|-----------------|
| Exploring the full cluster catalogue across the survey area | Standard Plotly (default) |
| Inspecting a single cluster's immediate neighbourhood with interactive sky tiles | Aladin Lite (requires exactly 1 cluster in viewport) |
| Cross-referencing cluster positions against the broader ESA multi-wavelength archive | ESA Sky |
| Overlaying a locally-stored MER FITS mosaic or HEALPix mask | Standard Plotly + mosaic controls |

### Cross-reference

For a full description of view mode switching, how `view-mode-store` controls
panel visibility, and the Aladin Lite integration, see
[USAGE.md](USAGE.md#using-esa-sky-view).
