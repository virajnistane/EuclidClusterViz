"""
Memory Management Module

Monitors and manages memory usage to prevent OOM crashes and maintain performance.
Implements LRU cache eviction and automatic memory cleanup.
"""

import gc
import time
from typing import Any, Dict

import psutil


class MemoryManager:
    """Manages memory usage and implements cache eviction strategies."""

    def __init__(self, max_memory_gb: float = 8.0, warning_threshold: float = 0.8):
        """
        Initialize memory manager.

        Args:
            max_memory_gb: Maximum memory to use in GB (default: 8GB)
            warning_threshold: Trigger cleanup at this fraction of max (default: 0.8 = 80%)
        """
        self.max_memory_bytes = max_memory_gb * 1024**3
        self.warning_threshold_bytes = self.max_memory_bytes * warning_threshold
        self.access_times: Dict[str, float] = {}  # Track when each cache item was last accessed
        self.process = psutil.Process()

        print(f"Memory manager initialized:")
        print(f"  Max memory: {max_memory_gb:.1f} GB")
        print(f"  Warning threshold: {max_memory_gb * warning_threshold:.1f} GB")

    def check_memory(self) -> int:
        """
        Get current memory usage in bytes.

        Returns:
            Current RSS (Resident Set Size) memory in bytes
        """
        rss: int = self.process.memory_info().rss
        return rss

    def get_memory_stats(self) -> Dict[str, float]:
        """
        Get detailed memory statistics.

        Returns:
            Dictionary with memory usage information
        """
        mem_info = self.process.memory_info()
        system_mem = psutil.virtual_memory()

        return {
            "rss_mb": mem_info.rss / 1024**2,  # Resident Set Size (actual RAM used)
            "vms_mb": mem_info.vms / 1024**2,  # Virtual Memory Size
            "rss_gb": mem_info.rss / 1024**3,
            "percent": self.process.memory_percent(),  # Percentage of system RAM
            "available_gb": system_mem.available / 1024**3,
            "total_gb": system_mem.total / 1024**3,
            "system_percent": system_mem.percent,
        }

    def mark_accessed(self, key: str) -> None:
        """
        Mark a cache item as recently accessed.

        Args:
            key: Cache item key
        """
        self.access_times[key] = time.time()

    def has_room(self) -> bool:
        """
        Check if we have room for more data (not at threshold yet).

        Returns:
            True if below warning threshold, False otherwise
        """
        current_memory = self.check_memory()
        return current_memory < self.warning_threshold_bytes

    def cleanup_if_needed(self, cache_dict: Dict[str, Any]) -> bool:
        """
        Automatically cleanup memory if threshold exceeded.

        Args:
            cache_dict: Dictionary containing cached data

        Returns:
            True if cleanup was performed, False otherwise
        """
        current_memory = self.check_memory()

        if current_memory > self.warning_threshold_bytes:
            stats = self.get_memory_stats()
            print(
                f"⚠️  Memory threshold exceeded: {stats['rss_gb']:.2f} GB / {self.max_memory_bytes / 1024**3:.2f} GB"
            )
            print(f"   Process using {stats['percent']:.1f}% of system RAM")

            # Get items sorted by access time (oldest first)
            items_by_age = sorted(
                self.access_times.items(), key=lambda x: x[1]  # Sort by timestamp
            )

            freed_total = 0
            removed_keys = []

            # Remove least recently used items until below 70% threshold
            target_memory = self.max_memory_bytes * 0.7

            for key, _ in items_by_age:
                if key in cache_dict:
                    # Remove item without expensive size calculation
                    del cache_dict[key]
                    del self.access_times[key]
                    removed_keys.append(key)

                    print(f"   Evicted cache: {key}")

                    # Check if we're below target now
                    if self.check_memory() < target_memory:
                        break

            # Force garbage collection
            gc.collect()

            new_memory = self.check_memory()
            actual_freed_mb = (current_memory - new_memory) / 1024**2
            new_stats = self.get_memory_stats()

            print(f"✓ Memory cleanup complete:")
            print(f"   Removed {len(removed_keys)} cache entries")
            print(f"   Freed ~{actual_freed_mb:.1f} MB")
            print(f"   Now using {new_stats['rss_gb']:.2f} GB ({new_stats['percent']:.1f}%)")

            return True

        return False

    def get_cache_stats(self, cache_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get statistics about cached items.
        Note: Uses process memory, not individual object sizes (which are slow to calculate).

        Args:
            cache_dict: Dictionary containing cached data

        Returns:
            Dictionary with cache statistics
        """
        items_by_age = []

        for key in cache_dict.keys():
            last_access = self.access_times.get(key, 0)
            age = time.time() - last_access if last_access > 0 else 0

            items_by_age.append({"key": key, "last_access": last_access, "age_seconds": age})

        # Sort by access time (most recent first)
        items_by_age.sort(key=lambda x: x["last_access"], reverse=True)

        return {"total_items": len(cache_dict), "items": items_by_age}

    def print_cache_report(self, cache_dict: Dict[str, Any]) -> None:
        """
        Print detailed cache usage report.

        Args:
            cache_dict: Dictionary containing cached data
        """
        mem_stats = self.get_memory_stats()
        cache_stats = self.get_cache_stats(cache_dict)

        print("\n" + "=" * 70)
        print("MEMORY USAGE REPORT")
        print("=" * 70)
        print(f"System Memory:")
        print(f"  Total RAM:      {mem_stats['total_gb']:.1f} GB")
        print(
            f"  Available:      {mem_stats['available_gb']:.1f} GB ({100 - mem_stats['system_percent']:.1f}% free)"
        )
        print(f"\nProcess Memory:")
        print(f"  RSS (actual):   {mem_stats['rss_mb']:.1f} MB ({mem_stats['rss_gb']:.2f} GB)")
        print(f"  VMS (virtual):  {mem_stats['vms_mb']:.1f} MB")
        print(f"  % of system:    {mem_stats['percent']:.1f}%")
        print(f"\nCache Statistics:")
        print(f"  Items cached:   {cache_stats['total_items']}")
        print(f"  Process memory: {mem_stats['rss_mb']:.1f} MB ({mem_stats['rss_gb']:.2f} GB)")
        print(f"  Max allowed:    {self.max_memory_bytes / 1024**3:.1f} GB")
        print(
            f"  Usage:          {(mem_stats['rss_gb'] / (self.max_memory_bytes / 1024**3)) * 100:.1f}%"
        )

        if cache_stats["items"]:
            print(f"\nCached items (by recency):")
            for item in cache_stats["items"][:5]:  # Show top 5
                age_str = (
                    f"{item['age_seconds']/60:.1f} min"
                    if item["age_seconds"] > 60
                    else f"{item['age_seconds']:.0f} sec"
                )
                print(f"  {item['key']:30s} (age: {age_str})")

        print("=" * 70 + "\n")

    @staticmethod
    def recommend_cache_size() -> float:
        """
        Recommend optimal cache size based on system memory.

        Returns:
            Recommended cache size in GB
        """
        system_mem = psutil.virtual_memory()
        total_ram_gb = system_mem.total / 1024**3

        # Use 50% of available RAM for cache, capped at 16GB
        recommended: float = min(total_ram_gb * 0.5, 16.0)

        print(f"\n💡 Memory Configuration Recommendation:")
        print(f"   System has {total_ram_gb:.1f} GB RAM")
        print(f"   Recommended cache size: {recommended:.1f} GB")
        print(f"   This allows safe multi-user operation and prevents OOM crashes\n")

        return recommended
