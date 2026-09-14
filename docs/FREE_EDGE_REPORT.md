# 自由边分类（R75/P371 当前状态）

复算：`python tools/free_edge_report.py --md docs/FREE_EDGE_REPORT.md`

| 样例 | 自由边 | 其中缝边 | 真缺口 | 曲线类型 | 相邻曲面类型 | 端点延续 | 零长 | 中位长 | 最长 |
|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `SampleModel4.scdoc` | 363 | 16 | 347 | bspline=90, circle=89, ellipse=23, line=161 | bspline=53, cone=5, cylinder=48, plane=169, torus=88 | chain=297, half=51, isolated=15 | 0 | 0.00681 | 0.317 |
| `samplemodel2.scdoc` | 1083 | 81 | 1002 | bspline=100, circle=222, ellipse=392, hyperbola=100, line=221, other=48 | bspline=4, cone=176, cylinder=445, plane=300, sphere=48, torus=110 | chain=835, half=179, isolated=69 | 48 | 0.0687 | 3.29 |
| `samplemodel3.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel5.scdoc` | 0 | 0 | 0 |  |  |  | 0 | 0 | 0 |
| `samplemodel6.scdoc` | 3 | 0 | 3 | ellipse=3 | cylinder=2, plane=1 | chain=3 | 0 | 0.157 | 0.313 |
