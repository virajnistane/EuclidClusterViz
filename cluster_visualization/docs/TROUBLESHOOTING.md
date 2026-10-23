# Troubleshooting Guide

## Port Conflicts

### `bind [127.0.0.1]:8050: Address already in use` — local machine

**Cause**: Previous SSH tunnel still holds port 8050 on your local machine.

**Fix**:
```bash
# Kill the stale tunnel:
lsof -ti :8050 | xargs kill -9 2>/dev/null; true
# Then retry your ssh -L command:
ssh -L 8050:localhost:<YOUR_PORT> username@remote-server.domain
```

---

### `8184 address already in use` / app falls back to port `9184` — remote node

**Cause**: Orphaned ClusterViz process from a previous session still listening on your UID port.

**Auto-fix**: The app automatically detects and kills its own stale process before binding. Simply relaunch:
```bash
./launch.sh
```

**Manual fix** (if auto-kill failed):
```bash
# Find your UID port:
python3 -c "import os; print(8050 + os.getuid() % 1000)"
# Kill the stale process (replace 8184 with your port):
lsof -ti :8184 -sTCP:LISTEN | xargs kill -9 2>/dev/null; true
# Relaunch:
./launch.sh
```

---

### App started on fallback port (e.g. `9184`) but tunnel points to `8184`

**Cause**: Primary UID port was held by another user's process (can't be auto-killed), so the app fell back.

**Fix**:
1. Check the port printed in the startup box
2. Kill old local tunnel: `lsof -ti :8050 | xargs kill -9 2>/dev/null; true`
3. Open new tunnel with the correct port: `ssh -L 8050:localhost:9184 username@host`

---

## SSH / Connection Issues

### No browser connection after tunneling

- Verify tunnel is open: `lsof -i :8050` on local machine should show an SSH process
- Check app is running on remote: `lsof -i :<YOUR_PORT> -sTCP:LISTEN` on remote node
- Browser URL must be `http://localhost:8050` — not the remote hostname

### Already logged in without `-L`

Open a **new terminal** on your local machine and run the tunnel command printed at startup — no need to disconnect your existing session.

### Warning: "No users have connected yet" after 1 minute

The app prints this if no browser has connected. Run the `ssh -L` command shown in the startup box, then open `http://localhost:8050`.

---

## Environment & Dependencies

### Terminal output: more or less detail

Log lines show time, level and module. The default level is INFO; debug
messages are hidden.

```bash
./launch.sh --log-level DEBUG          # everything, including per-render details
CLUSTERVIZ_LOG_LEVEL=WARNING ./launch.sh   # only warnings and errors
```

Where the level comes from, first match wins:

1. `--log-level` on `./launch.sh` (or `make run ARGS="--log-level DEBUG"`)
2. the `CLUSTERVIZ_LOG_LEVEL` environment variable
3. `level` in the `[logging]` section of the config file
4. INFO

While the app runs, **Configuration > Terminal log level** in the sidebar changes
it at once (not saved to the config file; a background task already running keeps
its level until it ends). The startup box with the SSH command is always printed,
whatever the level.

At INFO the terminal shows one line per action (data loaded, cluster clicked,
mosaic/mask overlay or cutout made, CATRED loaded). Timings that run on every
pan or zoom (`Patch [...]`, `Globe [...]`) and the profiler table are DEBUG lines.

### Missing packages at startup

Launches re-sync `.venv` automatically when `uv.lock` or `pyproject.toml`
changed (`setup_venv.sh --if-stale`). If packages are still missing:

```bash
cd ~/ClusterViz
./setup_venv.sh              # update .venv
./setup_venv.sh --recreate   # or: make rebuild — delete .venv and rebuild it
```

If the launcher prints "Environment up to date" but a package is broken, the
stamp is stale: `--recreate` rebuilds regardless. `CLUSTERVIZ_NO_AUTOSYNC=1`
disables the automatic check.

### Python environment not found or too old

```bash
./setup_venv.sh   # rebuilds .venv when it is missing or older than Python 3.14
```

### pytest / sphinx disappeared after an update

Extras are remembered in `.venv/.clusterviz-sync`; if they were installed with
an older `setup_venv.sh`, add them once more: `./setup_venv.sh --dev --docs`.

The launcher uses the project `.venv` managed by `uv`; EDEN-3.1 activation is not required.

### Verify installed packages

```bash
source .venv/bin/activate
pip show cluster-visualization dash plotly healpy
```

---

## Data / Configuration

### App loads but shows no clusters

Check data paths in your config:
```bash
python3 -c "from cluster_visualization.src.config import get_config; c = get_config(); print(c)"
```
Verify paths under `[paths]` exist on the remote node.

