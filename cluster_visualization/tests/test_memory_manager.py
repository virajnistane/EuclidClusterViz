#!/usr/bin/env python
"""
Test script for memory management functionality.

Demonstrates:
1. Memory monitoring
2. Cache eviction
3. Memory report generation
"""
import sys
import pathlib
import pdb

path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(path))

import time
from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader


def test_memory_management():
    """Test memory management features."""
    print("=" * 70)
    print("MEMORY MANAGEMENT TEST")
    print("=" * 70)

    # Initialize with a small memory limit to trigger eviction
    config = Config()
    loader = DataLoader(config, use_disk_cache=True, max_memory_gb=2.0)

    print("\n1. Loading PZWAV data...")
    data_pzwav = loader.load_data("PZWAV")
    print(f"   Loaded {len(data_pzwav['data_detcluster_mergedcat'])} clusters")

    # Print initial memory report
    print("\n2. Initial memory state:")
    loader.print_memory_report()

    print("\n3. Loading AMICO data...")
    data_amico = loader.load_data("AMICO")
    print(f"   Loaded {len(data_amico['data_detcluster_mergedcat'])} clusters")

    print("\n4. Loading BOTH data...")
    data_both = loader.load_data("BOTH")
    print(f"   Loaded {len(data_both['data_detcluster_mergedcat'])} clusters")

    # Print memory report after loading multiple datasets
    print("\n5. Memory state after loading 3 datasets:")
    loader.print_memory_report()

    # Get memory stats
    stats = loader.get_memory_stats()
    if stats:
        print(f"\n6. Quick memory check:")
        print(f"   Process using: {stats['rss_mb']:.1f} MB")
        print(f"   System has: {stats['available_gb']:.1f} GB available")

    # Simulate switching between algorithms multiple times
    print("\n7. Simulating rapid algorithm switching (10 times)...")
    algorithms = ["PZWAV", "AMICO", "BOTH"]
    for i in range(10):
        algo = algorithms[i % 3]
        _ = loader.load_data(algo)
        print(f"   Switch {i+1}: {algo}")

    print("\n8. Final memory state:")
    loader.print_memory_report()

    print("\n9. Manual cache clear:")
    loader.clear_memory_cache()
    loader.print_memory_report()

    print("\n" + "=" * 70)
    print("✓ Memory management test complete!")
    print("=" * 70)


if __name__ == "__main__":
    test_memory_management()
