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

### Missing packages at startup

```bash
cd ~/ClusterViz
./setup_venv.sh       # recreates .venv with all dependencies
```

### EDEN environment not detected

```bash
source /cvmfs/euclid-dev.in2p3.fr/EDEN-3.1/bin/activate
# or use the venv launcher which handles this automatically:
./launch.sh
```

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

Normal — data loading (~30s for large catalogs). Subsequent renders use disk cache (~5–10x faster).

### CATRED render button stays disabled

Zoom in until the viewport is smaller than 2°×2° in both RA and Dec.

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

## Getting Help

- Check server log output for error messages
- Log file when using background launch: `/tmp/clusterviz_<username>.log`
- See [README](https://github.com/virajnistane/EuclidClusterViz/blob/main/README.md) for full setup instructions