### Wrong config loading

Use `--config` to specify explicitly:
```bash
./launch.sh --config /path/to/my_config.ini
```

Priority order: `--config` arg → `config_local.ini` → `config.ini`.

---

## Performance

### Slow first render

Normal — data loading (~30s for large catalogs). Later starts read the catalogs
from the Parquet disk cache (see [DISK_CACHING_IMPLEMENTATION.md](DISK_CACHING_IMPLEMENTATION.md)).
If no `~/.cache/clusterviz/*.parquet` files appear, pyarrow is missing from the
environment (`python -c "import pyarrow"`); the app then caches as pickle.

### Slow cold start on the cluster (imports take a minute)

On a node whose page cache is cold, the venv and stdlib are read file by file from
network storage (Ceph), because Python imports one file at a time.

- `setup_venv.sh` writes `.venv/.clusterviz-prefetch` after each sync: the exact
  files the app loads (`.pyc`, extension modules and the shared libraries they
  use, including healpy/scipy/pyarrow used later), in import order.
- The launcher reads that list with parallel readers **in the background** while
  the app starts; it never waits for them.
- Refresh the list after large code changes: `./setup_venv.sh --manifest`.
- Turn it off with `CLUSTERVIZ_NO_PREFETCH=1`; change the number of readers with
  `CLUSTERVIZ_PREFETCH_JOBS` (default 16).

To compare, start once with and once without the prefetch on a cold node and read
the app's own `Imports done in …` and `App initialized …` lines.

### Sky map is slow or shows a density map instead of clusters

Large catalogs are culled to the view and replaced by a density map when the
visible area holds more than `density_threshold` clusters; zoom in to get
markers. Tune `[view]` in `config.ini` (see
[VIEWPORT_OPTIMIZATION.md](VIEWPORT_OPTIMIZATION.md)).

### CATRED render button stays disabled

Zoom in until the viewport is smaller than 2°×2° in both RA and Dec.

---

## Browser Errors

### `IndexError: list index out of range` at `inputs_state[ind]` after an update

**Symptom**: a button (e.g. Generate mask cutout) fails and the server log ends
in Dash's `dispatch` with `inputs_state[ind]` → `IndexError`.

**Cause**: the browser tab was opened before the server was restarted with new
code. Dash loads each callback's list of inputs once, when the page loads; a stale
tab sends the old, shorter list.

**Fix**: hard-reload the page (Ctrl+Shift+R / Cmd+Shift+R) after every server
update.

### `Name or service not known` when the server binds its port

Conda environments export `HOST=x86_64-conda-linux-gnu`, and Dash ≥ 2.16 lets the
`HOST`/`PORT` environment variables override the bind address. The app now pins
`HOST`/`PORT` to the chosen values; if you launch Dash code of your own, unset
`HOST` first.

---

## Aladin Lite Viewer

### Skeleton shimmer stays visible — Aladin viewer never appears

**Symptom**: After switching to "Aladin" view mode the animated skeleton overlay
(`aladin-skeleton`) keeps spinning and the sky map never loads.

**Cause**: Aladin Lite v3 is loaded on-demand from a CDN.  On a compute node with
no outbound internet access the CDN request times out or is blocked by a firewall,
so the JS bundle never executes and the viewer is never initialised.

**Fix**:
1. Check outbound network connectivity from the node:
   ```bash
   curl -I --max-time 10 https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js
   ```
2. If the node is air-gapped, host the Aladin Lite bundle locally and update the
   CDN `<script>` tag in `cluster_visualization/ui/aladin_view.py` to point to
   the local path.
3. Confirm the browser console shows no JavaScript errors (open DevTools → Console
   and reload the page after switching to Aladin mode).

---

### Server log shows `[Aladin] Warning: Could not load cluster data` or CATRED entries are missing

**Cause**: The `push_overlay_data` callback in `aladin_callbacks.py` caught an
exception while building the overlay JSON.

**Fix**: Check the server log for the full traceback printed after the warning.
Common sub-causes: missing `SNR_CLUSTER` / `Z_CLUSTER` columns in the merged
catalog, or the diskcache directory (`~/.cache/clusterviz_state`) not writable.

---

## ESA Sky Iframe

### Blank iframe — no map loads in ESA Sky mode

**Symptom**: After switching to "ESA Sky" view mode the iframe remains blank or
shows a loading spinner indefinitely.

**Cause**: The clientside JS bridge communicates with the ESA Sky iframe via
`postMessage`.  If the iframe cannot load `esasky.esac.esa.int` (e.g. a firewall
blocks the domain or the iframe `src` URL times out), or if the `postMessage`
handshake times out before the iframe is ready, the overlay is never applied and
the sky view stays blank.

