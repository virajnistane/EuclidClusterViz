---
target: analysis tabs
total_score: 16
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:/home/nviraj/Work/euclid/remote/ClusterViz/cluster_visualization/ui/tabs.py"
target_fingerprint: "sha256:330ccd84063f2f0e0ff10271847bb8c1112d1872e8d9eadb124fcd0b8aad7918"
target_path: /home/nviraj/Work/euclid/remote/ClusterViz/cluster_visualization/ui/tabs.py
timestamp: 2026-10-01T20-44-43Z
slug: cluster-visualization-ui-tabs-py
---
Method: dual-agent (A design review, B detector + mechanical scan); source-only, no browser.

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 2 | CATRED click updates a p(z) plot on a hidden sub-tab; Cluster Data plots stale until Refresh |
| 2 | Match System / Real World | 2 | Raw column names; ZP/RS/PMEM/H★ undefined; "MER data point above" hint wrong |
| 3 | User Control and Freedom | 2 | Cluster click forces Cluster Tools; no deselect; no clear-all |
| 4 | Consistency and Standards | 1 | Clashes with redesigned sidebar; collapses open in different places; duplicate modal |
| 5 | Error Prevention | 2 | Cutout size / bin width accept 0; tag defaults to good |
| 6 | Recognition Rather Than Recall | 2 | Selected-cluster card scrolls away; silent sidebar sync |
| 7 | Flexibility and Efficiency | 1 | Tagging 3+ clicks; no shortcuts; CSV path re-typed |
| 8 | Aesthetic and Minimalist Design | 1 | Rainbow buttons, mirror helper text, nested cards |
| 9 | Error Recovery | 2 | Raw exception in red in PHZ plot |
| 10 | Help and Documentation | 1 | No tour/tooltips for tabs |
| **Total** | | **16/40** | **Poor** |

Priority issues: [P0] CATRED click -> p(z) invisible (inner tab default cluster subtab, no active_tab output); [P1] style clash with sidebar; [P1] Cluster Tools structure/copy; [P1] jargon + 22 unnamed inputs; [P2] duplicate modal, nested 75vh/60vh scroll, narrow-width squeeze.
Detector: 0 findings (Python markup not scanned). Mechanical: 6 emoji labels, 12 semantic-colour buttons, 20/20 labels without htmlFor, 7 nested cards, fixed vh heights.
