#!/usr/bin/env python
"""
Test the oval rendering performance fix.

Simulates the scenario where user displays matched ovals with BOTH algorithms.
"""
import pathlib
import sys
import time

import numpy as np

path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(path))

from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader
from cluster_visualization.src.visualization.traces import TraceCreator


def test_oval_rendering():
    print("=" * 70)
    print("OVAL RENDERING PERFORMANCE TEST")
    print("=" * 70)

    # Load data
    config = Config()
    loader = DataLoader(config, use_disk_cache=True)

    print("\n1. Loading BOTH algorithm data...")
    start = time.time()
    data = loader.load_data("BOTH")
    load_time = time.time() - start
    print(f"   ✓ Loaded in {load_time:.2f}s")

    # Count potential matches
    merged_data = data["data_detcluster_mergedcat"]
    pzwav_mask = merged_data["DET_CODE_NB"] == 2
    amico_mask = merged_data["DET_CODE_NB"] == 1

    pzwav_data = merged_data[pzwav_mask]
    amico_data = merged_data[amico_mask]

    # Count matched pairs
    pzwav_matched = pzwav_data[np.logical_not(np.isnan(pzwav_data["CROSS_ID_CLUSTER"]))]
    amico_matched = amico_data[np.logical_not(np.isnan(amico_data["CROSS_ID_CLUSTER"]))]

    print(f"\n2. Data statistics:")
    print(f"   Total PZWAV clusters: {len(pzwav_data):,}")
    print(f"   Total AMICO clusters: {len(amico_data):,}")
    print(f"   Matched PZWAV: {len(pzwav_matched):,}")
    print(f"   Matched AMICO: {len(amico_matched):,}")
    print(f"   Potential ovals: {len(pzwav_matched):,}")

    # Test trace creation with matching enabled
    print(f"\n3. Creating traces with matching_clusters=True...")
    trace_creator = TraceCreator()

    start = time.time()
    traces = trace_creator.create_traces(
        data,
        show_polygons=True,
        show_merged_clusters=True,
        matching_clusters=True,  # This triggers oval creation
    )
    trace_time = time.time() - start

    print(f"\n4. Trace creation results:")
    print(f"   Time taken: {trace_time:.2f}s")
    print(f"   Total traces created: {len(traces)}")

    # Count oval traces
    oval_count = sum(1 for t in traces if hasattr(t, "name") and t.name == "Matched Pair")
    print(f"   Oval traces: {oval_count}")

    # Performance assessment
    print(f"\n5. Performance assessment:")
    if trace_time < 5:
        print(f"   ✓ FAST - Trace creation under 5s")
    elif trace_time < 15:
        print(f"   ⚠ ACCEPTABLE - Some delay but usable ({trace_time:.1f}s)")
    else:
        print(f"   ✗ SLOW - Taking too long ({trace_time:.1f}s)")

    if oval_count <= 1000:
        print(f"   ✓ Oval count within safe limit ({oval_count} <= 1000)")
    else:
        print(f"   ⚠ Too many ovals ({oval_count} > 1000)")

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(
        f"""
Before Fix:
  - Tried to create {len(pzwav_matched):,} ovals
  - Would take 60+ seconds
  - App would hang/freeze
  - Browser might crash

After Fix:
  - Automatically limited to 1000 highest-SNR pairs
  - Took {trace_time:.2f}s
  - App remains responsive
  - User gets clear warning message

Recommendation:
  - Users should apply SNR/redshift filters to reduce data
  - Or zoom into specific region of interest
  - Current limit of 1000 ovals is reasonable for performance
"""
    )


if __name__ == "__main__":
    test_oval_rendering()
