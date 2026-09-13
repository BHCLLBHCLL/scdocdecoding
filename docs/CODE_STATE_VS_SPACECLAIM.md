# 代码状态 × SpaceClaim 对标分析（2026-09-12 实测）

> **方法**：本机实跑代码 + 本机安装的 **ANSYS SpaceClaim 2019 R3（v195）** 官方二进制/资源/真实
> journal 作为对照基线；所有数字给出处，§9 附可复现命令。与既有文档冲突处一律以本次实测为准，
> 冲突清单见 §7。
>
> 关联文档：[function_gap_analysis.md](../function_gap_analysis.md)（2026-09-05 双口径，本报告对其
> 域清单口径提出修正）、[docs/IMPROVEMENT_PRIORITIES.md](IMPROVEMENT_PRIORITIES.md)、
> [docs/NYI_INVENTORY.md](NYI_INVENTORY.md)、[DEV_PLAN.md](../DEV_PLAN.md) §21。

---

## 0. 结论摘要

1. **真正到生产级的是格式层与官方互操作**：scdoc 读端 22 类 SAB 记录字段级解码，官方 Library
   6/6 样例全解析（最大 80 体 / 1,813 面 / 9,060 coedge）；写端以逆向 `SpaACIS.dll` 得到的
   FIFO 保存遍历算法产出官方可开文件（单体 bodies=1、装配 bodies=2）并过官方 SabSatConverter
   门禁。这一层是**唯一与官方对等**的部分（L2+～L3-）。
2. **命令面广度约为官方的 1/5**：我们 130 条目录命令 vs 官方 Commands.dll 内 **688 个
   `*Command` 类**（剔除设置/对话框/内部类后 **602**）。粒度不可逐条对齐，但量级差距明确。
3. **缺的是整域而不是零散命令**：梁/焊件（官方 43 个命令类 + 37 个 API 类型）、标准孔/螺纹/
   成形特征（101 个 API 类型）、CAE 网格与分析（90 个命令类 + 70 个 API 类型）、工程图标注体系
   （132 个 API 类型）、制造/去毛刺、装配配置、命名视图、参考图像——在我们这里**没有对应能力**。
4. **深度短板是结构性的**：无设计历史/特征树（undo = 形状快照，`history.py` 46 行）；参数化只有
   box/cylinder 两个构造器（`params.py`），"参数驱动重建"目前是门面而非机制；装配是扁平
   `Component(body_ids)` 列表，无 PartDef/实例/配置。对照官方 API 中 55 个 feature-track /
   smart-variable / script-block 类型，这条鸿沟不是补命令能补的。
5. **自评「整体 ≈91%」需要重定基线**：该数字是 13 个自选功能域的算术均值，域清单里**没有**梁/焊件、
   孔/螺纹/成形、CAE 网格、制造、装配配置、命名视图、PMI 等官方整域。建议改为**双口径分开记分**
   （§6）。

---

## 1. 实测基线（我们的代码，2026-09-12）

