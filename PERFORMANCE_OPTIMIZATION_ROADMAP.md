# Performance Optimization Strategies for Scaling Visualization

This document outlines comprehensive strategies to speed up the ClusterViz app as data volume increases.

---

## 1. **Data Loading & Caching Optimization**

### Current State
Your `DataLoader` already has basic caching, but it can be improved:

### Recommendations

**A. Lazy Loading with Memory-Mapped Files**
```python
# Instead of loading entire FITS files into memory
with fits.open(fitsfile, mode='readonly', memmap=True) as hdul:
    # Access only needed columns/rows
    tile_data = hdul[1].data[['RA_CLUSTER', 'DEC_CLUSTER', 'SNR_CLUSTER', 'Z_CLUSTER']]
```

**B. Pre-filter Data at Load Time**
```python
def load_data(self, select_algorithm: str = 'PZWAV', 
              snr_min: float = None, z_range: tuple = None) -> Dict[str, Any]:
    """Load with optional pre-filtering to reduce memory footprint."""
    
    # Load merged catalog
    data_merged = self._load_fits_filtered(
        fitsfile, 
        snr_range=(snr_min, None),
        z_range=z_range
    )
```

**C. Use HDF5 Instead of FITS for Large Catalogs**
```python
# Convert FITS to HDF5 once (much faster I/O)
import h5py

def convert_fits_to_hdf5(fits_path, hdf5_path):
    """One-time conversion for faster subsequent loads."""
    with fits.open(fits_path) as hdul:
        data = hdul[1].data
    
    with h5py.File(hdf5_path, 'w') as f:
        for col in data.columns.names:
            f.create_dataset(col, data=data[col], compression='gzip')
```

**D. Implement Multi-Level Caching**
```python
class DataLoader:
    def __init__(self, config=None):
        self.memory_cache = {}      # Hot data in RAM
        self.disk_cache_dir = '/tmp/clusterviz_cache'  # Warm data on disk
        
    def load_with_disk_cache(self, key, loader_func):
        """Check RAM → Disk → Load from source."""
        # Check memory first
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Check disk cache
        cache_file = os.path.join(self.disk_cache_dir, f"{key}.pkl")
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
            self.memory_cache[key] = data
            return data
        
        # Load from source and cache
        data = loader_func()
        self._cache_to_disk(key, data)
        self.memory_cache[key] = data
        return data
```

---

## 2. **Spatial Indexing for Fast Queries**

### Problem
Your proximity checks and spatial filtering are currently O(N) operations.

### Solution: Use Spatial Index

```python
from scipy.spatial import cKDTree
import numpy as np

class SpatialIndex:
    """Fast spatial queries for astronomical data."""
    
    def __init__(self, ra, dec):
        """Build KD-tree for RA/Dec coordinates."""
        # Convert to radians for proper spherical distance
        self.ra = np.radians(ra)
        self.dec = np.radians(dec)
        
        # Convert to 3D Cartesian coordinates
        x = np.cos(self.dec) * np.cos(self.ra)
        y = np.cos(self.dec) * np.sin(self.ra)
        z = np.sin(self.dec)
        self.coords = np.column_stack([x, y, z])
        
        # Build KD-tree
        self.tree = cKDTree(self.coords)
    
    def query_radius(self, ra_center, dec_center, radius_deg):
        """Find all points within radius (in degrees) of center.
        
        Returns indices of matching points - O(log N) instead of O(N)!
        """
        # Convert query point to Cartesian
        ra_rad = np.radians(ra_center)
        dec_rad = np.radians(dec_center)
        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)
        
        # Convert angular radius to chord distance
        chord_dist = 2 * np.sin(np.radians(radius_deg) / 2)
        
        # Query tree
        indices = self.tree.query_ball_point([x, y, z], chord_dist)
        return indices
    
    def query_box(self, ra_min, ra_max, dec_min, dec_max):
        """Find all points in RA/Dec box - much faster than filtering arrays."""
        mask = ((self.ra >= np.radians(ra_min)) & 
                (self.ra <= np.radians(ra_max)) &
                (self.dec >= np.radians(dec_min)) & 
                (self.dec <= np.radians(dec_max)))
        return np.where(mask)[0]
```

**Usage in your app:**
```python
# In TraceCreator.__init__ or DataLoader
self.cluster_index = SpatialIndex(
    data['data_detcluster_mergedcat']['RA_CLUSTER'],
    data['data_detcluster_mergedcat']['DEC_CLUSTER']
)

# In proximity-based enhancement (currently O(N))
def _enhance_markers_near_catred(self, ...):
    for catred_point in catred_sample:
        # OLD: Loop through ALL clusters - O(N * M)
        # NEW: Query only nearby clusters - O(log N)
        nearby_indices = self.cluster_index.query_radius(
            catred_point['ra'], catred_point['dec'], 
            radius_deg=0.1  # 6 arcmin
        )
        enhanced_mask[nearby_indices] = True
```

