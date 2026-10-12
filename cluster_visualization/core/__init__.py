"""
Core package for cluster visualization app.

This package contains the core application logic and utilities.
"""

ClusterVisualizationCore: object = None

try:
    from .app import ClusterVisualizationCore

    __all__ = ["ClusterVisualizationCore"]

except ImportError as e:
    from loguru import logger

    # Graceful fallback if modules not available
    logger.warning(f"Core modules not fully available: {e}")
    __all__ = []
