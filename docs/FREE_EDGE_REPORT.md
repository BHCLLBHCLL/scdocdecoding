# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 56 | 0 | 56 | circle=10, ellipse=42, line=4 | cylinder=34, plane=22 | chain=24, half=24, isolated=8 | 0 | 0.00486 | 0.0375 |
| `SampleModel4.scdoc` | 423 | 18 | 405 | bspline=87, circle=109, ellipse=35, line=192 | bspline=56, cone=5, cylinder=68, plane=207, torus=87 | chain=402, half=15, isolated=6 | 0 | 0.00562 | 0.317 |
| `samplemodel2.scdoc` | 2325 | 73 | 2252 | bspline=10, circle=729, ellipse=712, hyperbola=100, line=774 | bspline=4, cone=176, cylinder=1258, plane=685, sphere=96, torus=106 | chain=1827, half=393, isolated=105 | 0 | 0.0687 | 6.16 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 2 | 0 | 2 | circle=1, ellipse=1 | cylinder=1, plane=1 | chain=2 | 0 | 0.313 | 0.313 |
