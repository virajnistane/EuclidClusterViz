"""
Callbacks package for cluster visualization app.

This package contains all Dash callback implementations organized by functionality.
"""

try:
    from .main_plot import MainPlotCallbacks
    from .mer_callbacks import MERCallbacks  
    from .ui_callbacks import UICallbacks
    from .phz_callbacks import PHZCallbacks
    
    __all__ = ['MainPlotCallbacks', 'MERCallbacks', 'UICallbacks', 'PHZCallbacks']
    
except ImportError as e:
    # Graceful fallback if modules not available
    print(f"⚠️  Warning: Callbacks modules not fully available: {e}")
    MainPlotCallbacks = None
    MERCallbacks = None
    UICallbacks = None
    PHZCallbacks = None
    __all__ = []
