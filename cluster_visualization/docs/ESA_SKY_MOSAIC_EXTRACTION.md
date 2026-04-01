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
