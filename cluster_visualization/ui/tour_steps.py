"""
Guided-tour step definitions (driver.js), shared by every tour.

- ``quick``: a one-minute overview of the main areas.
- One entry per sidebar section: a detailed walk through every control in it.
- The full walkthrough is ``quick`` followed by every section, in SECTION_ORDER.

Each step: ``element`` (CSS selector), ``title``, ``body``, ``side`` and, for
section steps, ``section`` (the sidebar section id the engine opens before the
step is shown). Steps whose element is missing or hidden when a tour starts are
skipped, so variant controls (e.g. AMICO SNR while PZWAV is selected) only show
when they are actually on screen.
"""

# Sidebar section id -> menu / button label
SECTION_TITLES = {
    "clusters-settings": "Catalog",
    "filters-settings": "Filters",
    "mask-controls": "Mask",
    "image-controls": "Mosaic",
    "display-options": "Display",
    "app-config": "Configuration",
}
SECTION_ORDER = list(SECTION_TITLES)
# Tours outside the sidebar sections (own menu entry, appended to the full walkthrough)
EXTRA_TOURS = {"analysis": "Analysis panel"}


def _group(control_id):
    """Selector for the sidebar control group that contains ``control_id``."""
    return f".control-group:has(#{control_id})"


def _card(control_id):
    """Selector for the Mask/Mosaic block that contains ``control_id``."""
    return f".section-body .card:has(#{control_id})"


def _steps(section, steps):
    return [{**step, "section": section, "side": step.get("side", "right")} for step in steps]


