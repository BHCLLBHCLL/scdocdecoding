# scdocdecoding 当前代码状态独立复核（12 域） —— 对照 ANSYS SpaceClaim 2019 R3

> 复核日期：2026-09-12 ｜ 基线：HEAD `9cad847`（2026-09-09）+ 6 文件未提交改动
> 方法：**代码级 + 实跑验证**（读实现、跑测试、复跑官方门禁、独立复算），非文档转述。
> 格式参照 `D:\training\cgns\pphdecoding\docs\CODE_STATE_AUDIT_20260906.md`（12 域对照 + 分层深度 A–E
> + 冲突点 + 缺陷清单）。
> 对照基准：本机已安装的 **ANSYS SpaceClaim 2019 R3（v195）** `scdm\Commands.dll` /
> `SpaceClaim.Api.V19.dll` / `SpaceClaim.Api.V19.xml` 及其真实用户 journal（237 份）。
> 姊妹文档：`docs/CODE_STATE_VS_SPACECLAIM.md`（同日，逐域差距与 ROI 建议）；本报告聚焦**独立复核**。

---

## 0. 一句话结论

**这是一个"格式层生产级、GUI 层可用、专业域薄"的直接建模器**：① scdoc 格式层的读/写在
**官方门禁下被独立验证通过**（本次实跑 `official_gate` 5 passed + `official_open` 1 passed，
真实 SpaceClaim 打开我们写出的两体装配）；② GUI 壳层 18 页签 / 130 命令 / 144 live，形态完整；
③ 但**专业域（钣金/曲面/工程图/CAE/参数历史）普遍停在 L1–L2**，且**命令级测试覆盖只有 26/130**。

按 12 域独立复核：**整体约 74%**（文档自评 ≈91%）。差距**不在**格式层（那是本仓最强、
且经得起官方验证的部分），而在**特征族缺失 + 无设计历史 + 测试只测内核不测命令**。

与参照项目（pphdecoding）最大的结构差异：**pphdecoding 是"驱动已安装宿主的自动化编排层"，
本仓是"自带 OCCT 内核的独立实现"** —— 因此本仓回避了宿主依赖风险，但也不得不在
L1–L2 的深度上自己造每一个专业域。

---

## 1. 对照基准：SpaceClaim 2019 R3 实测功能面（非人工估计）

| 来源（本机安装实测） | 数值 |
|---|---|
| `Commands.dll` 反射枚举 | 2,806 类型；**692 个 `*Command` 类**（剔除 `Settings/Set*/Validate/Cell*/Debug/Legacy` 后 **602**）；131 接口 |
| `SpaceClaim.Api.V19.dll` | 3,490 类型（剔编译器生成 1,243）；**183 个 `I*` 接口** |
| `SpaceClaim.Api.V19.xml` 文档 | **612 文档化类型 / 4,100 成员** |
| 真实 journal（237 份） | 官方页签 ID 16 个：Design / EditSketch / **Insert** / **AssemblyConfigurations** / **Analysis** / CaePrepare / CaeRepair / SheetMetal / AdditiveMfg / Detailing / Workbench / GetKeyShot / View / Journal / RS / Ami.Controls |
| 命令类域归类（关键字首匹配，近似） | 直接建模 ~153 · **CAE 网格/求解 ~90** · **钣金 ~89** · **修复检查 ~55** · **草图/2D ~46** · **梁/焊件 ~43** · **工程图/标注 ~42** · 渲染 ~39 · 结构/视图 ~21 · 互操作 12 · 测量 11 · **装配 10** · 参数/脚本 5 · 增材 4 · UI 4 · 未归类 64 |
| API 类型域分布（剔编译器生成） | 工程图/标注/GD&T **132** · 钣金 **103** · 成形/孔/螺纹 **101** · 互操作/PMI 82 · 装配 **70** · 网格/CAE **70** · 渲染 62 · 参数/特征 **55** · 结构/视图 38 · 梁/焊件 **37** · 选择/UI 30 · 导入导出选项 19 · 测量 11 |

