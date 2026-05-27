# Mosaic Rendering Upgrade: `go.Heatmap` to `layout.images` PNG Bitmap

## Overview

Mosaic tile rendering was upgraded from Plotly `go.Heatmap` (serializing a raw float32 NumPy array into the figure JSON) to `layout.images` (encoding each tile as a grayscale PNG and embedding it as a base64 data URI). The change was landed in commit `8cb4551` and is implemented across two files:

- `cluster_visualization/src/mermosaic.py` — `create_mosaic_image_trace` now returns a `dict` (layout image spec) instead of `go.Heatmap`.
- `cluster_visualization/callbacks/mosaic_callback.py` — the render callback injects into `layout["images"]` instead of `figure["data"]`; visibility toggle, opacity, and delete controls operate on `layout.images` by the `"name"` prefix `"Mosaic"`.

## Why the Change

### Payload size

A single full-resolution MER tile downscaled to `1920 × 1920` pixels of `float32` data is roughly **14 MB** as a JSON array. The same tile encoded as an 8-bit grayscale PNG is **150–400 KB** — a 35–90× reduction. The comment in `create_mosaic_image_trace` documents this explicitly:

```python
# Returns a dict suitable for fig.layout.images rather than a go.Heatmap trace.
# This avoids serializing large float32 arrays (~14 MB per tile) — a PNG-encoded
# grayscale image is ~150–400 KB, giving a 35–90× payload reduction.
```

### WebGL / SVG layer conflict

`go.Heatmap` renders in the SVG layer by default. When other traces (cluster scatter, CATRED polygons) use WebGL, mixing SVG heatmap tiles with WebGL traces causes z-ordering problems and browser-specific rendering artefacts. `layout.images` are composited directly by Plotly's layout engine, independent of the trace rendering layer, and the `"layer": "below"` property places them behind all data traces without any WebGL interaction.

### Interactivity trade-off

The upgrade sacrifices per-pixel hover data (`RA`, `Dec`, `Intensity` fields from the old `hovertemplate`) because `layout.images` do not emit hover events. The commented-out legacy `go.Heatmap` block kept at the bottom of `create_mosaic_image_trace` records the original hover fields for reference. The mosaic cutout view (`create_mosaic_cutout_trace`) retains `go.Heatmap` because cutouts are small (capped at `512 × 512`) and hover data is useful at that scale.

## Why `heatmapgl` Was Attempted but Reverted (commit `0c6bd21`)

Before the PNG path was chosen, commit `0c6bd21` ("attempt to use heatmapgl, failed; minor changes in heatmap mosaic") tried switching the trace type from `go.Heatmap` to `go.Heatmapgl`. The diff shows the function was renamed internally to reference `heatmapgl` but the returned object remained a `go.Heatmap` constructor call — the attempt never fully switched the type. The payload problem remained (float32 data was still serialised in full), and `go.Heatmapgl` has known incompatibilities with `autorange="reversed"` axes used for the RA axis, causing the image to be mirrored or misaligned. The commit was immediately followed by `8cb4551` which abandoned the heatmap family entirely in favour of the bitmap path.

## Default Mosaic Source Change: `esa_sky` → `local_fits`

Prior to commit `184d36a`, the `mosaic-provider-selector` dropdown in `data_controls.py` defaulted to `value="esa_sky"`. The commit changed the default to `value="local_fits"`.

**What `local_fits` means.** The `local_fits` provider reads compressed `EUC_MER_BGSUB-MOSAIC-VIS_TILE{mertileid}*.fits.gz` files from the configured `paths.mosaic_dir`. These are the Euclid MER background-subtracted VIS mosaic products (`DpdMerBksMosaic`) stored on the cluster filesystem. The loading path is `_load_local_mosaic_fits_data` in `mermosaic.py`, which opens the FITS primary HDU, copies the 32-bit float data, and extracts the WCS header. No network request is made.

**Why it is now the default.** The `esa_sky` provider fetches JPEG or FITS cutouts from the CDS `hips2fits` public endpoint over HTTP. This requires an active internet connection from the compute node where the Dash server runs, is subject to network latency and rate limits, and produces lower-resolution cutouts (768 × 768 pixels) compared to the full MER tile. The local FITS files are always available in the project data directory and carry the actual Euclid VIS science data. Switching the default to `local_fits` avoids network calls on first load and surfaces the Euclid data immediately.

The `esa_sky` provider remains fully functional and can be selected from the UI. When selected, a secondary `mosaic-esa-format-selector` dropdown (shown by a clientside callback) lets the user choose between `fits` (32-bit, WCS-derived bounds) and `jpg` (8-bit, geometric bounds).

The `MOSAICHandler.__init__` also sets `self.default_mosaic_provider = "local_fits"` (overridable via `config.get_mosaic_provider_default()`), making `local_fits` the programmatic default as well.

## Opacity Controls: What Moved Serverside vs. Clientside

**Mosaic opacity** is fully clientside. The `_setup_mosaic_opacity_callback` method registers a `clientside_callback` that reads `mosaic-opacity-slider` and iterates over `figure.layout.images`, setting `img.opacity` on every entry whose `name` starts with `"Mosaic"`. It also updates `img._storedOpacity` so that the visibility toggle can restore the last-set opacity when re-showing a hidden tile.

**Mask opacity** is also clientside via `_setup_mask_opacity_callback`, which iterates over `figure.data` traces whose `name` starts with `"Mask overlay"` or equals `"Mask Colorbar"`.