| 维度 | 实测值 | 备注 |
| --- | --- | --- |
| Python 规模 | **26,262 行 / 89 文件** | 不含 `references/disasm` 逆向脚本、`_tmp`、缓存 |
| 包结构 | `scdm` 37 模块 / **197 个模块级公开函数** | AST 统计 |
| 最大文件 | `scdm_gui.py` 4,208 行 · `scdoc_write.py` 2,012 · `sab_emit.py` 1,725 · `gui/scene.py` 1,575 · `kernel.py` 1,468 · `gui/icons.py` 1,114 | 均有继续增长趋势 |
| 大函数 | **16 个 ≥100 行**（最长 `icons._draw` 963 行、`_assembly_document_xml` 421 行） | 维护性风险 |
| 内核能力 | `kernel.py` **80 个公开函数**（DEV_PLAN §21.1 记 71，已漂移）：基本体×5、布尔、变换、阵列（线性/圆周/路径/填充）、镜像、分割、圆角（含变半径）、倒角、抽壳（含多厚度）、拔模（含中性面）、填充、偏移、螺旋、中面、共享拓扑、干涉/体积/面积/重心、STEP/IGES/STL/OBJ/3MF/VRML/BREP 读写、离散 | OCCT 7.9.3 |
| GUI 命令面 | **17 ribbon 页签 + 1 backstage = 18**；**130 条目录命令**；live 全集 **144**（含 16 条 backstage）；占位 **2**（`prep.small`、`safety.tab`）；`_do_*` handler **123** 个 | `scdm/catalog.py` 实测 |
| 图标 | 105 个矢量图标 | `gui/icons.py` |
| 测试 | **244 passed / 1 skipped / 6 deselected，86 s**（conda env `scdm`，GUI offscreen）；`def test_` 236 条 / 27 文件 | 本次实跑，全绿 |
| 数据层 | 官方 Library `SrModels` **6/6 解析成功**：SampleModel1 109 面 / samplemodel2 37 体 1,813 面 9,060 coedge / samplemodel5 80 体 1,288 面；`DrawingFormats` 15 个图幅样例无几何（预期） | `references/scan_library.py` 实跑 |
| 官方门禁可用性 | `SabSatConverter.exe` 与 `SpaceClaim.exe` 均在装 → `official_gate` / `official_open` 可在本机跑 | `tests/conftest.py` 路径 |
| 在途改动（未提交） | 6 文件：`gui/icons.py`(+994/-589)、`gui/viewport.py`(+183/-14)、`gui/theme.py`、`gui/ribbon.py`、`gui/left_panel.py`、`tests/test_smoke.py`(+24) —— **GUI 观感/密度打磨（对齐 SpaceClaim Office2016 外观）+ 12 处冒烟断言** | `git diff` |

**结论**：当前工作树处于「P0/P1/P2 全闭环 + GUI 观感打磨在途」状态；测试可复跑且全绿；
工程纪律（能力门禁、官方哨兵、边界项入册）是本仓库最强的一环。

---

## 2. 官方对照基线（本机 SpaceClaim 2019 R3 实测）

| 来源 | 实测数值 |
| --- | --- |
| `Commands.dll`（6.3 MB） | **2,806 类型**；**692 个 `*Command` 类**（剔除 `*Settings/Set*/Validate/Cell*/Debug/Legacy` 等内部类后 **602**）；131 接口 |
| `SpaceClaim.Api.V19.dll` | **3,490 类型**（剔编译器生成后 1,243）；**183 个 `I*` 接口** |
| `SpaceClaim.Api.V19.xml`（API 文档） | **612 个文档化类型 / 4,100 个成员** |
| 真实 journal（`%APPDATA%\SpaceClaim\Journal Files`，237 份） | 官方页签 ID 实测：`DesignRibbonTab`、`EditSketchRibbonTab`、`InsertRibbonTab`、`AssemblyConfigurationsRibbonTab`、`AnalysisRibbonTab`、`CaePrepareRibbonTab`、`CaeRepairRibbonTab`、`SheetMetalRibbonTab`、`AdditiveMfgRibbonTab`、`DetailingRibbonTab`、`WorkbenchRibbonTab`、`GetKeyShotRibbonTab`、`ViewRibbonTab`、`JournalRibbonTab`、`RSRibbonTab`、`Ami.ControlsRibbonTab` |
| `Commands.dll` 关键字归类（近似口径，见 §9） | 直接建模 ~153 · **CAE 网格/求解 ~90** · **钣金 ~89** · **修复检查 ~55** · **草图/2D ~46** · **梁/焊件 ~43** · **工程图/标注 ~42** · 渲染/外观 ~39 · 结构/选择/视图 ~21 · 互操作 12 · 测量 11 · 装配 10 · 参数/脚本 5 · 增材 4 · UI 4 · 未归类 64 |
| `Api.V19` 域类型数（剔编译器生成） | 工程图/标注/GD&T **132** · 钣金 **103** · 成形/孔/螺纹 **101** · 互操作/PMI/单位 **82** · 装配/配合条件 **70** · 网格/CAE **70** · 渲染/材质 **62** · 参数/特征/脚本 **55** · 结构/视图/相机 **38** · 梁/焊件 **37** · 选择/UI/Ribbon 30 · 导入导出选项 **19** · 测量/质量属性 11 |