> 本仓 GUI 命令面：**17 ribbon 页签 + 1 backstage = 18**；**130 条目录命令**；live 144（含 16 backstage）；
> 占位 2（`prep.small`、`safety.tab`）。与官方口令类的粒度不可逐条对齐（我们 1 条 `create.pattern`
> 覆盖官方线性/圆周/路径/填充四种），量级比较用。

---

## 2. 仓库规模与形态（实测）

| 层 | 文件数 | 行数 |
|---|---:|---:|
| `scdm/`（内核·文档·工具态机·脚本） | 37 | 14,089 |
| 根目录 Python（GUI 主体 + 一次性脚本） | 6 | 4,819（其中 `scdm_gui.py` 4,208） |
| `scdoc_parser/`（格式读端） | 8 | 2,497 |
| `tests/`（pytest） | 28 | 4,115 |
| `references/`（互操作/哨兵/逆向脚本） | 26 | 2,742 |
| `tools/`（快照生成） | 1 | 52 |
| **Python 合计** | **106** | **28,314** |
| 文档 Markdown（根 + docs/） | 12 | 2,725 |

- **git**：136 commits，2026-08-24 → 2026-09-09；近 7 日 **28 commits**；未跟踪 7 项。
- **证据产物**：`references/golden` 7 个官方样本（243 KB）、`references/geometry` 2 个真实零件
  （3.7 MB）、`references/disasm` 18 个逆向脚本（4.1 MB）、`references/layout_extract/class_layouts.json`；
  根目录 `box.scdoc`（29.6 KB，官方模板）+ `box_report.json`。
- **环境**：`environment.yml`（py3.11 / pythonocc-core 7.9.3 / PyQt5 5.15.11 / vtk 9.6.1）+ `requirements.txt`
  + `.github/workflows/ci.yml`（`-m "not official"`）；本次在 conda env `scdm` 实跑**全绿**（§3-E）。
- **巨大文件**：`scdm_gui.py` 4,208 · `scdoc_write.py` 2,012 · `sab_emit.py` 1,725 ·
  `gui/scene.py` 1,575 · `kernel.py` 1,468 · `gui/icons.py` 1,114；**16 个函数 ≥100 行**（最长
  `icons._draw` 963 行）。

---

## 3. 分层深度清单（A–E）

### A. 格式层（读 + 写）—— 全仓最强，**L2+–L3**

| 模块 | 行数 | 真实能力 | 深度 |
|---|---:|---|---|
| `scdoc_parser/`（opc/sab/topology/facets/document/report） | 2,497 | OPC 容器、22 类 SAB 记录字段级解码、facets 双格式、document.xml 解析、报告 | **L2+（读）** |
| `scdm/sab_emit.py` | 1,725 | 逆向 `SpaACIS.dll` 得到的 **FIFO 保存遍历**（官方 141 记录 golden 复现）+ 数据驱动布局表 | **L2+（写）** |
| `scdm/scdoc_write.py` | 2,012 | 官方存档骨架 document.xml、装配 id 分配器（`_DocIdAllocator`）、多体 facets、元数据注入 | **L2+（写）** |
| `scdm/import_sab.py` | 400 | SAB 拓扑 → OCCT `TopoDS` | L2 |

**独立验证（本次实跑，非文档转述）**：

- `pytest -m official_gate` → **5 passed / 246 deselected / 20.0 s**：box、倒圆盒、打孔盒、锥台、
  放样（bcur）五类经官方 `SabSatConverter.exe`（SAB→SAT）全部通过。
- `pytest -m official_open` → **1 passed / 250 deselected / 110.8 s**：
  `test_official_open_assembly_bodies_two` —— **真实 SpaceClaim 2019 R3 打开我们写出的两体装配**。
- `python scdm_interop_check.py` → 自审输出：`records: 111 vs reference 111`、记录种类集合完全一致、
  `audit: OK`。
- `python references/scan_library.py` → 官方 Library **6/6** SrModels 解析成功
  （samplemodel2 = 37 体 / 1,813 面 / 9,060 coedge；samplemodel5 = 80 体 / 1,288 面）。

> **这是本仓唯一"文档声称 = 独立复核"的层**。参照项目（pphdecoding）在同类问题上被查出"零宿主回读验收"，
> 本仓相反：写端有真实宿主门禁。

### B. 几何内核层 —— **L2（自研封装 + OCCT，非 ACIS）**

