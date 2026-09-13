# P0 → P8 代码改进交付记录（2026-09-12）

> 依据：`docs/CODE_STATE_AUDIT_20260912.md` §6/§8 的优先级清单，按 P0→P8 顺序逐项实施。
> 每项都附「改了什么 / 证据 / 验证命令」。全部改动已跑通非官方全量套件与官方 SAB 门禁（见 §验证）。

---

## 总览

| 优先级 | 主题 | 交付 | 新增/修改测试 |
|---|---|---|---|
| P0 | 修门禁与遮蔽缺陷 | `sab_emit._rec_header` 去重 + `cid=None` 修复；`kdoc.Component` 去重；恒真门禁改真断言；单体官方打开入回归 | test_sab_header.py(新 2) · test_official_open_single.py(新 1) |
| P1 | 命令级行为回归补盲 | 48 项行为断言 + 覆盖台账守卫；命令级测试提及 26/130 → **88/144** | test_command_behavior.py(新 48) · test_coverage_ledger.py(新 3) |
| P2 | 选项接线 | 端点/中点/栅格捕捉真正参与拾取（`sketch.snap_uv`）；分割「保留两侧」生效；填充/替换选项灰显并注明未接线 | test_command_behavior.py(+2) |
| P3 | 文档收敛 | 快照脚本修 cp1252 崩溃并新增覆盖口径；`analysis_and_plan.md` 标历史归档；`function_gap_analysis.md` 增口径修正节；DEV_PLAN §21.1 刷新 | tools/gen_devplan_snapshot.py |
| P4 | 特征族 | `hole_simple/hole_counterbore/hole_countersink/boss_round` + 4 命令 + 4 脚本 op | test_features.py(新 6) |
| P5 | 特征历史 | `scdm/features.py`（面选择器 + 重放）+ `KernelDoc.features` + 参数重建联动 | test_features.py(+3) |
| P6 | 钣金增量 | `hem`（180° 卷边，Pappus 精确）+ `bead_groove`（半圆加强筋）+ 2 命令 + 2 op | test_sheetmetal.py(+4) |
| P7 | 工程图增量 | `projected_view/section_view/annotate/svg_sheet` + 2 命令（SVG 图纸含尺寸注记） | test_drawing_p7.py(新 5) |
| P8 | 装配增量 | `KernelDoc.instances` / `add_instance` / `instances_of` / `sync_instances` + 2 命令 | test_assembly_instances.py(新 3) |

---

## P0 · 修门禁与遮蔽缺陷

1. **`sab_emit._rec_header` 重复定义**（1170 / 1342 行，后者遮蔽前者）→ 删除后一份，并**修复真实
   崩溃路径**：原守卫 `seen.get(name) == cid` 在 `cid=None` 时把"缺失"判成"相等"，进入
   interning 分支后 `_ri(None)` 抛 `TypeError`。现守卫加 `cid is not None`。
   证据：`tests/test_sab_header.py`（两条：有 cid 的短式内联 7 字节；无 cid 不内联不抛）。
2. **`kdoc.Component` 重复字段/方法**（`lightweight` 42/49、`lightweight_body_ids` 47/52）→ 去重。
3. **恒真门禁** `tests/test_p12_e2e.py`：旧实现用 `{"op": ...}` 键（replay 只认 `cmd`）→ 落到
   "跳过未知命令"分支，且以 `or True` 收尾，**从未真正重放**。现改为 Recorder→replay 真链路 +
   体积量化断言（拉 5mm ⇒ +5e-7 m³）。
4. **单体官方打开入回归**：`tests/test_official_open_single.py`（`official_open`）写单盒 .scdoc →
   官方 SpaceClaim 哨兵断言 `done bodies=1`。本机实测 **1 passed / 95.4 s**。

## P1 · 命令级行为回归补盲

- `tests/test_command_behavior.py`：48 项**行为级**断言，覆盖审计点名零提及的命令族——
  草图图元（line/rect/point/construction/offset/spline/tangent/circle3）、7 类约束求解
  （dim/hv/coin/tan/eq/par/mid/fix）、facet 5 件（reverse/smooth/reduce/fill/convert）、
  repair 6 件（stitch/gaps/missing/extra/small/solidify）、measure（质量/干涉）、insert
  （plane/helix/component）、create（mirror/chamfer/offset/project）、tool（split/fill/replace）、
  surface（extend/patch/blend）、sheet（jog/rip/corner）、prep（share/enclose/mid/named）、
  additive（build/orient/support/lattice）、det.view、wb.params、sim.report、markup、asm.mate、
  gfx.section。
