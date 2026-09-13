# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `SampleModel4.scdoc` | 393 | 18 | 375 | bspline=91, circle=87, ellipse=30, line=185 | bspline=55, cone=5, cylinder=44, plane=200, torus=89 | chain=365, half=24, isolated=4 | 0 | 0.0068 | 0.317 |
| `samplemodel2.scdoc` | 1306 | 34 | 1272 | bspline=100, circle=323, ellipse=540, hyperbola=100, line=243 | bspline=4, cone=176, cylinder=602, plane=317, sphere=96, torus=111 | chain=1104, half=151, isolated=51 | 0 | 0.0687 | 3.29 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 3 | 0 | 3 | ellipse=3 | cylinder=2, plane=1 | chain=3 | 0 | 0.157 | 0.313 |