---

## 3. **Optimize Trace Generation**

### Current Bottlenecks
Your `TraceCreator` generates many individual traces.

### Solutions

**A. Batch Trace Creation**
```python
def _create_tile_traces_batch(self, tiles_dict, show_mer_tiles):
    """Create traces for multiple tiles in one go."""
    
    # Collect all polygon coordinates first
    all_lev1_x, all_lev1_y = [], []
    all_core_x, all_core_y = [], []
    trace_names = []
    
    for tileid, tile_value in tiles_dict.items():
        # Extract polygon data
        lev1_polygon = tile['LEV1']['POLYGON'][0]
        lev1_x = [p[0] for p in lev1_polygon] + [lev1_polygon[0][0]]
        lev1_y = [p[1] for p in lev1_polygon] + [lev1_polygon[0][1]]
        
        # Separate polygons with NaN
        all_lev1_x.extend(lev1_x + [np.nan])
        all_lev1_y.extend(lev1_y + [np.nan])
        trace_names.append(tileid)
    
    # Create ONE trace for all LEV1 polygons
    lev1_trace = go.Scatter(
        x=all_lev1_x,
        y=all_lev1_y,
        mode='lines',
        line=dict(color='red', width=2, dash='dash'),
        name='All LEV1 Boundaries',
        hovertemplate='Tile: ' + '<br>'.join(trace_names)
    )
    
    return [lev1_trace]  # 1 trace instead of N traces
```

**B. Use Scattergl for Large Point Clouds**
Already doing this - good! But ensure all large datasets use it:
```python
# For CATRED data (already using Scattergl)
catred_trace = go.Scattergl(...)  # ✓ Good

# For cluster data - check if using Scatter or Scattergl
cluster_trace = go.Scattergl(...)  # Should be Scattergl for >10k points
```

**C. Downsample Intelligently**
```python
def adaptive_downsample(data, zoom_level, max_points=10000):
    """Downsample based on current zoom level."""
    if len(data) <= max_points:
        return data
    
    if zoom_level == 'full':
        # Aggressive downsampling for full sky view
        step = len(data) // 5000
        return data[::step]
    elif zoom_level == 'medium':
        # Moderate downsampling
        step = len(data) // max_points
        return data[::step]
    else:
        # No downsampling when zoomed in
        return data
```

---

## 4. **Clientside Callbacks for Filtering**

### Move Heavy Lifting to Browser

**Current:** Python callbacks filter data server-side → serialize → send to browser

**Better:** Send all data once, filter in JavaScript

```javascript
// In layout.py - add clientside callback for SNR filtering
app.clientside_callback(
    """
    function(snr_range, figure) {
        if (!figure || !figure.data) return figure;
        
        // Filter traces in browser - no server round-trip!
        figure.data = figure.data.map(trace => {
            if (trace.name && trace.name.includes('Cluster')) {
                // Filter points by SNR in customdata
                const filtered_indices = trace.customdata
                    .map((snr, i) => snr >= snr_range[0] && snr <= snr_range[1] ? i : -1)
                    .filter(i => i >= 0);
                
                return {
                    ...trace,
                    x: filtered_indices.map(i => trace.x[i]),
                    y: filtered_indices.map(i => trace.y[i]),
                    customdata: filtered_indices.map(i => trace.customdata[i])
                };
            }
            return trace;
        });
        
        return figure;
    }
    """,
    Output('cluster-plot', 'figure'),
    Input('snr-slider', 'value'),
    State('cluster-plot', 'figure')
)
```

---

## 5. **Database Backend for Very Large Datasets**

### When to Consider This
If your catalogs exceed ~1M clusters, consider a database:

```python
import sqlite3
from contextlib import contextmanager

class ClusterDatabase:
    """SQLite backend for massive catalogs."""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_tables()
        self._create_spatial_index()
    
    def _create_tables(self):
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY,
                    ra REAL,
                    dec REAL,
                    z REAL,
                    snr REAL,
                    tileid TEXT,
                    algorithm TEXT,
                    INDEXED (ra, dec, snr, z)
                )
            """)
    
    def query_spatial_box(self, ra_range, dec_range, snr_range, z_range):
        """Fast indexed query for visible region."""
        query = """
            SELECT ra, dec, z, snr, tileid 
            FROM clusters 
            WHERE ra BETWEEN ? AND ?
              AND dec BETWEEN ? AND ?
              AND snr BETWEEN ? AND ?
              AND z BETWEEN ? AND ?
            LIMIT 50000
        """
        with self.connection() as conn:
            return pd.read_sql_query(
                query, conn,
                params=(*ra_range, *dec_range, *snr_range, *z_range)
            )
    
    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
```

