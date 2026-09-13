# 改进规划 R83（2026-09-12 立，R82 收尾后重新基线）

> 规则：每完成一轮改进重新基线并产出**下一编号**规划——本文件是 R83。
> R82 交付见 `docs/ROUND_R82_20260912.md`（裁剪修复候选 V2/V3/V5；SampleModel1 首次完全封闭）。

## 1. R83 起点基线（R82 实测）

| 口径 | 实测 |
|---|---|
| 真缺口 / 自由环 | **SampleModel1 0/0（封闭）**、SampleModel4 375/86、samplemodel2 1272/359、samplemodel3 0/0、samplemodel5 0/0、samplemodel6 3/2 |
| 缝边（非缺口） | 0 / 18 / 34 / 0 / 0 / 0 |
| 面数保真 | 5/6 样例完全一致；SampleModel4 149/177（ref 25/27） |
| 裁剪率 | SampleModel1 38/38、samplemodel5 132/132、samplemodel6 6/6（策略表 T/T/T/F/T/T） |
| 导入耗时 | 1.51 / 1.69 / 7.56 / 0.11 / 2.82 / 0.10 s |
| 占位命令 | 2 条（`prep.small`、`safety.tab`） |
| 测试 | 全量 CI 口径全绿（**637 passed, 2 skipped, 8 deselected**）；`def test_` 扫描 620 条 |

## 2. R83 工作项：P402 产品面 · 几何体检接上未封闭度

现状：`repair.check`（检查几何）已有 H4 全项检出 + 一键修复，但**不含** R75–R82 立起来的未封闭度口径
（真缺口 / 缝边 / 自由环）。本轮把它接上，**不新增命令**（避免同一事实两处实现，纪律 84）：

- `scdm/kernel.py`：`watertight_report(shape)`（free/open/seam/loops 四元组）与 `open_edge_points(shape, limit)`（缺口中点，供标记）；
- `scdm/scripting.py` `op_repair_check`：脚本侧报告未封闭度；`opts["mark"]` 时在缺口中点插 3D 标记便签（复用既有 markup 管线，标记天然不可拾取且不入包围盒）；
- `scdm_gui.py` `_do_repair_check`：状态栏/对话框带上未封闭度，并可选插标记；
- `scdm/catalog.py`：命令 note 注明"含未封闭度（缺口/缝边/自由环）"。

**验收**：脚本 op 的计数与 `K.open_edges`/`_free_boundary_wires` 独立复算一致；
标记数量 = min(缺口数, limit) 且标记不可拾取、不入包围盒（沿用场景既有双保险）；回放测试可重放。**成本**：0.5–1 天。

## 3. P403 · 每轮维护（必做）｜P404 · 后续候选

- P403 快照/CI/口径同步 + 编号递增 + 轮次记录同轮补齐（纪律 65）；
- P404 候选：未封闭度剩余项（SampleModel4 375/86、samplemodel2 1272/359 的逐类定位）、装配爆炸图第二批、
  型材库标准规格表、图面尺寸链第三批、占位命令 `prep.small`。

## 4. 纪律（延续）

1–89 条延续。