- `kernel.py` 1,468 行 / **80 个公开函数**（DEV_PLAN 记 71，已过期）：基本体×5、布尔、变换、
  阵列×4、镜像、分割、圆角（含变半径）、倒角、抽壳（含多厚度）、拔模（含中性面）、填充、偏移、
  螺旋、中面、共享拓扑、干涉/体积/面积/重心、STEP/IGES/STL/OBJ/3MF/VRML/BREP 读写、离散。
- 测试以**体积精确断言**为主（`pytest.approx` 1e-6～1e-9），例如折弯展开、多厚度抽壳、变半径圆角区间。
- **本质差异**：官方是 ACIS（`SpaACIS.dll` 60 MB），我们是 OCCT 7.9.3。这不是缺陷而是取舍
  （NYI-3/6 已入册），但意味着**任何"与 SpaceClaim 逐操作等价"的验收都只能靠哨兵**，不能靠数值对拍。

### C. GUI 层 —— 表面 **~90%**，语义 **~55%**

- `scdm_gui.py` 4,208 行 + `scdm/gui/`（scene 1,575 / left_panel 393 / ribbon 255 / viewport 261 /
  icons 1,114 / theme / status / backstage）；VTK 视口，per-face / per-edge / per-vertex actor 齐备。
- **真的接到内核的**：107/130 命令有专属 `_do_*` handler；工具态机（Select/Pull/Move/Fill/Combine/
  Split/Replace）走内核；草图模式可进入并点击绘制（`_sketch_click`）；测量含点点/边边(距+夹角)/
  面面(距+夹角)/柱面半径。
- **半接线（结构性）**：选项页只定义 4 个工具（`tool.select` / `tool.pull` / `tool.move` /
  `tool.combine`）；`tool.select` 的 4 项里**只有"捕捉到栅格"被消费**（`scdm_gui.py:2777`），
  端点/中点/重合只写进 `sel` 无人读；填充/替换/分割**连选项页都没有**。
- **在途未提交**：GUI 观感打磨（`icons.py` +994/-589、`viewport.py` +183、`ribbon/theme/left_panel`、
  `test_smoke.py` +24），方向是对齐官方 Office2016 观感。

### D. 数据 / 参数 / 脚本层 —— **L1**

- `kdoc.py`（186 行）= bodies / sketches / components / mates / parametrics / param_table / sim /
  named / groups；**没有特征历史**，撤销是 `history.py`（46 行）的形状快照。
- `params.py`（200 行）：表达式参数表（依赖排序、循环/未知引用/注入拒绝）+ **仅两个构造器**
  （`box_builder` / `cylinder_builder`）——"参数驱动重建"止步于基本体。
- `scripting.py`（456 行）：29 个 op 的录制/回放；`script_api.py`（145 行）：10 个 SpaceClaim 风格类
  （官方 612 个文档化类型 → 门面覆盖 ≈1.6%）。

### E. 测试与证据 —— 内核级扎实，**命令级稀疏**

| 口径 | 实测 |
|---|---|
| 全量（非官方） | **244 passed / 1 skipped / 6 deselected / 86 s**（本次实跑，conda env `scdm`） |
| 官方门禁 | `official_gate` **5 passed**、`official_open` **1 passed**（本次实跑） |
| 测试规模 | 28 文件 / 236 个 `def test_` / 收集 251 条 |
| **命令级覆盖** | 130 条目录命令中，**仅 26 条在测试源码中被提及**；**104 条零提及**（含全部 13 条草图图元、全部 7 条约束、facet 5 条、repair 6 条、detailing 5 条、tools 3 条） |
| 结构型门禁 | `test_g1.py` 通过**读源码字符串**断言"live 命令有 handler"；其中 17/130 命令走**前缀豁免**（`tool.*/show.*/style.*`）——守卫不校验这些 |
| 恒真断言 | `test_p12_e2e.py:80` `assert "pull" in str(exc) or True`（且 `except Exception` 吞异常）→ 该门禁**永不失败** |
| 官方行为覆盖 | 写端有真宿主门禁（见 A）；**单体**官方打开仅见于 DEV_SUMMARY 手工记录，**未挂 `official_open` 标记**（回归里只有装配） |

