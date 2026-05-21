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

## Getting Help

- Check server log output for error messages
- Log file when using background launch: `/tmp/clusterviz_<username>.log`
- See [README](../../../README.md) for full setup instructions
