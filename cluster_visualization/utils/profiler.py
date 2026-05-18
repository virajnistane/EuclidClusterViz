"""Lightweight cumulative wall-clock profiler for ClusterViz trace creation.

Usage
-----
The profiler is attached to :class:`TraceCreator` as ``self._profiler``.
It accumulates per-section stats across all renders and prints a sorted
summary table after every render call (controlled by
``CLUSTERVIZ_PROFILE`` env-var — set to ``"0"`` to disable).

Sections currently tracked
--------------------------
create_traces:total             – full create_traces() wall time
create_traces:merged_cluster_trace – _add_merged_cluster_trace()
create_traces:polygon_loop      – per-tile polygon creation loop
create_traces:unmerged_traces   – _add_unmerged_cluster_traces()
create_traces:diskcache         – CATRED diskcache persistence
tile_colors:total               – _compute_merged_tile_colors() (each call)
tile_colors:flat_build          – building per-tile flat coordinate arrays
tile_colors:kdtree_build        – scipy cKDTree construction
tile_colors:kdtree_query        – cKDTree nearest-neighbor query
tile_colors:numpy_fallback      – numpy argmin fallback (no scipy)
"""

import os
import time
import threading
from typing import Dict


_ENABLED_DEFAULT: bool = os.environ.get("CLUSTERVIZ_PROFILE", "1") != "0"


class _Stats:
    """Stores running stats for one named section."""

    __slots__ = ("count", "total", "min", "max")

    def __init__(self) -> None:
        self.count: int = 0
        self.total: float = 0.0
        self.min: float = float("inf")
        self.max: float = 0.0

    def update(self, elapsed: float) -> None:
        self.count += 1
        self.total += elapsed
        if elapsed < self.min:
            self.min = elapsed
        if elapsed > self.max:
            self.max = elapsed


class TraceProfiler:
    """Thread-safe cumulative wall-clock profiler.

    Stats are stored at the **class** level so they accumulate across
    multiple ``TraceCreator`` instances and Dash callback invocations
    (Dash may create fresh objects per request).

    Parameters
    ----------
    enabled:
        Override the ``CLUSTERVIZ_PROFILE`` env-var default.
    """

    _lock: threading.Lock = threading.Lock()
    _stats: Dict[str, _Stats] = {}
    _render_count: int = 0

    def __init__(self, enabled: bool = _ENABLED_DEFAULT) -> None:
        self.enabled = enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def timer(self, name: str) -> "_TimerCtx":
        """Return a context manager that times the enclosed block."""
        return _TimerCtx(name, self)

    def record(self, name: str, elapsed: float) -> None:
        """Record *elapsed* seconds for *name*."""
        if not self.enabled:
            return
        with self._lock:
            if name not in TraceProfiler._stats:
                TraceProfiler._stats[name] = _Stats()
            TraceProfiler._stats[name].update(elapsed)

    def tick_render(self) -> None:
        """Increment render counter and print the stats table."""
        if not self.enabled:
            return
        with self._lock:
            TraceProfiler._render_count += 1
            n = TraceProfiler._render_count
        self.print_stats(header=f"render #{n}")

    def print_stats(self, header: str = "") -> None:
        """Print a sorted stats table to stdout."""
        W = 70
        with self._lock:
            if not TraceProfiler._stats:
                return
            lines = [
                "",
                "=" * W,
                f"  CLUSTERVIZ PROFILER  {header}",
                "=" * W,
                f"  {'Section':<44} {'calls':>5}  {'total ms':>9}  "
                f"{'avg ms':>7}  {'min ms':>7}  {'max ms':>7}",
                f"  {'-'*44} {'-'*5}  {'-'*9}  {'-'*7}  {'-'*7}  {'-'*7}",
            ]
            sorted_items = sorted(
                TraceProfiler._stats.items(),
                key=lambda kv: kv[1].total,
                reverse=True,
            )
            for name, s in sorted_items:
                avg = s.total / s.count if s.count else 0.0
                lines.append(
                    f"  {name:<44} {s.count:>5}  {s.total*1000:>9.1f}  "
                    f"{avg*1000:>7.2f}  {s.min*1000:>7.2f}  {s.max*1000:>7.2f}"
                )
            lines.append("=" * W + "\n")
        print("\n".join(lines))

    def reset(self) -> None:
        """Clear all accumulated stats and reset render counter."""
        with self._lock:
            TraceProfiler._stats.clear()
            TraceProfiler._render_count = 0


class _TimerCtx:
    """Context manager returned by :meth:`TraceProfiler.timer`."""

    __slots__ = ("name", "profiler", "_t0")

    def __init__(self, name: str, profiler: TraceProfiler) -> None:
        self.name = name
        self.profiler = profiler
        self._t0: float = 0.0

    def __enter__(self) -> "_TimerCtx":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        self.profiler.record(self.name, time.perf_counter() - self._t0)