The render-time opacity passed to `create_mosaic_image_trace` (from `mosaic-opacity-slider` at button-click time) sets the initial `"opacity"` field in the layout image spec returned by the server. All subsequent live adjustments happen without a round-trip by mutating the figure JSON in the browser.

## Updated Rendering Pipeline

The full path from source data to a visible mosaic tile is:

1. **User zooms in** on the Plotly scatter map to a region narrower than 2° × 2°. A clientside callback enables the "Load Mosaic in Zoom" button (`mosaic-render-button`).

2. **User clicks "Load Mosaic in Zoom"**. The `render_mosaic_images` background callback fires with the current `relayoutData` (axis ranges), selected `mosaic-provider-selector` value, `mosaic-source-selector` value, and slider opacity.

3. **Tile intersection** (`load_mosaic_traces_in_zoom`). The zoom bounds are extracted from `relayoutData`. `_find_intersecting_tiles` tests each MER tile's Shapely polygon against the zoom box. Up to 5 intersecting tiles are selected; processing stops after 30 seconds.

4. **Data load** (per tile). For `local_fits`: `_load_local_mosaic_fits_data` opens the `.fits.gz` file in a daemon thread with a 10-minute timeout, reads the primary HDU `data` array and WCS header. For `esa_sky`: `_load_esa_cutout_by_mertile` fetches a cutout URL from `hips2fits` and parses the FITS or JPEG response.

5. **Image processing** (`_process_mosaic_image`, local FITS path only). The float32 array is:
   - Early-downsampled if the source is more than 4× larger than the target in either dimension.
   - Percentile-normalised with a robust 1st–99.5th stretch (`_percentile_normalize`), including IQR fencing to reject extreme outlier pixels.
   - Resized to `(img_scale_factor × original)` (default `0.1`) using PIL LANCZOS. For a native Euclid MER VIS tile (~19200 × 19200 px) this yields ~1920 × 1920 px. The `img_width`/`img_height` instance attributes (also initialised to 1920) track the last rendered size but do not cap it — the actual output dimensions are always `int(native_size × scale_factor)`.
   - Flipped left-right (FLIP_LEFT_RIGHT) so that column 0 = minimum RA.
   ESA cutouts are already normalised inside `_load_esa_cutout_by_mertile` and skip this step.

6. **Coordinate bounds** (`_calculate_image_bounds_direct`). The processed image corners are mapped back to RA/Dec using the scaled WCS to produce `ra_min`, `ra_max`, `dec_min`, `dec_max`.

7. **PNG encoding** (`create_mosaic_image_trace`). The processed array is double-flipped (`[::-1, ::-1]`) to put row 0 at `dec_max` and column 0 at `ra_max`, matching the `layout.images` anchor convention. Values are scaled to 0–255 uint8, saved as a grayscale PNG with `compress_level=6`, and base64-encoded into a `data:image/png;base64,...` URI.

8. **Layout image spec** returned as a `dict` with fields `source`, `xref="x"`, `yref="y"`, `x=ra_max`, `y=dec_max`, `sizex`, `sizey`, `sizing="stretch"`, `opacity`, `layer="below"`, and `name` prefixed with `"Mosaic"`.

9. **Injection into figure**. The callback sets `figure["layout"]["images"]`, replacing any existing entries whose `name` starts with `"Mosaic"` and appending the new specs.

10. **Live adjustments** (clientside). The opacity slider, visibility toggle, and delete button all operate on `figure.layout.images` in the browser without server round-trips.

## Image Source Radio Selector: Mosaic vs. Aladin

The `image-source-radio` component in `data_controls.py` (`create_mosaic_controls_section`) presents two options:

| Radio value | Label | Initial state |
|-------------|-------|---------------|
| `"mosaic"` | MER Mosaic | enabled (default) |
| `"aladin"` | Aladin Sky | disabled until exactly 1 cluster is visible in viewport |

The `"aladin"` option starts with `"disabled": True` in the static Python layout, but a clientside callback in `ui_callbacks.py` dynamically updates the options list on every zoom/pan event: it counts cluster points inside the current viewport and sets `disabled: count !== 1`. The Aladin view is therefore only reachable when the user has zoomed in to exactly one cluster.

When `"mosaic"` is selected, the `mer-mosaic-controls` `html.Div` is shown. This container holds the mosaic enable switch, opacity slider, provider/source dropdowns, and "Load Mosaic in Zoom" button. The MER pipeline (steps 1–10 above) is used.

When `"aladin"` is selected, the radio value triggers a `view-mode-store` update (via a separate clientside callback: `radioVal === 'aladin' → 'aladin'`), which in turn hides the Plotly map container, shows the Aladin Lite container, and hides `mer-mosaic-controls`. The `aladin-survey-dropdown` becomes visible. The dropdown lists surveys such as `P/DSS2/color`, `CDS/P/Euclid/Q1/VIS`, `CDS/P/Euclid/Q1/NIR`, `P/2MASS/H`, and `P/allWISE/color`. The Aladin Lite widget renders the selected survey as a background layer using its own internal HiPS tile protocol, completely independent of the Plotly `layout.images` pipeline described above.

The radio and the `view-mode-store` are kept in sync bidirectionally: the view-mode toggle buttons also write to `view-mode-store`, which then updates the radio value back to `"mosaic"` or `"aladin"` to reflect the current mode.