> 口径说明：`*Command` 类含对话框与内部命令，**602** 是「剔除明显内部类」后的近似用户可见数，
> 不是精确的 Ribbon 按钮数；域归类为关键字首匹配，用于**量级比较**而非精确统计。

---

## 3. 页签级对照

| 官方页签（journal 实测） | 我们的对应 | 判定 |
| --- | --- | --- |
| Design | 设计（59 命令 / 9 组） | 有，广度小于官方 |
| View | 显示（11 命令） | 有 |
| Measure | 测量（3 命令：测量/质量属性/干涉） | 覆盖主要手段 |
| Facets | 分面（5 命令：反转/光滑/简化/填孔/转实体） | 有 |
| AdditiveMfg | 增材（4 命令：构建体/取向/支撑/点阵） | 命令数相当（官方 Additive* 4 个） |
| CaeRepair | 修复（7 命令） | 有，官方 ~55 命令类 |
| CaePrepare | 准备（5 命令） | 官方另有 ~90 个网格/求解命令类 |
| Analysis | 仿真（4 命令，仅数据模型） | 官方 `AnalysisRibbonTab` 有网格/求解链 |
| Workbench | Workbench（2 命令：参数/发布） | 仅参数单向 |
| SheetMetal | 钣金（5 命令） | 官方 ~89 命令类 |
| Detailing | 详细（5 命令） | 官方 ~42 命令类 + 132 API 类型 |
| GetKeyShot | KeyShot（1 命令） | 仅入口 |
| Assembly | 组件（7 命令） | 官方另有装配配置页 |
| **Insert** | 无独立页签（部分命令散在 设计▸插入） | **缺页签** |
| **AssemblyConfigurations** | 无 | **缺整域（模型里也没有配置概念）** |
| **EditSketch**（专用模式页签） | 无（草图模式复用设计页 + 模式切换） | 形态不同 |
| Journal / RS / Ami.Controls | 工具（脚本/录制/自定义） | 部分对应 |
| —（我们额外） | 曲面、安全、工具 | 官方曲面/安全为页签或模块，形态不同 |

**官方有、我们没有的整域**：梁与焊件、标准孔/螺纹/成形特征、CAE 网格与 Blocking、装配配置、
命名视图、参考图像、制造（去毛刺/刀路）、PMI/GD&T 标注。

---

## 4. 逐域完整度 × 深度对照（双口径，深度沿用 L0–L4 自评尺度）

> 深度尺度：**L0** 桩 · **L1** 参数闭环（自研可用、语义简化）· **L2** 权威执行（自研产物官方可开/
> 权威门禁通过）· **L3** 字节·签名·对拍级。完整度为**该域用户路径覆盖**的自评。

