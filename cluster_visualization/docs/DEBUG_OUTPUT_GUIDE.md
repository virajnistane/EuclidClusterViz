# Memory Manager Debug Output Reference

## Overview
When the app is running, the memory manager provides detailed debug output to help you understand memory operations and diagnose issues.

---

## Debug Output Symbols

| Symbol | Meaning | When You See It |
|--------|---------|-----------------|
| 🔍 | Memory Check | Before each data load operation |
| ✓ | Success/Cache Hit | Data found in memory cache |
| ⏳ | Cache Miss | Data needs to be loaded from disk/FITS files |
| 💾 | Cache Decision | Deciding whether to store data in memory |
| ⚠️ | Warning | Memory threshold exceeded or cache skipped |
| ↳ | Follow-up Info | Additional details about the operation |

---

## Example Debug Output Flow

### Normal Operation (Cache Miss → Cache Hit)

```
🔍 [Memory Check] Current: 138.1 MB, Loading: PZWAV
⏳ [Cache MISS] Loading data for algorithm: PZWAV
✓ Using GlueMatchCat for merged data (includes both PZWAV and AMICO)
✓ Loaded from cache: merged_catalog_PZWAV (4.76 MB, age: 1.8 hours)
💾 [Cache Decision] Data size: 0.0 MB, Current: 158.8 MB / 2048.0 MB
   ↳ ✓ Cached in memory: PZWAV
   ↳ Memory now: 158.8 MB (usage: 7.8%)
```

**What's happening:**
1. Checking current memory (138.1 MB) before loading PZWAV
2. Data not in memory cache, loading from disk
3. Successfully loaded from disk cache (fast: 9x speedup)
4. Deciding whether to cache in memory
5. Data fits, cached successfully
6. Memory increased to 158.8 MB (7.8% of 2 GB limit)

---

### Cache Hit (Fast Path)

```
🔍 [Memory Check] Current: 158.8 MB, Loading: PZWAV
✓ [Cache HIT] Using cached data for PZWAV
   ↳ Marked PZWAV as recently accessed (LRU)
```

**What's happening:**
1. Checking current memory
2. Data already in memory - instant retrieval!
3. Updating access time for LRU tracking

---

### Memory Threshold Exceeded (Automatic Cleanup)

```
🔍 [Memory Check] Current: 1850.5 MB, Loading: BOTH
⚠️  Memory threshold exceeded: 1.81 GB / 2.00 GB
   Process using 15.2% of system RAM
   Evicted cache: PZWAV (~12.4 MB)
   Evicted cache: AMICO (~18.7 MB)
✓ Memory cleanup complete:
   Removed 2 cache entries
   Freed ~31.2 MB
   Now using 1.79 GB (14.8%)
⏳ [Cache MISS] Loading data for algorithm: BOTH
```

**What's happening:**
1. Memory check shows we're at 1.85 GB (exceeds 80% of 2 GB limit)
2. Automatic cleanup triggered
3. Removes least recently used items (PZWAV, AMICO)
4. Freed 31.2 MB, now at 1.79 GB
5. Proceeds to load BOTH algorithm

---

### Memory Cache Skipped (Near Limit)

```
💾 [Cache Decision] Data size: 85.3 MB, Current: 1920.0 MB / 2048.0 MB
   ↳ ⚠️  Skipping memory cache for BOTH (would exceed limit)
   ↳ Data will be loaded from disk cache on next request.
```

**What's happening:**
1. New data is 85.3 MB
2. Current memory is 1920 MB (close to 2048 MB limit)
3. Caching would exceed threshold
4. Skipping memory cache (disk cache still works!)
5. Next request will load from disk (still fast: 9x speedup)

---

## How to Read Memory Usage

### Memory Check Format
```
🔍 [Memory Check] Current: 258.2 MB, Loading: AMICO
```
- **Current**: Process memory usage right now
- **Loading**: Which algorithm is being loaded

### Cache Decision Format
```
💾 [Cache Decision] Data size: 12.4 MB, Current: 158.8 MB / 2048.0 MB
   ↳ ✓ Cached in memory: PZWAV
   ↳ Memory now: 171.2 MB (usage: 8.4%)
```
- **Data size**: How much new data we're adding
- **Current / Max**: Current memory vs maximum allowed
- **Memory now**: Total after caching
- **Usage %**: Percentage of maximum (should stay < 80%)

