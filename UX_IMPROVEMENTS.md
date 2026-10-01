# ClusterViz UX Improvements

Tracking checklist from the 2026-09-30 UX audit. Check items off as completed.

## Onboarding
- [ ] ~~Surface the SSH tunnel command + assigned port in the browser UI~~ — rejected: page is only reachable after the tunnel is already up, so an in-browser banner tells the user nothing new (chicken-and-egg). Console print at startup remains the right place for this.
- [x] Add an in-app "Getting Started" card/modal for first-time users (replaces reading 10 separate docs)
- [x] Add an interactive guided tour ("Tutorial" button, driver.js) that walks through the plot, view toggle, Render, Catalog, Filters, Mask, Mosaic, Display, status toast and Getting Started
- [x] Layered tours — Tutorial menu offers a quick tour, a full walkthrough, or one section in detail; a "?" next to each section header tours that section control by control. One engine and one step list (`ui/tour_steps.py`); sections open for the tour and are restored after; hidden variant controls are skipped

## Status feedback visibility
- [x] Reposition `status-info` alerts as a floating/fixed toast (top-right) instead of bottom-of-page div
- [ ] (optional) Auto-dismiss status alerts after N seconds

## Sidebar information architecture
- [x] Default-open the Catalog and Filters sections; Configuration moved to the last section
- [ ] ~~Add summary badges to collapsed section headers (e.g. current SNR/z range)~~ — implemented then reverted: badge text kept getting cut off, removed entirely
- [x] Make "Configuration" (formerly "App Configuration") an actual dedicated control section — merged the browse/edit/apply controls for the GlueMatchCat XML path (previously a separate, easy-to-miss "File Config" tab) directly into the sidebar card; Tile Detection List stays read-only (no apply pipeline existed for it)

## Manual render/apply workflow
- [x] Unapplied-changes indicator — one sticky "Apply filters" button replaces the per-filter Apply buttons; it lists what changed ("Changed: Redshift, SNR") and every pending control shows a "Not applied" tag
- [ ] ~~Consider auto-apply-on-release (debounced) for clientside-only filters~~ — decided against: filters (including switches, richness mode, flags, ID list and matched clusters) apply only on the explicit "Apply filters" action; Display options stay live and use the last-applied filters
- [x] Selected-range readout ("a – b of min – max") and synced Min/Max number inputs on every range slider
- [x] Incremental Apply — only cluster traces are rebuilt and patched into the figure (`dash.Patch`), without the background-render fork or a full redraw
- [x] Full Re-render keeps CATRED, mosaic and mask overlays

## Visual design
- [x] Quiet visual redesign — gradients, emoji headers and perpetual animations removed; token-based neutral palette, one accent, flat sections, visible focus rings, reduced-motion support
- [x] Responsive sidebar — fixed ~300–380 px column beside the plot on desktop, stacks above it below 992 px
- [x] Main button names its action: "Render clusters", then "Re-render · <algorithm>" (no click counters)

## Disabled / dead-end controls
- [ ] Resolve duplicate cluster-action UI: `Modals.create_cluster_action_modal()` vs `AppLayout._create_cluster_action_modal()` (tab version) have inconsistent enabled/disabled feature sets — pick one source of truth
- [ ] Wire up or remove dead ESASky view-mode toggle (code exists in `esasky_callbacks.py` but not exposed in header toggle)
- [ ] Standardize "why is this disabled" explanation pattern (currently inconsistent small-text captions) into one reusable popover component

## Numeric control context
- [ ] Add live low-cost preview (e.g. cluster/source count passing filter) next to Coverage Threshold / Magnitude Limit / redshift bin width sliders

## Search / navigation
- [ ] Add a quick-jump-to-cluster input (RA/Dec or cluster ID → pan+zoom) as an alternative to zoom-and-click or CSV ID upload