---

## 4. 12 域对照：文档声称 vs 独立复核

| # | 域 | 声称 | 实际支撑（证据类型） | 复核后 | 残留风险 |
|---|---|---|---|---|---|
| 1 | scdoc 解析读端 | 100% L3- | (a) 官方库 6/6 解析（本次实跑）；22 类记录字段级解码 | **95% L2+–L3** | 读端不产字节，无字节级判据；B 样条特殊变体按文档留白 92 条（未独立复算） |
| 2 | scdoc 写端 | 92% L2+ | (a) **本次复跑官方双门禁通过**（SabSatConverter 5 + SpaceClaim 打开 1）；自审 111/111 记录同构 | **85% L2+** | 单体官方打开无回归门禁；字节恒等不可达（NYI-1）；通用体走 B 样条逼近 |
| 3 | 工程文件管理 | 100% L2+ | (b) e2e 链：草图→拉伸→抽壳→阵列→截面→命名选择→存 .scdm→重开→体积恒等（rel=1e-9） | **88% L2** | pickle 无版本头；恢复/自动保存仅接线 |
| 4 | CAD 互操作 | 95% L2 | (b) `scdm_interop_check.py` OK；(a) 五类形体经 SAT 官方 restore | **82% L2** | 互操作矩阵脚本未入 pytest；STEP 装配层级、CATIA/Parasolid 直读缺（NYI-2） |
| 5 | 直接建模 | 95% L2+ | (a/b) 体积精确断言密集；(c) 命令级测试 26/130 | **78% L2** | 选项半接线；无特征历史；无选择歧义循环 |
| 6 | 草图与约束 | 80% L1+ | (b) LM 求解器 12 测试（DOF/冲突/冗余/表达式联动）；(c) 13 图元命令**零测试提及** | **65% L1+** | 捕捉 3 项仅 1 项生效；无 3D 草图；无曲线编辑命令；无 DCM 级鲁棒性 |
| 7 | 装配与配合 | 90–99% L1+/L2 | (a) **本次复跑 official_open 通过**（真实宿主打开两体装配）；(b) 7 类运动副 9 测试 | **74% L2-** | 扁平 `Component(body_ids)`：无 PartDef/实例/配置；无官方装配配合样本（TODO-1） |
| 8 | 钣金 | 85% L2 | (b) 14 测试含体积精确（BA=θ(R+Kt)、展开长、槽口去除量）；(c) 官方 89 命令类 / 103 类型 | **68% L1+** | hem/bead/gusset/tab/junction、圆锥/轴向折弯、cross-break、折弯表、展开图 |
| 9 | 曲面 | 85% L2 | (b) 8 测试（untrim 面积 3×、offset 采样 R+d、patch 1e-4）；(c) 官方 33 类型 | **64% L1+** | face-face blend、曲线网络、trim-by-surface、ruled/导引曲线 |
| 10 | 修复/检查/准备/仿真 | 85% L1 | (b) 7 测试（6 检出器 + 自动修复归零）；(c) 官方 ~90 CAE 命令类 / 70 类型 | **68% L1+** | 无网格/Blocking/Analysis；检出率未对官方样本做基准；仿真仅数据模型 |
| 11 | 工程图/显示/渲染/测量 | 75% L1–L2 | (b) drawing 3 测试 + 官方图幅尺寸；(c) `measure.mass`/`measure.interfere`/`ks.render` **零测试提及** | **55% L1** | 视图族（投影/局部/剖视/断裂）与标注族（GD&T/粗糙度/焊接/气球/表格）缺（官方 132 类型） |
| 12 | 参数/脚本/API/特征 | 90% L2 | (b) 10 测试（表达式/循环/注入拒绝）；(c) API 门面 10 类 vs 官方 612 文档类型 | **45% L1** | **无特征历史/特征树**；参数化仅 2 个构造器；编辑操作不入参数链 |

**复核均值 ≈ 74%**（文档自评 ≈91%）。