---

## 6. **Optimize HEALPix Mask Rendering**

### Your Current Issue
Mask overlays zoom out and render slowly.

### Solutions Already Discussed
- ✓ Rasterization approach (you added this)
- ✓ Colorbar visibility fix (resolved)

### Additional Optimization

**Pre-compute Mask for Common Zoom Levels:**
```python
class MaskCache:
    """Cache rasterized masks at different resolutions."""
    
    def __init__(self):
        self.cache = {}  # {(tileid, resolution): rasterized_mask}
    
    def get_or_create(self, tileid, resolution, generator_func):
        key = (tileid, resolution)
        if key not in self.cache:
            self.cache[key] = generator_func(tileid, resolution)
        return self.cache[key]
```

---

## 7. **Implement Progressive Loading**

### Show Something Fast, Then Refine

```python
@app.callback(
    Output('cluster-plot', 'figure'),
    Input('load-button', 'n_clicks'),
    background=True,  # Dash 2.x long callback
    running=[
        (Output('load-button', 'disabled'), True, False),
        (Output('loading-indicator', 'children'), 'Loading...', '')
    ]
)
def progressive_load(n_clicks):
    if not n_clicks:
        return no_update
    
    # Stage 1: Show low-res version immediately
    quick_data = load_downsampled_data(factor=10)
    yield create_figure(quick_data)
    
    # Stage 2: Load full resolution in background
    full_data = load_full_data()
    yield create_figure(full_data)
```

---

## 8. **Memory Management**

### Monitor and Limit Memory Usage

```python
import psutil
import gc

class MemoryManager:
    """Monitor and control app memory usage."""
    
    def __init__(self, max_memory_gb=8):
        self.max_memory_bytes = max_memory_gb * 1024**3
    
    def check_memory(self):
        """Get current memory usage."""
        process = psutil.Process()
        return process.memory_info().rss
    
    def cleanup_if_needed(self, cache_dict):
        """Clear cache if memory exceeds limit."""
        if self.check_memory() > self.max_memory_bytes:
            print("Memory limit exceeded - clearing cache")
            cache_dict.clear()
            gc.collect()
            return True
        return False
```

---

## 9. **Specific Recommendations for Your App**

### Priority 1 (Highest Impact)
1. **Add spatial indexing** for proximity checks (KD-tree)
   - Affects: CATRED proximity enhancement, cutout generation
   - Speedup: 10-100x for spatial queries

2. **Implement disk caching** for processed data
   - Affects: App startup time, algorithm switching
   - Speedup: 5-10x for repeated loads

3. **Use HDF5** instead of FITS for large catalogs
   - Affects: Data loading time
   - Speedup: 3-5x for I/O operations

### Priority 2 (Medium Impact)
4. **Batch polygon traces** into fewer traces
   - Affects: Rendering performance with many tiles
   - Speedup: 2-3x for polygon rendering

5. **Move filtering to clientside** callbacks
   - Affects: SNR/redshift slider responsiveness
   - Speedup: Instant filtering (no server round-trip)

6. **Memory-map FITS files** instead of loading entirely
   - Affects: Memory usage, startup time
   - Benefit: Constant memory regardless of data size

### Priority 3 (Future-Proofing)
7. **Database backend** for 1M+ clusters
   - Affects: Scalability to very large surveys
   - When: If catalog exceeds ~500k clusters

8. **Progressive loading** for better UX
   - Affects: Perceived performance
   - Benefit: Show something immediately while loading rest

---

## 10. **Benchmarking Code**

### Measure Before and After

```python
import time
import functools

def benchmark(func):
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper

# Usage
@benchmark
def load_data(self, algorithm):
    # ... your loading code
    pass
```

---

## Summary: Implementation Roadmap

**Week 1:** Spatial indexing + disk caching (biggest wins)  
**Week 2:** HDF5 conversion + memory-mapped FITS  
**Week 3:** Clientside filtering + batch polygon traces  
**Week 4:** Progressive loading + memory management

**Expected Overall Speedup:** 5-10x for typical operations, 50-100x for spatial queries

---

## Next Steps

Prioritize implementations based on your current bottlenecks. Use the benchmarking decorator to measure impact of each optimization.
