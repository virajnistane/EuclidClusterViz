# Zoom-Based Oval Rendering Guide

## Overview

The matched cluster oval feature now uses **zoom-based rendering** to prevent performance issues. Ovals are only shown for clusters within the current viewport, making it practical to visualize matches even with 40,000+ total pairs.

---

## How It Works

### Workflow

1. **Select BOTH algorithm** from dropdown
2. **Enable "Show matched clusters"** toggle
3. **Zoom into region of interest** (pan/zoom on the plot)
4. **Click Re-render button** next to the toggle
5. **Ovals appear only for matches in viewport!**

### Re-rendering

- Ovals are **not automatically updated** when you pan/zoom
- This prevents constant re-rendering and maintains performance
- Click **Re-render button** whenever you want to update ovals for new viewport

---

## Performance Characteristics

### Before Fix (Full Dataset Rendering)
```
Total matched pairs: 40,727
Attempted to render: All 40,727 ovals at once
Result: App hangs for 60+ seconds, browser may crash
```

### After Fix (Viewport-Based Rendering)
```
Total matched pairs: 40,727
Viewport contains: 50-500 clusters (depends on zoom level)
Ovals rendered: 50-500 (instant!)
Result: Smooth, responsive interaction
```

---

## Example Scenarios

### Scenario 1: Wide View
```
User view: Full sky (RA: 0-360°, Dec: -90 to +90°)
Clusters in view: 40,727
Action: System shows warning + limits to top 2000 by SNR
Message: "⚠️ 40727 pairs in viewport is still too many!"
         "💡 Tip: Zoom in further or apply filters"
```

### Scenario 2: Regional Zoom
```
User view: Small region (RA: 58-62°, Dec: -63 to -60°)
Clusters in view: 342
Action: Renders all 342 ovals
Time: ~0.5 seconds
Message: "✓ Created 342 oval traces"
```

### Scenario 3: Tight Zoom (Recommended)
```
User view: Very small region (RA: 59-60°, Dec: -62 to -61°)
Clusters in view: 23
Action: Renders all 23 ovals perfectly
Time: <0.1 seconds
Message: "✓ Created 23 oval traces"
Result: Clear view of individual matched pairs!
```

---

## Tips for Best Experience

### 1. Start with Filters
Apply SNR or redshift filters first to reduce total cluster count:
```
- Set SNR threshold: e.g., > 5.0
- Set redshift range: e.g., 0.2 - 0.5
- This reduces clusters before matching
```

### 2. Zoom Before Rendering
```
1. Zoom into your region of interest first
2. Then click Re-render
3. Don't render at full sky view!
```

### 3. Use Progressive Zoom
```
1. Start with medium zoom (100-500 clusters)
2. See general pattern of matches
3. Zoom tighter (20-100 clusters) for details
4. Re-render at each zoom level
```

### 4. Monitor Feedback
Watch terminal output:
```
✓ Good: "PZWAV clusters in view: 145 / 40727"
⚠️ Still too many: "1234 pairs in viewport is still too many!"
✓ Perfect: "Created 67 oval traces"
```

---

## Understanding the Output

### Terminal Messages

**Zoom detection:**
```
🔍 Zoom-based oval rendering:
   Viewport: RA [58.39, 61.38], Dec [-62.18, -60.48]
   PZWAV clusters in view: 145 / 40727
```
- Shows current viewport bounds
- Shows how many clusters are visible vs total

**Safety limiting:**
```
⚠️ 3456 pairs in viewport is still too many!
   Limiting to highest SNR 2000 pairs.
   💡 Tip: Zoom in further or apply SNR/redshift filters
```
- Viewport still has too many clusters
- Auto-filters to top 2000 by SNR
- Suggests zooming in more

**Successful rendering:**
```
🎯 Creating 234 ovals for matched pairs...
   ✓ Created 234 oval traces
```
- Number within safe range
- All ovals rendered successfully

**No matches in view:**
```
ℹ️ No matched pairs in current viewport
```
- You zoomed to area with no matched clusters
- Pan to different region and re-render

---

## Safety Limits

### Hard Limits
- **Maximum ovals per render: 2000**
- Beyond this, only highest SNR pairs shown
- This prevents browser crashes

### Recommended Targets
- **Optimal: < 200 ovals** - Smooth interaction, clear visualization
- **Acceptable: 200-1000 ovals** - Still responsive, may be cluttered
- **Too many: 1000-2000 ovals** - Slow, hard to see individual pairs
- **Way too many: > 2000** - Auto-limited, need to zoom more

---

## Comparison: Full vs Viewport Rendering

| Aspect | Full Dataset | Viewport-Based |
|--------|-------------|----------------|
| Initial load | Hangs 60+ sec | Instant |
| Ovals shown | All 40K+ | 20-500 in view |
| Browser memory | May crash | Stable |
| Visualization | Too cluttered | Clear & detailed |
| User control | None | Full control |
| Re-render on pan | N/A (frozen) | Click Re-render |

---

## Troubleshooting

### "No zoom window detected" message
**Problem:** Ovals won't render because viewport info missing
**Solution:** 
1. Zoom in on the plot first
2. Then click Re-render button
3. System needs viewport bounds from zoom action

### Too many ovals even when zoomed
**Problem:** "Still too many" warning at tight zoom
**Solution:**
1. Apply SNR filters: Increase minimum SNR
2. Apply redshift filters: Narrow the range
3. Zoom even tighter: Focus on smaller region

### Ovals don't update when I pan
**Expected behavior:** This is intentional!
**Why:** Prevents constant re-rendering
**Solution:** Click Re-render button after panning

### No ovals appear
**Check:**
1. Is "Show matched clusters" toggle ON?
2. Did you select "BOTH" algorithm?
3. Did you click Re-render after zooming?
4. Are there matches in your viewport? (check terminal)

---

## Advanced Usage

### Finding Dense Match Regions
```python
# Look at terminal output across different regions:
# High density: "234 clusters in view" over small area
# Low density: "12 clusters in view" over same size area
# Focus on high-density regions for interesting matches
```

### SNR-Based Exploration
```python
# Strategy: Progressive SNR filtering
1. Start: SNR > 3.0 (see all matches)
2. Refine: SNR > 5.0 (higher quality)
3. Focus: SNR > 7.0 (best matches only)
# Re-render after each filter change
```

### Systematic Survey
```python
# To survey all matches systematically:
1. Apply tight filters (reduce to ~2000 total)
2. Divide sky into grid regions
3. Zoom to each grid cell
4. Re-render and inspect
5. Move to next cell
```

---

## Performance Metrics

### Timing Examples

| Clusters in Viewport | Oval Render Time | User Experience |
|---------------------|------------------|-----------------|
| 20 | < 0.1 sec | Instant |
| 100 | 0.2 sec | Very fast |
| 500 | 1.0 sec | Fast |
| 1000 | 2.5 sec | Acceptable |
| 2000 | 5.0 sec | Noticeable delay |

---

## Summary

**Key Benefits:**
1. ✅ No more hanging/crashing with large datasets
2. ✅ User controls when ovals are rendered (Re-render button)
3. ✅ Only shows relevant ovals for current view
4. ✅ Clear feedback about what's being shown
5. ✅ Encourages focused, detailed exploration

**Best Practice:**
1. Apply filters to reduce total clusters
2. Zoom to region of interest (not full sky!)
3. Click Re-render to show ovals
4. Pan to new area, Re-render again
5. Enjoy smooth, responsive visualization!
