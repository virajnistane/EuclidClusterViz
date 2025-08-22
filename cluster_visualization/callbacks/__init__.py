"""
Callbacks package for cluster visualization app.

This package contains all Dash callback implementations organized by functionality.
"""

try:
    from .main_plot import MainPlotCallbacks
    from .catred_callbacks import CATREDCallbacks  
    from .ui_callbacks import UICallbacks
    from .phz_callbacks import PHZCallbacks
    
    __all__ = ['MainPlotCallbacks', 'CATREDCallbacks', 'UICallbacks', 'PHZCallbacks']
    
except ImportError as e:
    print(f"Warning: Could not import all callback modules: {e}")
    MainPlotCallbacks = None
    CATREDCallbacks = None