**Fix**:
1. Open your browser's Developer Tools (F12) → Console tab.  Look for
   `postMessage` timeout errors or `Content Security Policy` / CORS errors.
2. Verify the node can reach ESA Sky:
   ```bash
   curl -I --max-time 15 https://esasky.esac.esa.int
   ```
3. If the domain is blocked, contact your site administrator to allow outbound
   HTTPS to `esasky.esac.esa.int`.

---

### ESA Sky overlay data (clusters / CATRED) not shown

**Cause**: The `push_overlay_data` callback in `esasky_callbacks.py` caught an
exception while serialising catalog or CATRED data.

**Fix**: Check the server log for `[ESASky] Warning:` messages.  Re-render CATRED
(zoom in below 2°×2° and click the CATRED button) before switching to ESA Sky mode
to ensure `current_catred_data` is populated.

---

## Mosaic (MER / ESA) Source

### Mosaic not loading after upgrade — `local_fits` default fails silently

**Symptom**: After upgrading ClusterViz the mosaic panel stays empty or the server
log shows `[ERROR] paths.mosaic_dir is not configured` / `Warning: No mosaic FITS
file found for MER tile <id>`.

**Cause**: The default mosaic provider was changed to `local_fits` (previously the
default may have been different).  The `local_fits` path requires:
- `paths.mosaic_dir` configured in your `config.ini` / `config_local.ini`
- FITS tiles matching the pattern
  `EUC_MER_BGSUB-MOSAIC-VIS_TILE<id>*.fits.gz` present in that directory

If the directory is missing or empty, `_load_local_mosaic_fits_data` in
`mermosaic.py` returns `None` and no image trace is created.

**Fix**:
1. Verify the configured mosaic directory:
   ```bash
   python3 -c "from cluster_visualization.src.config import get_config; c = get_config(); print(c.mosaic_dir)"
   ```
2. Check that FITS tiles are present:
   ```bash
   ls <mosaic_dir>/EUC_MER_BGSUB-MOSAIC-VIS_TILE*.fits.gz | head
   ```
3. If local FITS tiles are unavailable, switch the provider to `esa_sky` using the
   radio selector in the mosaic panel — ESA sky cutouts will be fetched from the
   configured `esa_cutout_base_url` endpoint instead.
4. To set `esa_sky` as the persistent default, add to your `config_local.ini`:
   ```ini
   [mosaic]
   mosaic_provider_default = esa_sky
   ```

---

## Galaxy Catalogs

See [GALAXY_CATALOGS_GUIDE.md](GALAXY_CATALOGS_GUIDE.md) for how catalogs work.

### "file not found" or "file not readable" when reading columns

The path is read on the cluster, by the app's account. Check it there
(`ls -l /path/to/catalog.fits`). Inside the Apptainer image only bound folders exist:
`launch_sif.sh` binds `/sps` and your home; add others with
`CLUSTERVIZ_BIND=/path/to/catalogs ./launch_sif.sh`.

### A catalog takes long to appear the first time

The first time a catalog is shown, its mapped columns are read from the file; a
FITS table is read in full (about 1.5 minutes for the 617 MB Euclid catalogue over
sshfs). Later loads come from `~/.cache/clusterviz_catalogs/` and are immediate.
Changing the mapping or the file starts a new cache entry; that folder can be
deleted at any time.

### Only part of a large catalog is drawn

Catalogs above 10,000 rows are drawn around the current view and thinned to
10,000 points there; the legend says "(10,000 of N here)". Zoom in to see all
galaxies in an area. This is deliberate: the full catalog would slow every plot
update over the SSH tunnel.

### "none of N OBJECT_IDs found in CATRED"

The catalog's OBJECT_IDs are not in the CATRED tiles of that area: the catalog
may come from another data release than the configured CATRED, or the mapped
column is not the MER OBJECT_ID. Remove the OBJECT_ID mapping (pen icon) to
match by position instead.

### "Load CATRED near shown catalogs" stays disabled

Render the clusters first and zoom in to under 2° × 2°, as for the CATRED render
button.

### The Spec-z verification filter is greyed out

It lists only catalogs with a merged cluster ID column mapped (the "Merged
cluster ID" line in the Add/Edit dialog). A catalog whose file can't be loaded is
listed as unavailable.

---

## Getting Help

- Check server log output for error messages
- Log file when using background launch: `/tmp/clusterviz_<username>.log`
- See [README](https://github.com/virajnistane/EuclidClusterViz/blob/main/README.md) for full setup instructions
