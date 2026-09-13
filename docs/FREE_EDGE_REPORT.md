# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 36 | 0 | 36 | ellipse=32, line=4 | cylinder=24, plane=12 | chain=4, half=24, isolated=8 | 0 | 0.00348 | 0.00559 |
| `SampleModel4.scdoc` | 405 | 18 | 387 | bspline=87, circle=98, ellipse=32, line=188 | bspline=56, cone=5, cylinder=58, plane=199, torus=87 | chain=384, half=15, isolated=6 | 0 | 0.0044 | 0.317 |
| `samplemodel2.scdoc` | 2227 | 82 | 2145 | bspline=10, circle=557, ellipse=805, hyperbola=100, line=755 | bspline=4, cone=176, cylinder=1208, plane=632, sphere=96, torus=111 | chain=1728, half=395, isolated=104 | 0 | 0.0604 | 3.29 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 2 | 0 | 2 | circle=1, ellipse=1 | cylinder=1, plane=1 | chain=2 | 0 | 0.313 | 0.313 |
