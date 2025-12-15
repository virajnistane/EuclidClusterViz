"""
UI layout package for cluster visualization app.

This package contains the UI layout definitions for the Dash application.
"""

AppLayout: object = None

try:
    from .layout import AppLayout

    __all__ = ["AppLayout"]

except ImportError as e:
    # Graceful fallback if modules not available
    print(f"⚠️  Warning: UI layout modules not fully available: {e}")
    __all__ = []