| 功能域 | 我们（实测） | 官方规模（实测） | 深度 | 关键缺口 |
| --- | --- | --- | --- | --- |
| scdoc 读端 | 22 类 SAB 记录字段级解码；官方库 6/6 解析 | — | **L3-** | 字节恒等 round-trip（读端不产字节） |
| scdoc 写端 | FIFO 遍历算法（官方 141 记录 golden 复现）+ SabSatConverter/SpaceClaim 双门禁（bodies=1/2） | — | **L2+** | 字节恒等（NYI-1，信息论不可行） |
| CAD 互操作 | 9–10 格式读写 + X_T 官方管线 | 19 组导入导出选项类（ACIS/CATIA/Parasolid/STEP/STL/OBJ/Workbench…） | **L2** | CATIA/Parasolid 直读、Workbench 导入、PMI、PDF-3D（多为 NYI-2 边界） |
| 直接建模 | Pull 模式族（`pull_auto`）、变半径圆角、多厚度抽壳、中性面拔模、路径/填充阵列、分割、替换、填充 | ~153 命令类 | **L2** | Detach/Merge/Extend/Unroll/MakeThin/ReverseFaceNormal/FindDuplicateFaces 等命令族；选择歧义循环 UI |
| 草图与约束 | 13 图元命令全 live；LM 求解器（DOF/冲突/冗余/表达式联动，12 类残差） | ~46 命令类 + DCM 求解 | **L1+ / L2-** | 无 3D 草图；无曲线编辑命令（trim/extend/offset）；捕捉 3 项仅「栅格」生效；无 DCM 级鲁棒性 |
| 装配与配合 | 7 类运动副求解 + 官方打开 bodies=2 + 组件树写回 | ~10 命令类 + 70 API 类型 | **L2-** | 无 PartDef/实例（同零件多实例不可表达）、无装配配置、无齿轮副 |
| 钣金 | 折弯/展开（多弯链）/撕裂/角释放/折弯槽口/jog | **~89 命令类 / 103 API 类型** | **L1+** | 卷边(hem)、加强筋(bead)、角撑(gusset)、舌片(tab)、接缝(junction)、圆锥/轴向折弯、cross-break、折弯表/展开图 |
| 曲面 | untrim/extend/offset/thicken/patch(多约束)/blend-loft | 33 API 类型 | **L1+** | face-face blend、曲线网络、trim-by-surface、ruled/导引曲线 |
| 修复与检查 | 6 检出器 + 自动修复 + 一键报告 | **~55 命令类** | **L1+** | 去毛刺、标准孔/缺口/成形识别、模型清理、简化/包围/中面的完整命令族 |
| 测量 | 点点/边边(距+夹角)/面面(距+夹角)/柱面半径 + 质量属性 + 干涉 | ~11 命令类 | **L2-** | 投影面积等专业量 |
| 工程图/标注 | HLR 三视图 + 图幅模板(A0–E/B/C) + BOM + 尺寸 | **~42 命令类 / 132 API 类型** | **L1** | 投影/局部/剖视/旋转剖/断裂视图、气球、表格、GD&T、粗糙度、焊接符号、条码 |
| 参数/脚本/特征 | 2 个参数化构造器（box/cylinder）+ 29 个脚本 op + 10 类 SpaceClaim 风格 API 门面 | **55 API 类型**（feature-track/smart variable/script block）+ 5 命令类 | **L1** | **无特征历史/特征树**；参数化不覆盖编辑操作；API 门面 ≈ 官方 612 文档类型的 1.6% |
| CAE 网格/分析 | 仿真准备数据模型（载荷/支撑/接触/标记）4 命令 | **~90 命令类 / 70 API 类型** | **L1** | 网格划分、Blocking、求解链（NYI-4 边界：求解走 ANSYS 宿主） |
| 增材 | 构建体/取向/支撑/点阵（几何级） | 4 个 Additive* 命令类 + AMI 支撑 | **L1** | 切片/机输出/悬垂分析 |
| 渲染 | VTK 着色/边/透明 + 剖面 + KeyShot 入口 | 62 API 类型 | **L1** | 材质库/光照/场景/光线追踪（NYI-5 边界） |
| 结构树/图层/视图 | 图层、命名选择、用户组、可见性 | 38 API 类型 | **L1** | 无命名视图（TODO-7 边界）、无配置树、无选择集历史 |
| 梁/焊件/制造/成形 | **无** | **~43 + 101 API 类型** | **L0** | 整域缺失 |

---

## 5. 深度剖析：比"命令条数"更重要的六个结构性差距

### 5.1 没有设计历史（最大结构差）
`KernelDoc` 只有 `bodies / sketches / components / mates / parametrics / param_table / sim / named /
groups`；撤销是 `history.py`（46 行）的**形状快照**栈。官方有完整的特征追踪体系（`IFeatureTrackBlock*`、
`IScriptBlock`、`IReplayState`、`SmartVariable` 等 55 个类型）+ 692 个可重放命令类。
后果：任何"改参数 → 重建整条建模链"的能力在我们的架构里**无处安放**。

### 5.2 "参数化"名不副实
`params.py` 只有 `box_builder`/`cylinder_builder` 两个构造器；`Parametric` 只能重放"建基本体"。
拉伸/圆角/抽壳/布尔等编辑操作不进参数化链。对照官方的 feature/smart-variable 体系，这块是**架构级**
而非功能级缺口。

