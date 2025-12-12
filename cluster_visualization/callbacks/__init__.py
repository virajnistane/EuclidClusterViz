"""
Callbacks package for cluster visualization app.

This package contains all Dash callback implementations organized by functionality.
"""

try:
    from .catred_callbacks import CATREDCallbacks
    from .cluster_modal_callbacks import ClusterModalCallbacks
    from .main_plot import MainPlotCallbacks
    from .mosaic_callback import MOSAICCallbacks
    from .phz_callbacks import PHZCallbacks
    from .ui_callbacks import UICallbacks

    __all__ = [
        "MainPlotCallbacks",
        "CATREDCallbacks",
        "MOSAICCallbacks",
        "UICallbacks",
        "PHZCallbacks",
        "ClusterModalCallbacks",
    ]

except ImportError as e:
    print(f"Warning: Could not import all callback modules: {e}")
    MainPlotCallbacks = None
    CATREDCallbacks = None
