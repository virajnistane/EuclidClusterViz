#!/usr/bin/env python
"""
Quick test to see debug output during normal app operations.
"""
import sys
import pathlib

path = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.append(str(path))

from cluster_visualization.src.config import Config
from cluster_visualization.src.data.loader import DataLoader

print("=" * 70)
print("MEMORY MANAGER DEBUG OUTPUT TEST")
print("=" * 70)

# Initialize with small limit to see more interesting behavior
config = Config()
loader = DataLoader(config, use_disk_cache=True, max_memory_gb=2.0)

print("\n" + "=" * 70)
print("SCENARIO 1: First Load (Cache Miss)")
print("=" * 70)
data1 = loader.load_data("PZWAV")

print("\n" + "=" * 70)
print("SCENARIO 2: Second Load (Cache Hit)")
print("=" * 70)
data1_again = loader.load_data("PZWAV")

print("\n" + "=" * 70)
print("SCENARIO 3: Different Algorithm (Cache Miss)")
print("=" * 70)
data2 = loader.load_data("AMICO")

print("\n" + "=" * 70)
print("SCENARIO 4: Third Algorithm (May Trigger Memory Management)")
print("=" * 70)
data3 = loader.load_data("BOTH")

print("\n" + "=" * 70)
print("SCENARIO 5: Switching Back (Cache Hit if Still in Memory)")
print("=" * 70)
data1_third = loader.load_data("PZWAV")

print("\n" + "=" * 70)
print("FINAL MEMORY STATUS")
print("=" * 70)
loader.print_memory_report()

print("\n✓ Debug output test complete!")
print("\nKey debug indicators to look for:")
print("  🔍 [Memory Check] - Shows current memory before each operation")
print("  ✓ [Cache HIT]    - Data found in memory cache")
print("  ⏳ [Cache MISS]   - Data needs to be loaded from disk/file")
print("  💾 [Cache Decision] - Whether data can fit in memory")
print("  ⚠️  [Memory threshold exceeded] - Automatic cleanup triggered")
print("  ↳ [Follow-up info] - Additional details about the operation")