### 5.3 装配是扁平列表，不是产品结构
`Component` = `{id, name, body_ids, anchored, visible, lightweight, explosion, transform}`，无
PartDef/实例引用/配置/替换件；写回靠"一体一 part"。官方有 Part/Component/Instance/Configuration
四层（70 个装配 API 类型），因此**同一零件的多实例、装配配置、零部件替换**在我们这里不可表达。

### 5.4 工具选项与拾取仍是"半接线"
- 选项页只定义 4 个：`tool.select`（捕捉到栅格/端点/中点/重合）、`tool.pull`（对称/复制/到面 +
  距离）、`tool.move`（复制/到点/到面 + 距离）、`tool.combine`（合并/减去/相交）。
- 消费情况：pull/move/combine 的选项确实被 `_opts_for()` 读取并传入内核（12 处 `opts.get`）；
  `tool.select` 的 4 项里**只有"捕捉到栅格"被消费**（`scdm_gui.py:2777` 的圆柱/球放置与草图栅格），
  **端点/中点/重合只写进 `sel` 不参与拾取**；填充/替换/分割**连选项页都没有**。
- 拾取已有 per-edge / per-vertex actor（`gui/scene.py`），比早期文档描述的状态好；但仍无官方的
  "按住点击循环遍历候选"语义。

### 5.5 内核语义不同（已入册边界，但影响深度评价）
内核是 OCCT 7.9.3，官方是 ACIS（`SpaACIS.dll`）。我们以"官方 SabSatConverter restore + 官方
SpaceClaim 打开 + 逐字段 diff"替代内核复刻（NYI-3/6），这是**正确的工程取舍**，但意味着圆角溢出
控制、公差语义、求解容差等行为**永远不等于**官方；凡涉及"与 SpaceClaim 逐操作等价"的验收，都必须
用哨兵而非数值断言。

### 5.6 代码健康（顺带实测到的具体缺陷）
`scdm/kdoc.py` 的 `Component` 存在**重复定义**：`lightweight: bool = False`（42 行与 49 行）、
`lightweight_body_ids()`（47 行与 52 行）各定义两次——后者静默覆盖前者，属真实（暂无害）缺陷。
另有 4 个 1.4k–4.2k 行巨文件、16 个 ≥100 行函数。

---

## 6. 自评口径复核：把 91% 拆成两个数

| 口径 | 分子/分母 | 结论 |
| --- | --- | --- |
| **A. 格式与互操作层** | scdoc 读/写 + 官方双门禁 + 9–10 种格式 | **≈95–100%**（该说法成立，且有官方哨兵背书） |
| **B. 功能广度层** | 我们 130 条目录命令 vs 官方 ≈602 个用户可见 `*Command` 类 | **≈20–25%**（粒度不可逐条对齐，仅表量级） |
| **C. 功能深度层** | 共享域内"能跑通" vs "能用好" | 除格式层外集中在 **L1–L2**；无整域覆盖的域按 0 计 |

**建议**：`function_gap_analysis.md` 的域清单必须扩到官方页签/命令面（至少加入梁焊件、孔/螺纹/成形、
CAE 网格、制造、装配配置、命名视图、PMI 七域），并把 A/B 两个口径**分开记分**——否则"91%"会被读成
"整体接近官方"，与实测差距不符。

---

## 7. 文档漂移清单（需修正）

