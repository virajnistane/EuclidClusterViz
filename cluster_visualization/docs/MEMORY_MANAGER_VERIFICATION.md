# Memory Manager Verification Guide

## How to Know If Memory Manager Is Working

The memory manager automatically monitors and controls memory usage to prevent OOM (Out Of Memory) crashes. Here's how to verify it's working correctly:

---

## 1. Quick Verification (Basic Test)

Run the basic memory test:
```bash
python cluster_visualization/tests/test_memory_manager.py
```

**What to look for:**
- ✅ "Memory manager initialized" message at startup
- ✅ Memory usage stays stable across multiple algorithm switches
- ✅ Cache size stays below max_memory_gb limit
- ✅ Memory report shows accurate statistics

---

## 2. Comprehensive Verification (With Trace Rendering)

Run the comprehensive test that includes trace rendering:
```bash
python cluster_visualization/tests/test_memory_with_traces.py
```

**What to look for:**
- ✅ Memory increases during data loading + trace rendering
- ✅ Memory stabilizes and doesn't grow indefinitely
- ✅ Cache statistics show items being tracked
- ✅ Memory growth < 250 MB over 15 algorithm switches
- ✅ Cache usage stays below threshold (< 80%)

### Example Output (Good):
```
Process memory:     705.7 MB
Max allowed cache:  3072.0 MB
Cache usage:        23.0%
System available:   117.6 GB

✓ Memory manager keeping usage below threshold
```

---

## 3. Key Indicators Memory Manager Is Working

### ✅ **1. Memory Stays Stable During Algorithm Switching**
When you switch between PZWAV, AMICO, and BOTH repeatedly, memory should:
- Increase initially as datasets are loaded
- Stabilize after 3-5 switches
- Not grow indefinitely

**Test:**
```python
from cluster_visualization.src.data.loader import DataLoader
from cluster_visualization.src.config import Config

loader = DataLoader(Config(), max_memory_gb=2.0)

# Switch algorithms 10 times
for i in range(10):
    algo = ['PZWAV', 'AMICO', 'BOTH'][i % 3]
    data = loader.load_data(algo)
    loader.print_memory_report()  # Check each iteration
```

**Expected:** Memory fluctuates but doesn't continuously increase.

---

### ✅ **2. Cache Size Stays Below max_memory_gb Limit**
The memory manager enforces a hard limit on cached data.

**Check the memory report:**
```
Cache Statistics:
  Items cached:   3
  Cache size:     0.0 MB (0.00 GB)
  Max allowed:    3.0 GB
  Usage:          16.0%   <-- Should stay < 80%
```

**If usage exceeds 80%:** Memory manager will automatically evict least recently used items.

---

### ✅ **3. LRU Eviction Happens Automatically**
When memory approaches the limit, the manager evicts old items.

**To trigger eviction:**
```python
# Set a very small limit to force eviction
loader = DataLoader(Config(), max_memory_gb=0.5)

# Load multiple algorithms - should trigger eviction
data1 = loader.load_data('PZWAV')   # Loads and caches
data2 = loader.load_data('AMICO')   # Loads and caches  
data3 = loader.load_data('BOTH')    # May evict PZWAV if memory low
```

**Look for:**
- Items being removed from cache
- "Evicted X items" messages (if verbose logging enabled)
- Cache count decreasing despite loading new data

---

### ✅ **4. No Memory Leaks**
Process memory should stabilize after initial warmup.

**Acceptable:** +50-250 MB growth over 15 switches (Python overhead, trace objects)
**Concerning:** +500+ MB growth or continuous increase

**Monitor with:**
```python
stats = loader.get_memory_stats()
print(f"Process RSS: {stats['rss_mb']:.1f} MB")
```

---

### ✅ **5. System Available Memory Stays Healthy**
The manager should keep enough free RAM for the system.

**Check:**
```
System Memory:
  Total RAM:      188.0 GB
  Available:      117.6 GB (62.5% free)  <-- Should stay > 50%
```

