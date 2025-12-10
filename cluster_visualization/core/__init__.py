"""
Core package for cluster visualization app.

This package contains the core application logic and utilities.
"""

try:
    from .app import ClusterVisualizationCore

    __all__ = ["ClusterVisualizationCore"]

except ImportError as e:
    # Graceful fallback if modules not available
    print(f"⚠️  Warning: Core modules not fully available: {e}")
    ClusterVisualizationCore = None
    __all__ = []