---

## What to Look For

### ✅ Healthy Patterns

1. **Cache hits after first load:**
   ```
   ✓ [Cache HIT] Using cached data for PZWAV
   ```
   This means data is being reused efficiently.

2. **Memory usage stays under 80%:**
   ```
   ↳ Memory now: 258.2 MB (usage: 12.6%)
   ```
   Plenty of headroom, no cleanup needed.

3. **LRU tracking works:**
   ```
   ↳ Marked PZWAV as recently accessed (LRU)
   ```
   Recently used data won't be evicted first.

### ⚠️ Warning Patterns

1. **Frequent memory cleanup:**
   ```
   ⚠️  Memory threshold exceeded: 1.85 GB / 2.00 GB
   ```
   If you see this often, consider increasing `max_memory_gb`.

2. **Always skipping memory cache:**
   ```
   ↳ ⚠️  Skipping memory cache for ... (would exceed limit)
   ```
   Memory limit may be too low for your data size.

3. **Memory continuously growing:**
   ```
   Memory now: 500 MB → 800 MB → 1200 MB → 1600 MB
   ```
   Possible memory leak or limit too high.

### 🔴 Problem Patterns

1. **No memory manager:**
   ```
   💾 Cached in memory: PZWAV (no memory limit)
   ```
   This appears for EVERY load - memory manager may not be active.

2. **Eviction not working:**
   Memory exceeds threshold but no eviction message appears.

---

## Testing Debug Output

### Quick Test
```bash
python cluster_visualization/tests/test_debug_output.py
```

Shows typical scenarios:
- Cache miss (first load)
- Cache hit (second load)
- Multiple algorithms
- Memory management decisions

### Comprehensive Test
```bash
python cluster_visualization/tests/test_memory_with_traces.py
```

Shows memory behavior with trace rendering included.

---

## Interpreting the Output

### Scenario: Switching Algorithms in Dash App

When user changes dropdown from PZWAV → AMICO:

```
🔍 [Memory Check] Current: 200.5 MB, Loading: AMICO
⏳ [Cache MISS] Loading data for algorithm: AMICO
[... loading from disk cache ...]
💾 [Cache Decision] Data size: 15.2 MB, Current: 215.7 MB / 3072.0 MB
   ↳ ✓ Cached in memory: AMICO
   ↳ Memory now: 230.9 MB (usage: 7.5%)
```

**User experience:** Fast load from disk cache (9x speedup), cached for instant access next time.

---

### Scenario: Long-Running Session with Many Switches

After 20+ algorithm switches:

```
🔍 [Memory Check] Current: 2450.3 MB, Loading: BOTH
⚠️  Memory threshold exceeded: 2.45 GB / 3.00 GB
   Process using 1.3% of system RAM
   Evicted cache: PZWAV (~45.2 MB)
✓ Memory cleanup complete:
   Removed 1 cache entries
   Freed ~45.2 MB
   Now using 2.40 GB (80.0%)
```

**User experience:** Brief cleanup (< 0.1s), then normal operation continues. Old algorithm data removed, most recent kept.

---

## Tuning Based on Debug Output

### If You See Frequent Evictions
```python
# Increase memory limit
loader = DataLoader(config, max_memory_gb=8.0)  # Instead of 3.0
```

### If Memory Usage Always Low
```python
# Can reduce limit to free up system resources
loader = DataLoader(config, max_memory_gb=2.0)  # Instead of 8.0
```

### If You Want Verbose Logging
The debug output is already verbose. To disable:
- Comment out print statements in `loader.py`
- Or redirect stdout: `python app.py > /dev/null 2>&1`

---

## Summary

**The debug output tells you:**
1. 🔍 When memory checks happen
2. ✓/⏳ Whether data is cached or needs loading  
3. 💾 Memory caching decisions
4. ⚠️ When automatic cleanup occurs
5. 📊 Current vs maximum memory usage

**All of this happens automatically** - no action required unless you see warning patterns consistently.