---

## 4. Does It Work After Rendering Traces?

**Yes!** The memory manager monitors the entire process memory, including:
- ✅ Loaded FITS data
- ✅ Cached numpy arrays
- ✅ Rendered Plotly traces
- ✅ All Python objects in memory

### Trace Rendering Memory Impact:
```
Phase 1 - Data Loading:     162 MB (PZWAV data)
Phase 2 - After Traces:     196 MB (+34 MB for traces)
Phase 3 - All 3 Datasets:   492 MB (data + traces)
Phase 4 - 15 Switches:      706 MB (stabilized)
```

**The memory manager sees all of this** and will evict cached data if total process memory approaches the limit.

---

## 5. Manual Memory Operations

### Check Memory Stats Anytime:
```python
stats = loader.get_memory_stats()
print(f"Process: {stats['rss_mb']:.1f} MB")
print(f"Available: {stats['available_gb']:.1f} GB")
```

### Print Full Memory Report:
```python
loader.print_memory_report()
```

### Manually Clear Cache:
```python
loader.clear_memory_cache()
```

---

## 6. Configuration Options

### Auto-Detect (Recommended):
```python
loader = DataLoader(config)  # Uses 50% of RAM, max 16 GB
```

### Custom Limit:
```python
loader = DataLoader(config, max_memory_gb=4.0)  # 4 GB limit
```

### Very Tight Constraint:
```python
loader = DataLoader(config, max_memory_gb=1.0)  # 1 GB limit
```

---

## 7. Warning Signs Memory Manager Is NOT Working

❌ **Memory grows continuously** - Check if MemoryManager is initialized
❌ **No eviction despite high usage** - Check threshold settings
❌ **OOM crashes still occur** - Limit may be set too high for system
❌ **Cache usage shows 0.0 MB always** - Memory size calculation may be broken

### Debug:
```python
# Check if memory manager is active
print(f"Memory manager available: {loader.memory_manager is not None}")
print(f"Max memory: {loader.memory_manager.max_memory_gb if loader.memory_manager else 'N/A'} GB")
```

---

## 8. Performance Impact

The memory manager has **negligible overhead**:
- Memory checks: ~0.001s per check (uses psutil)
- Eviction: Only happens when threshold exceeded
- Access tracking: Simple dictionary update

**No noticeable slowdown in normal operation.**

---

## 9. Integration with Dash App

In the real Dash app, memory manager works transparently:

```python
# In app initialization
data_loader = DataLoader(config, max_memory_gb=8.0)

# In callback when algorithm changes
@app.callback(...)
def update_plot(select_algorithm):
    # Memory manager automatically:
    # 1. Cleans up old data before loading
    # 2. Checks if new data fits
    # 3. Evicts LRU items if needed
    # 4. Tracks access time for LRU
    data = data_loader.load_data(select_algorithm)
    traces = create_traces(data)
    return traces
```

**Memory is managed automatically - no code changes needed in callbacks!**

---

## 10. Troubleshooting

### Issue: "Memory manager not available"
**Solution:** Ensure psutil is installed: `pip install psutil`

### Issue: Memory still grows despite manager
**Possible causes:**
1. Limit set too high (reduce max_memory_gb)
2. Traces not being garbage collected (keep only necessary trace references)
3. Memory leak in custom code (check for global variables accumulating data)

### Issue: Performance degraded
**Check:** If eviction happens too frequently, increase max_memory_gb

---

## Summary

**Memory Manager IS Working If:**
1. ✅ Memory stabilizes after initial loading
2. ✅ Cache usage stays < 80% of limit
3. ✅ No OOM crashes during algorithm switching
4. ✅ Memory reports show accurate statistics
5. ✅ System free RAM stays healthy (> 50%)

**Run the comprehensive test to verify all of the above:**
```bash
python cluster_visualization/tests/test_memory_with_traces.py
```
