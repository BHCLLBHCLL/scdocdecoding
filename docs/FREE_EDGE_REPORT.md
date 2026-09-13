# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 36 | 0 | 36 | ellipse=32, line=4 | cylinder=24, plane=12 | chain=4, half=24, isolated=8 | 0 | 0.00348 | 0.00559 |
| `SampleModel4.scdoc` | 403 | 18 | 385 | bspline=90, circle=93, ellipse=33, line=187 | bspline=55, cone=5, cylinder=50, plane=204, torus=89 | chain=373, half=26, isolated=4 | 0 | 0.0068 | 0.317 |
| `samplemodel2.scdoc` | 1427 | 34 | 1393 | bspline=119, circle=355, ellipse=564, hyperbola=100, line=289 | bspline=4, cone=176, cylinder=678, plane=362, sphere=96, torus=111 | chain=1227, half=149, isolated=51 | 0 | 0.0687 | 3.29 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 2 | 0 | 2 | circle=1, ellipse=1 | cylinder=1, plane=1 | chain=2 | 0 | 0.313 | 0.313 |