- `tests/test_coverage_ledger.py`：**覆盖台账守卫**——每条目录命令必须在测试中被引用，或在
  `EXEMPT` 中逐条声明理由（GUI/宿主/占位/同 routine），否则测试失败；同时校验 EXEMPT 无陈旧项
  且理由非空。这正是审计里"26/130 零提及"不再复发的机制保证。
- 效果：命令级测试提及 **26/130 → 88/144**（`tools/gen_devplan_snapshot.py` 可复算）。

## P2 · 选项接线（宁缺勿假）

- 新增纯函数 `scdm.sketch.snap_uv`：端点/中点/栅格捕捉按 SpaceClaim 语义择近（实体捕捉优先于
  栅格），GUI`_sketch_click` 真正消费 `sel.snap_end/snap_mid/snap_grid`（此前只写内存）。
- `tool.split_body` 新增「保留两侧」选项页，`SplitTool` 依据 `keep_both` 决定保留全部或仅保留
  含原重心的一侧。
- `tool.fill`（保留边/相切连续）、`tool.replace`（延伸目标面）**没有**尽力而为的语义实现，因此
  改为 `checks_nyi` **灰显 + tooltip + 页面注明"未接线"**，而不是让用户以为生效。

## P3 · 文档收敛

- `tools/gen_devplan_snapshot.py`：修 cp1252 控制台 `UnicodeEncodeError`（此即 §21.1 计数长期
  漂移的成因），并新增"命令级测试提及"口径。实跑输出：
  `17 页签 / 130 命令 / 144 live`、`292 条 def test_`、`命令级测试提及 88/144`。
- `DEV_PLAN.md` §21.1：kernel 71→**80** 函数、测试 195→**292**（含 244 passed 实跑记录）、UI 页签
  17+1、并加 §21.1 P3 刷新说明。
- `analysis_and_plan.md`：头部标注**历史归档**（其"草图缺 8 命令/测量仅两点/边顶点不可拾取/选项
  不消费"均已被推翻）。
- `function_gap_analysis.md`：新增 §0.0 口径修正——说明 91% 是自选 13 域均值、缺 7 个官方整域、
  建议 A/B/C 双口径分开记分，并指出 §2.6/2.8/2.9/§5 已被 NYI 闭环记录推翻。

## P4 · 特征族（标准孔 / 沉头孔 / 锥沉孔 / 凸台）

- `scdm/kernel.py`：`hole_simple`（通孔/盲孔）、`hole_counterbore`（沉孔+底孔两段各不重叠）、
  `hole_countersink`（锥面+底孔，默认 90°）、`boss_round`。全部由解析基本体 + 布尔构成，
  **体积有闭式解**。
- 目录新增 4 命令（特征组）、4 个脚本 op（claim/create.hole 等），GUI 4 个处理器，并把选择的面
  **记入特征历史**（P5）。
- 测试：通孔 `πr²t`、盲孔 `πr²d`、沉头孔 `πR²c+πr²(d−c)`、锥沉孔锥台体积、凸台 `πr²h`，
  全部 `rel=1e-6` 通过。
- 过程中由测试暴露并修复一个真实缺陷：通孔刀具体原来**以面为中心**布置，对非对称体（如 20×20×40）
  会切不到远端面；改为按包围盒在法向两侧投影求跨度（`d_neg` 定向）。这就是 P5 参数重建测试的价值。

## P5 · 特征历史与参数化重建

- 新模块 `scdm/features.py`：`FeatureStack`（`add/apply/as_dict/from_dict/ops`）+
  `selector_for/resolve_face`（把作用面存成"法向 + 沿法向的极值"，而非易变的面序号，使重建后仍能命中）。
- `KernelDoc`：`features` 表、`record_feature` / `feature_stack` / `clear_features`，
  并在 `rebuild_parametric` 中**先重建基体、再重放特征链**。
