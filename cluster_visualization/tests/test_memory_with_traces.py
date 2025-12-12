#!/usr/bin/env python
"""
Comprehensive memory management test including trace rendering.

Tests:
1. Memory monitoring during data loading
2. Memory usage during trace creation
3. Cache eviction with multiple algorithms
4. Memory stability over extended operations
"""
import pathlib
import sys

path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(path))

import time

from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader
from cluster_visualization.src.visualization.traces import TraceCreator


def test_memory_with_traces():
    """Test memory management through the full data loading + trace rendering workflow."""
    print("=" * 70)
    print("MEMORY MANAGEMENT TEST - WITH TRACE RENDERING")
    print("=" * 70)

    # Initialize with moderate memory limit
    config = Config()
    loader = DataLoader(config, use_disk_cache=True, max_memory_gb=3.0)

    print("\n" + "=" * 70)
    print("PHASE 1: DATA LOADING")
    print("=" * 70)

    print("\n1. Loading PZWAV data...")
    data_pzwav = loader.load_data("PZWAV")
    print(f"   ✓ Loaded {len(data_pzwav['data_detcluster_mergedcat'])} clusters")

    stats = loader.get_memory_stats()
    print(f"   Memory: {stats['rss_mb']:.1f} MB (Process)")

    print("\n2. Initial memory state:")
    loader.print_memory_report()

    # Initialize trace creator
    trace_creator = TraceCreator()

    print("\n" + "=" * 70)
    print("PHASE 2: TRACE RENDERING")
    print("=" * 70)

    print("\n3. Creating traces for PZWAV...")
    traces_pzwav = trace_creator.create_traces(
        data_pzwav, show_polygons=True, show_merged_clusters=True
    )
    print(f"   ✓ Created {len(traces_pzwav)} traces")

    stats = loader.get_memory_stats()
    print(f"   Memory: {stats['rss_mb']:.1f} MB (Process)")

    print("\n4. Loading and rendering AMICO...")
    data_amico = loader.load_data("AMICO")
    print(f"   ✓ Loaded {len(data_amico['data_detcluster_mergedcat'])} clusters")

    traces_amico = trace_creator.create_traces(
        data_amico, show_polygons=True, show_merged_clusters=True
    )
    print(f"   ✓ Created {len(traces_amico)} traces")

    stats = loader.get_memory_stats()
    print(f"   Memory: {stats['rss_mb']:.1f} MB (Process)")

    print("\n5. Memory state after 2 datasets + traces:")
    loader.print_memory_report()

    print("\n6. Loading and rendering BOTH...")
    data_both = loader.load_data("BOTH")
    print(f"   ✓ Loaded {len(data_both['data_detcluster_mergedcat'])} clusters")

    traces_both = trace_creator.create_traces(
        data_both, show_polygons=True, show_merged_clusters=True
    )
    print(f"   ✓ Created {len(traces_both)} traces")

    stats = loader.get_memory_stats()
    print(f"   Memory: {stats['rss_mb']:.1f} MB (Process)")

    print("\n7. Memory state after 3 datasets + traces:")
    loader.print_memory_report()

    print("\n" + "=" * 70)
    print("PHASE 3: ALGORITHM SWITCHING SIMULATION")
    print("=" * 70)

    print("\n8. Simulating user switching algorithms 15 times...")
    print("   (Each switch: load data + render traces)")

    algorithms = ["PZWAV", "AMICO", "BOTH"]
    start_mem = loader.get_memory_stats()["rss_mb"]

    for i in range(15):
        algo = algorithms[i % 3]
        data = loader.load_data(algo)
        traces = trace_creator.create_traces(data, show_polygons=True)

        if (i + 1) % 5 == 0:
            stats = loader.get_memory_stats()
            print(f"   After {i+1} switches: {stats['rss_mb']:.1f} MB")

    end_mem = loader.get_memory_stats()["rss_mb"]
    mem_growth = end_mem - start_mem

    print(f"\n   Memory growth: {mem_growth:+.1f} MB")
    if abs(mem_growth) < 50:
        print("   ✓ Memory stable (growth < 50 MB)")
    else:
        print("   ⚠ Memory increased significantly")

    print("\n9. Final memory state:")
    loader.print_memory_report()

    print("\n" + "=" * 70)
    print("PHASE 4: MEMORY ANALYSIS")
    print("=" * 70)

    stats = loader.get_memory_stats()
    cache_usage_pct = (stats["rss_mb"] / (3.0 * 1024)) * 100

    print(f"\n10. Summary:")
    print(f"    Process memory:     {stats['rss_mb']:.1f} MB")
    print(f"    Max allowed cache:  3072.0 MB")
    print(f"    Cache usage:        {cache_usage_pct:.1f}%")
    print(f"    System available:   {stats['available_gb']:.1f} GB")
    print(f"    Trace count:        {len(traces_both)} (last rendered)")

    if cache_usage_pct < 80:
        print(f"\n    ✓ Memory manager keeping usage below threshold")
    else:
        print(f"\n    ⚠ Memory usage approaching limit")

    print("\n11. Testing manual cache clear...")
    loader.clear_memory_cache()
    print("    ✓ Cache cleared")

    print("\n" + "=" * 70)
    print("✓ COMPREHENSIVE MEMORY TEST COMPLETE!")
    print("=" * 70)

    # Recommendations
    print("\n📊 KEY INDICATORS THAT MEMORY MANAGER IS WORKING:")
    print("   1. Memory stays stable during algorithm switching")
    print("   2. Cache size stays below max_memory_gb limit")
    print("   3. LRU eviction happens automatically (check 'Largest cached items')")
    print("   4. No memory leaks (growth < 50MB over 15 switches)")
    print("   5. System available memory stays healthy (> 50%)")


if __name__ == "__main__":
    test_memory_with_traces()
