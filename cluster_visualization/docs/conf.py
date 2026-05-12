# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# -- Path setup ---------------------------------------------------------------
# Point to the repo root so autodoc can import the cluster_visualization package.
sys.path.insert(0, os.path.abspath("../.."))

# -- Project information -------------------------------------------------------
project = "ClusterViz"
copyright = "2026, Viraj Nistane"
author = "Viraj Nistane"
release = "1.0.0"

# -- General configuration ----------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# MyST-Parser: recognise .md files as source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- Autodoc ------------------------------------------------------------------
autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Modules with heavy optional dependencies that may not be installed in the
# build environment are mocked so autodoc can still import the package.
autodoc_mock_imports = [
    "healpy",
    "dash",
    "dash_bootstrap_components",
    "diskcache",
    "plotly",
    "shapely",
    "astropy",
    "psutil",
    "PIL",
    "requests",
    "flask",
]

# -- Napoleon (NumPy / Google-style docstrings) -------------------------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_use_rtype = False

# -- Intersphinx --------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
}

# -- HTML output --------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = [] # type: ignore
html_theme_options = {
    "navigation_depth": 4,
    "titles_only": False,
}