| 文档 | 过期结论 | 本次实测 |
| --- | --- | --- |
| `analysis_and_plan.md` | 125 命令 / 113 live；8 个草图命令无 handler；测量仅两点；边/顶点不可拾取；选项面板只展示不消费；拔模普通盒体抛错 | 全部**已过期**：草图 8 命令均在 live；per-edge/vertex actor 已实现；测量含夹角/半径/面距；pull/move/combine 选项已消费 |
| `function_gap_analysis.md` §0 表 | 整体 ≈91%（13 域均值）；钣金 §2.8 记"多弯展开/折弯槽口未实现"；草图 §2.6 记 L1+ 80%；§5 记"167 passed" | 91% 的分母缺 7 个官方整域；多弯展开/折弯槽口/图幅版式**均已闭环**（NYI TODO-2/3/5）；草图求解器已升级（TODO-8 关闭）；测试实测 244 passed |
| `DEV_PLAN.md` §21.1 | "18 页签 / 130 命令 / 144 live"（对）但"kernel.py 71 函数"、"测试 195 条" | kernel.py 实测 **80** 个公开函数；`def test_` **236** 条、本次收集通过 **244** |
| `docs/IMPROVEMENT_PRIORITIES.md` | P0/P1/P2 全闭环（准确） | 准确；但**未记录在途 GUI 观感打磨**（6 文件未提交） |
| `docs/NYI_INVENTORY.md` | 与代码一致 | 核对通过（TODO-1 装配对拍样本仍是唯一"暂缓"项） |

---

## 8. 差距排序与建议（按 ROI）

| # | 建议 | 依据 | 预估 |
| --- | --- | --- | --- |
| 1 | **特征族补齐**：标准孔（含沉头/锥沉）、螺纹、成形（凸台/凹坑/百叶/敲落/压铆） | 官方 101 个 API 类型，是实际建模最高频特征；OCCT 可实现（孔=切削+阵列，成形=布尔+圆角近似） | 2–3 周 |
| 2 | **特征历史 / 参数化重建**：把编辑操作记录为特征块，参数变更重放 | 架构级；决定"参数驱动"是否名副其实（官方 55 个 feature 类型） | 3–5 周（需设计） |
| 3 | **钣金完整性**：hem/bead/gusset/tab/junction + 圆锥/轴向折弯 + 展开图输出 | 官方 89 命令类 / 103 API 类型，我们 5 命令 | 3–4 周 |
| 4 | **工程图标注体系**：投影/局部/剖视视图 + 气球/表格 + GD&T/粗糙度/焊接符号 | 官方 132 个 API 类型，我们 5 命令 | 3–4 周 |
| 5 | **装配结构**：PartDef/实例/配置 + 齿轮副/对齐条件 | 官方 70 个装配 API 类型；扁平模型阻塞多实例 | 2–3 周 |
| 6 | **CAE 准备与网格**（面向 ANSYS 受众的差异化）：网格控制/Blocking | 官方 90 命令类；我们仅数据模型 | 4 周+ |
| 7 | **交互深度收尾**：端点/中点捕捉真正参与拾取、填充/替换/分割选项页、选择歧义循环 | §5.4 实测 | 1 周 |
| 8 | **代码与文档健康**：拆巨文件、修 `kdoc.Component` 重复定义、`function_gap_analysis` 重定基线、§21.1 快照自动化含测试数 | §5.6/§7 | 3–5 天 |

---

## 9. 复现命令（本次实测所用）

```powershell
$py = "C:\Users\sdcll\.conda\envs\scdm\python.exe"

# 1) 测试门禁（非官方档）
$env:PYTHONIOENCODING='utf-8'; $env:QT_QPA_PLATFORM='offscreen'
& $py -m pytest tests/ -m "not official" -q        # -> 244 passed, 1 skipped, 6 deselected

# 2) 官方 Library 解析覆盖
& $py references/scan_library.py                    # -> SrModels 6/6，最大 80 体/1813 面/9060 coedge

# 3) 命令面快照
& $py tools/gen_devplan_snapshot.py                 # 需 PYTHONIOENCODING=utf-8（脚本用 cp1252 会 UnicodeEncodeError）

# 4) 官方对照基线（本机 SpaceClaim 安装）
#    - Commands.dll / SpaceClaim.Api.V19.dll 反射枚举类型
#    - SpaceClaim.Api.V19.xml 文档化类型/成员计数
#    - %APPDATA%\SpaceClaim\Journal Files\*.scjournal 提取 UI_CMD=/DC= 页签与命令 ID
```

---

*报告生成：2026-09-12 · 基线：工作树 HEAD `9cad847` + 6 文件未提交改动 · 对照：ANSYS SpaceClaim 2019 R3 (v195)*