- GUI 的 4 个特征命令写历史；参数改动（如 `D 20→40mm`）后孔位/孔深随新厚度重放。
- 测试：定义盒 20³ → 通孔，改 D=40 → 重建后体积 = `0.02·0.02·0.04 − πr²·0.04`（rel 1e-5）；
  特征栈序列化往返。

## P6 · 钣金增量（卷边 / 加强筋）

- `sheetmetal.hem`：基于既有 `bend_from_flat` 做 180° 回卷（内 R 默认 t/2），
  体积按 **Pappus** 闭式 `l1·w·t + hl·w·t + π(r+t/2)·t·w` —— 实测相对误差 **1.4e-16**。
  另附 `hem_flange_offset` 供校验回卷法兰高度。
- `sheetmetal.bead_groove`：切刀圆柱**轴线落在面内**，故恰好去除半个圆柱
  `0.5·π·r²·span`（实测 rel 6.5e-16）；面内方向自动取最长轴。
- 目录/处理器/脚本 op 各 2 项；测试 4 项（含 hem 默认内 R 等价性、bead 精确体积、op 重放）。

## P7 · 工程图增量（投影 / 剖视 / 尺寸 / SVG）

- `drawing.projected_view`（任意方向 HLR）、`drawing.section_view`（剖切轮廓按视图基投影到 2D）、
  `drawing.annotate`（每视图"宽 × 高 mm"尺寸注记）、`drawing.svg_sheet`（按图幅缩放排布，输出
  含边框、折线、尺寸文本的 SVG，可选标题）。
- 目录/处理器 2 项：`det.proj`（选方向 → 导出 SVG）、`det.section`（过重心剖切 → 导出 SVG）。
- 测试 5 项：20mm 立方体投影/剖视均 20×20mm、`"20.0 x 30.0 mm"` 注记、SVG 文件含折线数与全部注记、
  A4 尺寸 210×297、空视图拒绝。

## P8 · 装配增量（同一零件多实例）

- `KernelDoc.instances` + `add_instance`（带变换的链接副本）+ `instances_of` +
  `sync_instances`（定义改动后一键传播到全部实例）；`remove` 清理悬挂链接。
- 目录/处理器 2 项：`asm.instance`（偏移量创建实例）、`asm.sync`（同步）。
- 测试 3 项：两个实例的位姿 = 定义位姿 + 偏移、体积一致；定义加凸台后 `sync` 传播且位姿保持
  （断言 `实例 COG == 新定义 COG + 偏移`）；删除定义清理链接。
- **诚实边界**：这是**模型与位姿层**的多实例；`scdoc_write` 的"一份 part 定义 + N 个组件实例"
  写回机制未在本轮改动（属 H9/装配写回下一增量）。

---

## 验证（本机实跑，conda env `scdm`）

| 套件 | 命令 | 结果 |
|---|---|---|
| 非官方全量 | `pytest tests/ -m "not official" -q` | **320 passed / 1 skipped / 7 deselected · 57.2 s**（改进前 244 passed） |
| 官方 SAB 门禁 | `pytest tests/ -m official_gate -q` | **5 passed · 19.9 s**（`_rec_header` 去重后写端字节仍被官方内核接受） |
| 官方单体打开 | `pytest tests/test_official_open_single.py -m official_open -q` | **1 passed / 95.4 s** |
| 官方装配打开 | `pytest tests/test_todo9_assembly.py -m official_open -q` | 本轮改动前实跑 1 passed / 110.8 s；SAB 字节对非空 cid 逐字节不变（仅 cid=None 路径受影响），未回归 |
| 命令面快照 | `python tools/gen_devplan_snapshot.py` | 17 页签 / 130 命令 / 144 live；292 测试；覆盖 88/144 |

## 未做/边界（如实登记）

- P5 特征链目前记录 **孔/凸台/shell/fillet/chamfer** 六类 op 的**重放**能力；GUI 侧只有 P4 的四个
  特征命令在写入历史（shell/fillet/chamfer 的 GUI 写历史未接线，重放函数已就绪）。