> 12 域定义：1 读端 · 2 写端 · 3 工程文件 · 4 互操作 · 5 直接建模 · 6 草图 · 7 装配 · 8 钣金 ·
> 9 曲面 · 10 修复/准备/CAE · 11 表现层（工程图/显示/渲染/测量）· 12 参数/脚本/特征历史。
> 与官方页签的对应见姊妹文档 §3。**未纳入本表的官方整域**：梁/焊件、标准孔/螺纹/成形、
> 装配配置、命名视图、参考图像、制造——它们在我们的清单里没有对应域（=0），若计入则均值更低。

---

## 5. 与文档结论的冲突点（可验证）

| # | 文档声称 | 反证 |
|---|---|---|
| C1 | `function_gap_analysis.md` §0「整体 ≈91%（13 域均值）」 | ① 分母是**自选 13 域**，无梁焊件/孔螺纹成形/CAE 网格/制造/装配配置/命名视图/PMI；② 逐域百分比无独立复算来源；本报告同域复核 **≈74%**，且未计上述整域 |
| C2 | `DEV_SUMMARY.md`「单体 box/cyl 官方打开 bodies=1 已复验」 | 回归套件中**只有装配**挂了 `official_open` 标记；单体官方打开**无持续门禁**，仅存手工记录 |
| C3 | `analysis_and_plan.md`：8 个草图命令无 handler、测量仅两点、边/顶点不可拾取、选项面板只展示不消费 | **全部过期**：13 条草图命令均在 live 集；`gui/scene.py` 有 per-edge/vertex actor；`_measure_pick` 支持半径/边夹角/面距/面夹角；`_opts_for` 已消费 pull/move/combine 选项 |
| C4 | `function_gap_analysis.md` §2.8「多弯展开/折弯槽口未实现」、§2.9「图幅版式缺」、§2.6「草图 L1+ 80%」、§5「167 passed」 | 与同仓 `docs/NYI_INVENTORY.md` 的 TODO-2/3/4/5/**8** 闭环记录**自相矛盾**；测试实测 244 passed |
| C5 | `DEV_PLAN.md` §21.1「kernel.py 71 函数 / 测试 195 条」 | 实测 `kernel.py` **80** 个公开函数；`def test_` **236** 条、收集 **251** 条 |
| C6 | `tests/test_g1.py` 保证「live 命令必有落点」 | `_dispatchable()` 对 `tool.*/show.*/style.*` **前缀一律放行**（17/130 条），"全部可派发"含 13% 未校验成分 |
| C7 | `tests/test_p12_e2e.py` 为「§20.8 录放链门禁」 | `:80` `assert "pull" in str(exc) or True` 恒真 + `except Exception` 吞异常 → **该门禁无法失败** |

**已确认成立（本次独立复现）**：写端官方双门禁、官方 Library 6/6 解析、SAB 记录同构自审、
非官方全量测试全绿、环境可复现（`environment.yml` + conda env `scdm`）。

---

## 6. 关键缺陷清单（按严重度，全部可复现）

| 级别 | 缺陷 | 证据 | 影响 |
|---|---|---|---|
| P1 | **`sab_emit.py` `_rec_header` 重复定义**（1170 行与 1342 行），后者遮蔽前者 | AST 扫描；两版差异：前者支持 `cid is None`（`hdrlen` 条件 +5），后者恒 +5 且无条件写 `T_ID` | `cid=None` 分支成为**死代码**；未来任何传 None 的调用点会 `_ri(None)` 崩溃。当前 12 个调用点均传显式 cid，故未爆 |
| P1 | **回归门禁存在恒真断言** `test_p12_e2e.py:80` | `assert "pull" in str(exc) or True` + 前置 `except Exception` | 录放链（§20.8 验收项）实际**未被门禁保护** |
| P1 | **命令级测试覆盖 26/130**，104 条零提及（全部草图图元、全部约束、facet、repair、detailing、tools、measure.mass/interfere、ks.render） | 本次字符串口径扫描 | 「命令 live」只等于「源码里有 handler」，不等于「行为被验证」；专业域回归靠内核单测间接覆盖 |
| P1 | **`kdoc.py` `Component` 重复定义**：`lightweight`（42/49 行）、`lightweight_body_ids()`（47/52 行） | AST 扫描 | 后者静默覆盖前者；属真实（暂无害）缺陷；同一处 `KernelDoc.notes` 属性 getter/setter 成对（正常） |
| P1 | **工具选项半接线**：仅 4 个工具定义选项页；`tool.select` 4 项中 3 项（端点/中点/重合）只写内存 | `gui/left_panel.py:201-206`（定义）、`scdm_gui.py:2777`（唯一消费点 `snap_grid`） | 用户以为在用的捕捉选项不生效 |
| P2 | **单体官方打开无回归门禁** | `grep official_open tests/` 仅 1 处（装配） | 写端在单体路径上的官方兼容性**只在手工验证时知情** |
| P2 | **`tools/gen_devplan_snapshot.py` 在 cp1252 控制台直接崩溃** | 实跑：`UnicodeEncodeError: 'charmap' codec ... position 5-7` | 需 `PYTHONIOENCODING=utf-8` 才能生成 §21.1 快照；文档计数因此长期漂移 |
| P2 | **VTK 弃用 API** `SetCells`（`gui/scene.py:1484/1502/1541/1564`） | 全量测试 19 条 `DeprecationWarning` | VTK 9.6 下可用，10.x 需改 `ImportLegacyFormat/SetData` |
| P2 | **文档漂移三处**（analysis_and_plan 全面过期；function_gap_analysis 域表/测试数过期；DEV_PLAN §21.1 计数过期） | §5 C3/C4/C5 | 新读者会按过期结论判断现状 |
| P3 | 巨型文件/函数：4 个 ≥1.4k 行文件；16 个 ≥100 行函数（`icons._draw` 963 行、`_assembly_document_xml` 421 行） | AST 扫描 | 维护与 review 成本 |
| P3 | 根目录遗留 `cyl_ref_sentinel.txt` 未跟踪；`_tmp/SpaceClaim` 残留 | `git status` | 仓库卫生（`.gitignore` 已覆盖 `_*.py/_t.*/_tmp/`，但哨兵 txt 未覆盖） |

---

## 7. 谁做什么：本仓 vs SpaceClaim

| 能力 | 本仓自研 | 委派/依赖 | SpaceClaim 独有（未复刻） |
|---|---|---|---|
| scdoc 容器 / SAB / facets / document.xml | ✅ **读 L2+ / 写 L2+（官方门禁通过）** | — | 内核侧语义（ACIS 类号表已逆向） |
| 几何造型（布尔/圆角/抽壳/拔模/阵列…） | ✅ 封装 **OCCT 7.9.3** | 内核 = OCCT（≠ACIS） | ACIS 数值语义、溢出/公差行为 |
| 草图约束求解 | ✅ LM 数值解 + DOF/冲突分析 | — | D-Cubed DCM 级鲁棒性、3D 草图 |
| 装配配合 | ✅ 7 类运动副求解 | — | PartDef/实例/配置（70 个装配 API 类型） |
| 钣金 / 曲面 | ⚠️ 各 5–6 个功能 | — | hem/bead/gusset/tab/junction、face-face blend、曲线网络 |
| 特征族（孔/螺纹/成形） | ✗ | — | 101 个 API 类型（BossForm/DimpleForm/Louver…） |
| 梁/焊件、制造、PMI、材料库 | ✗ | — | 整域 |
| CAE 网格 / 求解 | ✗（仅仿真准备数据模型） | — | ~90 命令类 / 70 类型；求解走 ANSYS 宿主（NYI-4） |
| 工程图标注体系 | ⚠️ HLR 三视图 + 图幅 + BOM | — | 132 个 API 类型（投影/局部/剖视/GD&T/条码…） |
| 渲染 | ⚠️ VTK 着色/边/透明 | KeyShot 入口（NYI-5） | 材质库/光照/光线追踪 |
| GUI | ✅ 18 页签 / 130 命令 / VTK 视口 | — | 完整交互语义（选择歧义循环、选项面板） |

**本质**：本仓是**自带内核的独立实现 + 官方格式互操作层**；"格式里的东西"做到了可被官方验证的深度，
"专业域里的东西"普遍是自研 MVP（L1–L2），"算不出来的东西"（网格/求解/材料/PMI）明确不入目标。

---

## 8. 评级与建议

| 维度 | 评级 |
|---|---|
| 格式解码（读） | **A−（95%，L2+–L3；官方库 6/6 实跑）** |
| 格式编码（写） | **A−（85%，L2+；官方双门禁本次独立通过）** |
| 几何内核封装 | **B（L2；OCCT 非 ACIS，数值等价不在目标内）** |
| GUI 壳层 | **B−（表面 ~90%，语义 ~55%；选项半接线）** |
| 直接建模 | **B−（78%，L2；无特征历史）** |
| 专业域（钣金/曲面/工程图/CAE/参数） | **C（55–74%，L1+～L2；整域缺失多）** |
| 测试可信度 | **C+（内核级 A、官方门禁 A；命令级仅 26/130，含 1 处恒真门禁）** |
| 文档可信度 | **C+（工程纪律与边界入册罕见地好；但 3 处文档漂移 + 自评口径偏高）** |

**优先级建议**

1. **P0 · 修门禁**：删 `test_p12_e2e.py:80` 的 `or True`（改为真实断言或显式 `pytest.skip`）；
   给**单体**官方打开补 `official_open` 回归（与装配同批）。
2. **P0 · 修遮蔽缺陷**：删 `sab_emit.py` 重复的 `_rec_header`（保留含 `cid is None` 分支的那份），
   补一条 `cid=None` 单测；清理 `kdoc.py` `Component` 重复字段/方法。
3. **P1 · 命令级回归补盲**：优先给"用户路径最短"的 104 条零提及命令加**行为级**冒烟
   （草图 13 图元 → 拉伸体积；约束 7 条 → 求解收敛；facet 5 条 → 网格不变量；repair 6 条 → 检出计数）。
   建议用参数化表驱动，一次覆盖多条。
4. **P1 · 选项接线收尾**：端点/中点捕捉接入拾取；fill/replace/split 补选项页；或把选项页灰显并标注
   "未接线"（宁缺勿假）。
5. **P1 · 文档收敛**：`function_gap_analysis.md` 域清单扩到官方 12+ 域、把 91% 拆成"格式层/功能层"
   双口径；`analysis_and_plan.md` 头部标注**历史归档**；§21.1 快照纳入测试数并修 cp1252 崩溃。
6. **P2 · 专业域纵深**（按 ROI，详见姊妹文档 §8）：特征族（孔/螺纹/成形）→ 特征历史/参数化 →
   钣金完整性 → 工程图标注 → 装配实例/配置 → CAE 网格。
7. **P2 · 仓库卫生**：清 `cyl_ref_sentinel.txt` / `_tmp` 残留；把 `.gitignore` 扩到 `*.sentinel.txt`；
   下一次触碰时顺带拆 `scdm_gui.py` / `scdoc_write.py`。

---

## 附：本报告用到的复核动作

- **全量回归**（conda env `scdm`，offscreen）：`pytest tests/ -m "not official" -q` →
  **244 passed / 1 skipped / 6 deselected / 86 s**（exit 0）。
- **官方门禁**：`pytest tests/ -m official_gate -q` → **5 passed / 20.0 s**；
  `pytest tests/ -m official_open -q` → **1 passed / 110.8 s**（真实 SpaceClaim 打开两体装配）。
- **官方库解析**：`python references/scan_library.py` → SrModels 6/6；
  samplemodel2 = 37 体/1,813 面/9,060 coedge，samplemodel5 = 80 体/1,288 面。
- **写端自审**：`python scdm_interop_check.py` → `records: 111 vs reference 111` / `audit: OK`。
- **官方基准枚举**：`Commands.dll` / `SpaceClaim.Api.V19.dll` 反射（2,806 / 3,490 类型）、
  `SpaceClaim.Api.V19.xml` 解析（612 类型 / 4,100 成员）、237 份 `*.scjournal` 提取页签与命令 ID。
- **静态复核**（AST/文本扫描）：重复定义（`sab_emit._rec_header`、`kdoc.Component`）、
  可变默认参数 0、裸 `except` 0、库内硬编码绝对路径 0、≥100 行函数 16 个、
  命令→测试提及 26/130、恒真断言 1 处、前缀豁免派发 17/130、选项页 4 个。
- **分层代码审计**：格式层 / 内核层 / GUI 层 / 数据脚本层 / 测试层（全部 file:line 级证据）。
