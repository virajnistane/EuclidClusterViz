# ClusterViz UX Improvements

Tracking checklist from the 2026-09-30 UX audit. Check items off as completed.

## Onboarding
- [ ] ~~Surface the SSH tunnel command + assigned port in the browser UI~~ — rejected: page is only reachable after the tunnel is already up, so an in-browser banner tells the user nothing new (chicken-and-egg). Console print at startup remains the right place for this.
- [x] Add an in-app "Getting Started" card/modal for first-time users (replaces reading 10 separate docs)

## Status feedback visibility
- [x] Reposition `status-info` alerts as a floating/fixed toast (top-right) instead of bottom-of-page div
- [ ] (optional) Auto-dismiss status alerts after N seconds

## Sidebar information architecture
- [ ] Default-open "Detected Clusters" section instead of "App Configuration"
- [ ] Add summary badges to collapsed section headers (e.g. current SNR/z range) so state is visible without expanding

## Manual render/apply workflow
- [ ] Add "N unapplied changes" indicator near Apply buttons (SNR/redshift/CATRED/mosaic)
- [ ] Consider auto-apply-on-release (debounced) for clientside-only filters (threshold slider already has clientside callback)

## Disabled / dead-end controls
- [ ] Resolve duplicate cluster-action UI: `Modals.create_cluster_action_modal()` vs `AppLayout._create_cluster_action_modal()` (tab version) have inconsistent enabled/disabled feature sets — pick one source of truth
- [ ] Wire up or remove dead ESASky view-mode toggle (code exists in `esasky_callbacks.py` but not exposed in header toggle)
- [ ] Standardize "why is this disabled" explanation pattern (currently inconsistent small-text captions) into one reusable popover component

## Numeric control context
- [ ] Add live low-cost preview (e.g. cluster/source count passing filter) next to Coverage Threshold / Magnitude Limit / redshift bin width sliders

## Search / navigation
- [ ] Add a quick-jump-to-cluster input (RA/Dec or cluster ID → pan+zoom) as an alternative to zoom-and-click or CSV ID upload
