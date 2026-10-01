---
target: sidebar control section
total_score: 15
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:/home/nviraj/Work/euclid/remote/ClusterViz/cluster_visualization/ui/sidebar_sections.py"
target_fingerprint: "sha256:548072c0523e5ba11bf503ba158f8b1a5b102be0d29243219baea7cc2fdb8eff"
target_path: /home/nviraj/Work/euclid/remote/ClusterViz/cluster_visualization/ui/sidebar_sections.py
timestamp: 2026-10-01T13-24-39Z
slug: cluster-visualization-ui-sidebar-sections-py
---
Method: dual-agent (A: design review · B: detector + browser). Both source-only; browser blocked by plan mode.

## Design Health Score
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 1 | Badges show data bounds, not selected cut; hover-only tooltips; click counters in labels |
| 2 | Match System / Real World | 2 | ZP/RS, MER/LEV2 unexplained |
| 3 | User Control and Freedom | 1 | No filter reset; algorithm switch wipes SNR/z cuts |
| 4 | Consistency and Standards | 1 | Chevron flips, Redshift label/icon changes post-callback, shared icons |
| 5 | Error Prevention | 2 | Apply disabled pre-render without reason; upload accepts any file |
| 6 | Recognition Rather Than Recall | 1 | Collapsed sections show no active-filter summary |
| 7 | Flexibility and Efficiency | 1 | No numeric entry, presets, shortcuts |
| 8 | Aesthetic and Minimalist Design | 1 | Gradient card per control, emoji, perpetual animations |
| 9 | Error Recovery | 2 | Raw exception text on upload error |
| 10 | Help and Documentation | 3 | Modal + tour exist; Mosaic tour copy wrong |
| **Total** | | **15/40** | **Poor** |

## Design Specificity Verdict
Generic Bootstrap/Dash sidebar with AI-dashboard styling (purple gradients, emoji, pulse, gradientShift, shimmer). Color decorative; science filters styled as red danger. Detector: 1 finding, layout-transition at enhanced_styles.css:197 (toast, outside sidebar). Detector does not parse Python Dash; `transition: all` rules at css 29/66/118/291/374 and `transition: left` at 140 unscanned.

## Priority Issues
- [P0] Richness radio defaults "none" (sidebar_sections.py:443) but ZP container visible (:657), None hidden (:687); clientside sync prevent_initial_call=True (ui_callbacks.py:1665). Fix initial styles/drop prevent_initial_call. /impeccable harden
- [P1] Selected cut invisible: badges show data bounds; hover-only tooltips. Show "Selected a–b (of min–max)", numeric inputs, unapplied state. /impeccable clarify
- [P1] Apply model incoherent: 5 Apply + Render + main render, all identical purple via .btn-enhanced !important; click counters; "real-time" banner contradiction. /impeccable distill
- [P1] dbc.Col(width=2) (layout.py:144) at all breakpoints: ~65px at 390. Responsive widths. /impeccable adapt
- [P2] IA: Detected Clusters ~20 controls; orphaned Spec-z section; aspect default contradicts help; Re-render vs Render copy. /impeccable layout

## Persona Red Flags
Alex: no numeric entry/presets/export; algorithm switch wipes cuts; collapse state not persisted.
Sam: html.Label without htmlFor; RangeSlider no aria-label; collapse toggles lack aria-expanded; emoji read aloud; icon-only Browse; no reduced-motion guard; low-contrast help text.
Astronomer: cannot cite cuts or N; ZP/RS unexpanded; flag semantics unexplained; danger red on filters.

## Minor Observations
Radius/gradient-angle drift; me-0 icon spacing; dead _create_mosaic_controls_section (layout.py:476-640); debug print (ui_callbacks.py:230); leading spaces in flag labels; colon inconsistency.

## Questions to Consider
- Can a methods-section reader reconstruct the selection from a sidebar screenshot?
- Why per-filter Apply when plot re-renders live?
- What is lost if every gradient, emoji, animation goes?