TOUR_STEPS = {
    "quick": [
        {"element": "#cluster-plot", "title": "Main plot", "side": "bottom",
         "body": "Pan and zoom the sky; click a cluster to open its actions."},
        {"element": "#view-mode-btn-group", "title": "View modes", "side": "bottom",
         "body": "Switch between the Standard scatter view and the Aladin sky view. "
                 "Aladin unlocks once you zoom to a single cluster."},
        {"element": "#render-button", "title": "Render", "side": "right",
         "body": "Draws the catalog for the selected algorithm. Afterwards it reads "
                 "\"Re-render\" and redraws everything for the current view."},
        {"element": "#clusters-settings-header", "title": "Sections", "side": "right",
         "body": "Controls are grouped into sections. Click a header to open it; the "
                 "? next to it gives a detailed tour of that section."},
        {"element": "#filters-settings-header", "title": "Filters", "side": "right",
         "body": "Redshift, SNR, richness, cluster-ID and matched-cluster options. "
                 "Changes wait for Apply filters at the bottom of the section."},
        {"element": "#mask-controls-header", "title": "Mask", "side": "right",
         "body": "High-resolution CATRED sources and the Healpix coverage mask."},
        {"element": "#image-controls-header", "title": "Mosaic", "side": "right",
         "body": "Survey imagery behind the clusters for the current zoomed view."},
        {"element": "#display-options-header", "title": "Display", "side": "right",
         "body": "MER tiles, polygon fill and aspect ratio. These update the plot immediately."},
        {"element": "#status-info-toggle", "title": "Status", "side": "left",
         "body": "Render results and errors appear here; click to restore it if minimized."},
        {"element": "#tutorial-tour-menu", "title": "More tours", "side": "bottom",
         "body": "Open this menu for the full walkthrough or a detailed tour of any one section. "
                 "The Getting Started guide (?) is always one click away."},
    ],
    "clusters-settings": _steps("clusters-settings", [
        {"element": _group("algorithm-dropdown"), "title": "Detection algorithm",
         "body": "PZWAV, AMICO, or both together. After changing it, press the main button "
                 "(\"Re-render · <algorithm>\") to draw the new catalog."},
        {"element": _group("cltile-info-switch"), "title": "CL-tile information",
         "body": "Colours each cluster by the CL-tile it came from and draws the tile outlines. "
                 "When individual tile data is missing the switch is disabled and the reason is shown below it."},
        {"element": _group("unmerged-clusters-switch"), "title": "Unmerged clusters",
         "body": "Adds clusters detected in individual tiles that did not make it into the merged catalog."},
    ]),
    "filters-settings": _steps("filters-settings", [
        {"element": _group("redshift-range-slider"), "title": "Redshift filter",
         "body": "Each range filter works the same way. This group limits clusters by redshift."},
        {"element": "#redshift-range-display", "title": "Selected range",
         "body": "Shows the range you chose against the full range in the data. "
                 "A \"Not applied\" tag appears here until you press Apply filters."},
        {"element": "#redshift-range-slider", "title": "Range slider",
         "body": "Drag either handle to narrow the range."},
        {"element": ".control-group:has(#redshift-range-slider) .row", "title": "Exact values",
         "body": "Type exact Min and Max values instead. They stay in sync with the slider; "
                 "values outside the data range are clamped."},
        {"element": "#redshift-include-missing", "title": "Missing values",
         "body": "Keep or drop clusters that have no redshift at all. Every range filter has this switch. "
                 "It is only enabled when some loaded clusters really lack the value; otherwise it is "
                 "greyed out and marked \"(none missing)\"."},
        {"element": "#snr-pzwav-container", "title": "SNR (PZWAV)",
         "body": "Signal-to-noise range for PZWAV clusters. Only the selected algorithm's SNR filter is shown."},
        {"element": "#snr-amico-container", "title": "SNR (AMICO)",
         "body": "Signal-to-noise range for AMICO clusters. Only the selected algorithm's SNR filter is shown."},
        {"element": "#richness-mode-radio", "title": "Richness estimate",
         "body": "Off by default. Rich-CL, the richness and membership code, gives two estimates: "
                 "ZP (photometric-redshift branch) and RS (red-sequence branch). Choose one to filter on; "
                 "its quality flags and range then appear below."},
        {"element": "#richness-zp-container", "title": "Richness (ZP)",
         "body": "Tick the quality flags to keep (0 with richness, 1 dubious, 2 no richness), "
                 "then set the richness range."},
        {"element": "#richness-rs-container", "title": "Richness (RS)",
         "body": "Tick the quality flags to keep (0 with richness, 1 dubious, 2 no richness), "
                 "then set the richness range."},
        {"element": _group("idcluster-upload"), "title": "Cluster-ID list",
         "body": "Upload a .txt, .csv or .dat file with one cluster ID per line (column 0 for .dat) "
                 "to show only those clusters. The line below confirms how many IDs were read; Clear removes the list."},
        {"element": _group("matching-clusters-switch"), "title": "Matched clusters",
         "body": "With PZWAV and AMICO selected, draws ovals around matched pairs in the current view. "
                 "The hint below tells you when the view is small enough; zoom in first."},
        {"element": "#apply-filters-button", "title": "Apply filters", "side": "top",
         "body": "Every filter above takes effect only when you press this. It stays disabled until "
                 "the first render and while the plot already matches your filters."},
        {"element": "#apply-filters-status", "title": "What will change", "side": "top",
         "body": "Lists the filters you changed since the last render, e.g. \"Changed: Redshift, SNR\". "
                 "Only the cluster markers are redrawn, so applying is quick."},
    ]),
    "mask-controls": _steps("mask-controls", [
        {"element": _card("catred-mode-switch"), "title": "Masked CATRED",
         "body": "When on, CATRED sources under the Healpix mask are hidden and the threshold and "
                 "magnitude controls below apply."},
        {"element": "#catred-threshold-container", "title": "Coverage threshold",
         "body": "Minimum effective coverage a source needs to be kept in masked mode."},
        {"element": "#magnitude-limit-container", "title": "Magnitude limit",
         "body": "Keeps sources brighter than this H-band magnitude."},
        {"element": "#catred-render-button", "title": "Render CATRED sources",
         "body": "Zoom in first, then load high-resolution CATRED sources for the view. "
                 "Clusters near CATRED sources are highlighted, and clicking a source shows its redshift PDF."},
        {"element": "div:has(> #catred-render-marker-color)", "title": "Marker colour",
         "body": "Changes the CATRED marker colour without reloading."},
        {"element": "#catred-toggle-visibility-button", "title": "Hide / Clear",
         "body": "Hide keeps the loaded sources but stops drawing them; Clear removes them."},
        {"element": "#mask-type-selector", "title": "Mask type",
         "body": "Corrected mask, or the effective-coverage mask."},
        {"element": "#mask-opacity-slider", "title": "Mask opacity",
         "body": "How strongly the mask overlay covers the plot."},
        {"element": "#healpix-mask-button", "title": "Load Healpix mask",
         "body": "Zoom in first, then load the coverage mask for the MER tiles in view."},
        {"element": "#mask-binary-inverted-toggle", "title": "Inverted mask",
         "body": "Shows the uncovered area instead of the covered one."},
        {"element": "#mask-toggle-visibility-button", "title": "Hide / Delete mask",
         "body": "Hide the mask temporarily, or delete it."},
    ]),
    "image-controls": _steps("image-controls", [
        {"element": "#image-source-radio", "title": "Image source",
         "body": "MER mosaics in the Standard view; Aladin sky surveys in the Aladin view."},
        {"element": "#aladin-survey-dropdown", "title": "Sky survey",
         "body": "Background survey shown in the Aladin view."},
        {"element": "#mosaic-enable-switch", "title": "Enable mosaics",
         "body": "Turn on to load background images for the Standard view."},
        {"element": "#mosaic-provider-selector", "title": "Provider and source",
         "body": "Local MER FITS tiles on disk, or ESA Sky public surveys online. "
                 "For ESA Sky, also pick the survey and the image format (FITS for quality, JPEG for speed)."},
        {"element": "#mosaic-opacity-slider", "title": "Mosaic opacity",
         "body": "Blend the image with the clusters drawn on top."},
        {"element": "#mosaic-render-button", "title": "Load mosaic",
         "body": "Zoom in below about 2° first, then load images for the MER tiles in view."},
        {"element": "#mosaic-toggle-visibility-button", "title": "Hide / Delete",
         "body": "Hide the images temporarily, or delete them."},
    ]),
    "display-options": _steps("display-options", [
        {"element": _group("mer-switch"), "title": "MER tiles",
         "body": "Draws MER tile outlines inside the CL-tiles. Needs CL-tile information switched on."},
        {"element": _group("polygon-switch"), "title": "Fill CL-tile polygons",
         "body": "Fills the CORE area of each CL-tile instead of drawing outlines only."},
        {"element": _group("aspect-ratio-switch"), "title": "Free aspect ratio",
         "body": "Off keeps true sky proportions. Display options update the plot immediately, "
                 "using your last applied filters."},
    ]),
    "app-config": _steps("app-config", [
        {"element": _group("config-merged-catalog"), "title": "Merged catalog",
         "body": "The merged cluster catalog this session loaded."},
        {"element": _group("config-detintile-list"), "title": "Tile detection list",
         "body": "The per-tile detection files behind the CL-tile information."},
        {"element": _group("gluematchcat-file-display"), "title": "GlueMatchCat file",
         "body": "The cross-match file in use. Browse picks another file on the server."},
        {"element": _group("gluematchcat-file-input"), "title": "Use another file",
         "body": "Or paste a path, then press \"Use this file\" to switch."},
    ]),
    "analysis": [
        {"element": "#analysis-tabs", "title": "Analysis panel", "side": "left",
         "body": "Two tabs: PHZ Analysis for redshift probabilities, Cluster Tools for the cluster you selected."},
        {"element": "#phz-inner-tabs", "title": "PHZ Analysis", "side": "left",
         "body": "CATRED source shows the p(z) of a CATRED source you click on the map; the panel switches "
                 "here automatically. Cluster data shows redshift and SNR distributions for the current view."},
        {"element": "#phz-pdf-plot", "title": "Redshift probability", "side": "left",
         "body": "The source's p(z) with its mode and median marked. Drag to zoom into a narrow peak."},
        {"element": ".tool-summary", "title": "Selected cluster", "side": "left",
         "body": "Click a cluster on the map to select it. Its position, redshift, SNR and merged ID stay "
                 "pinned here; copy the coordinates or Deselect."},
        {"element": ".tool-row:has(#tab-cutout-button)", "title": "Overlays", "side": "left",
         "body": "Image cutout, Healpix mask cutout, CATRED box and cluster members. Each opens its options "
                 "right below; Hide and Clear manage what you drew."},
        {"element": ".quick-tag-bar", "title": "Quick tagging", "side": "left",
         "body": "Tag the selected cluster Good, Bad or Dubious, or press G, B or D (not while typing in a field)."},
        {"element": ".tool-row:has(#tab-tag-panel-button)", "title": "Tagging and export", "side": "left",
         "body": "Add a dataset label, review the tagged list and save it as CSV. The path is remembered."},
    ],
}
