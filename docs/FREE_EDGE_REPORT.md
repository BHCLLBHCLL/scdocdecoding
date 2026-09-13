# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 36 | 0 | 36 | ellipse=32, line=4 | cylinder=24, plane=12 | chain=4, half=24, isolated=8 | 0 | 0.00348 | 0.00559 |
| `SampleModel4.scdoc` | 386 | 18 | 368 | bspline=88, circle=98, ellipse=32, line=168 | bspline=55, cone=5, cylinder=58, plane=181, torus=87 | chain=358, half=23, isolated=5 | 0 | 0.00577 | 0.317 |
| `samplemodel2.scdoc` | 1494 | 34 | 1460 | bspline=111, circle=373, ellipse=570, hyperbola=100, line=340 | bspline=4, cone=176, cylinder=709, plane=398, sphere=96, torus=111 | chain=1293, half=149, isolated=52 | 0 | 0.0648 | 3.29 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 2 | 0 | 2 | circle=1, ellipse=1 | cylinder=1, plane=1 | chain=2 | 0 | 0.313 | 0.313 |