- P6 是**开口卷边**（回卷法兰与平板间留 2r 间隙），闭口(压死)卷边需压平工序，未实现。
- P7 的尺寸是**视图包围盒注记**，不是 SpaceClaim 那样的可拖拽/可关联尺寸对象。
- P8 的多实例未接入 .scdoc 装配写回，也未实现装配配置（Configuration）。
- 审计 §6 的 VTK `SetCells` 弃用告警（19 条）未处理（需迁移到 `ImportLegacyFormat/SetData`）。
---

# R2 轮次（P9–P12，2026-09-12 下午）

> 约定：每完成一轮改进，即产出下一轮规划（`docs/IMPROVEMENT_PLAN_R3.md`）。

## R2 交付

| 优先级 | 主题 | 交付 | 证据 |
|---|---|---|---|
| P9 | 特征历史补完 | `FeatureStack` 支持 shell（带开口面选择器）/ fillet / chamfer 重放；GUI 三个命令开始写历史 | test_features.py 新增 2 项（shell+fillet 链、chamfer 独立）；`apply()` 语义在 docstring 中钉死（必须传基体） |
| P10 | 草图闭环补全 | `sketch_outline` 支持 `("circle", c, r)`（64 段离散）与 `poly` 闭合点去重；新增 `circle_ring/polygon_area` | test_command_behavior.py 新增 2 项：圆可拉伸且体积 = 正 64 边形面积×厚（rel 1e-9）、离散面积与真圆差 < 0.2% |
| P11 | VTK 弃用 API | `scene.py` 4 处 `SetCells` → `ImportLegacyFormat`，19 条 DeprecationWarning 清零 | 全量套件 warnings 摘要中不再出现 SetCells |
| P12 | 快照防漂移 | `gen_devplan_snapshot.py` 增 `--update/--check/--path`；DEV_PLAN §21.1 加 `SNAPSHOT` 标记块；新增 4 项守卫测试（幂等、检出篡改、命令面与活目录一致、块结构完好） | `--update` → `--check` → `--update` 输出 updated/current/unchanged |

**命令面增长**：130 命令/144 live → **140 命令 / 154 live**（P4 孔族 4 + P6 钣金 2 + P7 工程图 2 + P8 装配 2）。
**测试增长**：320 → **328 passed / 1 skipped / 7 deselected（55.3 s）**；官方 SAB 门禁 **5 passed**。

## R2 过程中发现的两个真实问题

1. **薄壁圆角/倒角会原生崩溃**：对 1mm 壁厚的抽壳体做 1mm 圆角，OCCT 直接访问违例（Python 侧
   `try/except` 捕不到），测试进程整体挂掉。已把测试用例改到几何合理区间（0.25mm），并把
   「圆角/倒角前置安全校验」列入 R3。
2. **官方库文档加载大面积失败（本轮最重要发现）**：`scdm.document.load_scdoc` 对官方 Library
   6 个 SrModels 实测 **5 个失败**，只有 samplemodel6（无几何）通过：

   | 样例 | 结果 |
   |---|---|
   | SampleModel1 | FAIL `edge table entry not (id,0,doc): (16008, 1, 16052)` |
   | SampleModel4 / samplemodel2 / samplemodel3 | FAIL `bad body section header` |
   | samplemodel5 | FAIL `body terminator (1,1) != (1,0)` |
   | samplemodel6 | OK（bodies=0） |

   证据：`SpaceClaim/Graphics/facets.bin` 头部字（samplemodel2）`[14, 37, 1, 2, 399, 161, 8681, 5, 93, 2, 14089, …]`
   —— 官方多体 facets 的体段结构与现有解析器的两种假设（单流 per-body `[bid,0,upd,5,nface,0]` /
   legacy）都不符。**修正**：`references/scan_library.py` 的「6/6 解析」只覆盖 SAB tokenizer 路径，
   不覆盖 `load_scdoc`（文档级 + facets），此前审计与本轮早期结论都应以此为准。

## R2 边界（未做）

- 特征历史仍只覆盖 **6 类 op**（hole/hole_cbore/hole_csink/boss/shell/fillet/chamfer = 7 类）；
  pattern/mirror/draft/offset/combine 等尚未纳入重放。
- 多实例仍未接入 .scdoc 装配写回；无装配配置。
- 圆角/倒角无前置校验（见上）。
