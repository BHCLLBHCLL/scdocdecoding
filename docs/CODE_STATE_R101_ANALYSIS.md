# 代码状态复核 × SpaceClaim 对标（R101 分析，2026-09-12 实测）

> **口径**：本文§1 的每个数字都由本轮新增的 `tools/state_inventory.py` 直接产出（一个事实一个来源，
> 纪律 84），复核命令见 §8；除§3 的官方基线外，全部数字在 **HEAD 99fed3a** 上重测。
> 官方基线引自 P3 期本机 **SpaceClaim 2019 R3（v195）** 反射实测（`docs/CODE_STATE_VS_SPACECLAIM.md` §2），
> **本轮未重测**——凡引用处都标注「P3 实测」。
>
> 关联：[IMPROVEMENT_PLAN_R102.md](IMPROVEMENT_PLAN_R102.md)（新一轮关键点）、
> [ROUND_R101_20260912.md](ROUND_R101_20260912.md)（本轮交付）、
> [CODE_STATE_VS_SPACECLAIM.md](CODE_STATE_VS_SPACECLAIM.md)（P3 期基线，本文 §7 逐条修正其过期结论）。

---

## 0. 结论摘要

1. **规模与验证**：Python **198 文件 / 49,727 行**（含 tests/tools/references/根模块）；`scdm` 包
   **49 文件 / 22,578 行 / 345 个模块级公开函数**；测试 **102 文件 / 14,310 行 / 680 条 `def test_`**；
   文档 `docs/*.md` **195 篇**；git **235 提交**。CI 口径全量（`-m "not official"`）本轮实测见 §1.3。
2. **命令面必须同时给三个口径**（D3，§6.3）：**ribbon 164 命令**（18 页签）/ **目录全集 178**
   （含 backstage 12 + QAT 5，去重 3）/ **live 29（内核不可用）·177（内核可用）**；占位 1（`safety.tab`，
   按设计保留）。GUI `scdm_gui.py` 5,443 行、**156 个 `_do_*` 处理器、0 个孤儿**。
3. **数据面仍是最强层**（R100 官方库验收，§5.4）：6 样例 **3,494 面**、真缺口 **1,328（83 条缝边）**、
   自由环 **269**；R80→R100 缺口 1,811→1,328、环 475→269；包围盒漂移全 0.0%。
   这是唯一与官方**对等**的层（官方 SabSatConverter + 官方 SpaceClaim 双门禁）。
4. **判定（双口径）**：格式/互操作层 **L2+～L3-**（≈95%+）；**域广度约官方用户可见命令面（P3 实测 602 类）
   的 1/4**；**共享域深度集中在 L1+～L2**。与 P3 期相比，主要矛盾已从「整域缺失」转为
   「**补齐了但深度不足**」：P3 期列的 7 个缺失整域里，梁/焊件、标准孔族、GD&T 标注三域已落地（§7）。
5. **结构性短板已被部分填平**（P3 期结论已过期，§7）：`kdoc` 现有 `Configuration` / `instances` /
   每体 `FeatureStack` / 文档级 `FeatureHistory`；`mates.py` 有 7 类运动副 + DOF 表；
   `sketch_solver.py` 是 LM 求解器（12 类约束 + DOF/冗余/冲突报告）；**20+ 处特征录制点**
   （pull/shell/draft/hole 族/dimple/louver/knockout/beam/gusset/tab/junction/cross_break/boss/fillet/chamfer
   + 文档级 mirror/pattern）。仍未填平的是 **GUI 侧的特征编辑闭环**与**设计历史树语义**（§5.2）。
6. **本轮发现 3 个可复现问题，修掉 2 个**（§6）：**D1** 快照门禁口径随解释器变化（已修 + 回归测试）；
   **D2** `con.perp` / `con.mid` 已实现、已 live、有处理器，却**没有 ribbon 入口**（已修：拆开
   合并按钮并补图标）；**D3** 命令面数字三口径在多份文档里被混用（已统一口径 + 快照自动块）。
---

## 1. 实测基线

### 1.1 总量（`python tools/state_inventory.py` 输出，含空行）

| 口径 | 实测 |
| --- | --- |
| Python 总量（scdm + scdoc_parser + tools + tests + references + 根模块） | **198 文件 / 49,727 行** |
| `scdm` 包 | **49 文件 / 22,578 行**；模块级公开函数 **345** 个 |
| `kernel.py` / `scripting.py` | 公开函数 **106** 个 / 脚本 op **52** 条 |
| 命令面 | 18 ribbon 页签 + 1 backstage；ribbon 命令 **164**、目录全集 **178**（backstage 12 + QAT 5，去重 3） |
| live | 内核不可用 **29** / 内核可用 **177**；占位 `safety.tab` |
| GUI 派发 | `scdm_gui.py` **5,443** 行；`_do_*` 处理器 **156** 个；孤儿 **0** 个 |
| 测试 | **102 文件 / 14,310 行**；`def test_` **680** 条；命令级提及 **126/178**，豁免声明 **55** 条 |
| 文档 | `docs/*.md` **195** 篇；仓库 `*.md` **204** 篇 |
| 最大模块 | `scdm_gui.py`（5,443 行） |

> 对照 P3 期（2026-09-12 上午）：26,262 行 / 89 文件、kernel 80 函数、130 命令、244 passed。
> 一天内增长主要来自 R81–R100 的八层接线与 GUI 观感打磨，以及 `scdm/gui/*` 拆分。

### 1.2 最大模块（本次实测行数）

| 模块 | 行 | 模块 | 行 |
| --- | --- | --- | --- |
| `scdm_gui.py` | 5,443 | `scdm/sheetmetal.py` | 756 |
| `scdm/kernel.py` | 2,307 | `scdm/gui/sheet.py` | 629 |
| `scdm/import_sab.py` | 2,270 | `scdm/drawing.py` | 605 |
| `scdm/scdoc_write.py` | 2,056 | `scdm/beams.py` | 583 |
| `scdm/gui/scene.py` | 1,733 | `scdm/sketch.py` | 578 |
| `scdm/sab_emit.py` | 1,717 | `scdm/gui/left_panel.py` | 528 |
| `scdm/gui/icons.py` | 1,132 | `scdm/mesh.py` | 493 |
| `scdm/scripting.py` | 935 | `scdm/kdoc.py` | 490 |

### 1.3 验证（本轮改动前，HEAD 99fed3a）

- CI 口径全量：**694 passed, 2 skipped, 8 deselected，414.9 s**（conda env `occ`，`QT_QPA_PLATFORM=offscreen`）；
- 快照门禁：`tools/gen_devplan_snapshot.py --check` —— **修复前**在默认解释器（无 OCC）下 **exit 1
  "snapshot STALE"**、在 `occ` 下 exit 0（D1，§6.1）；**修复后两种解释器都 exit 0**；
- 本轮改动后全量：**703 passed, 2 skipped, 8 deselected，394.3 s**（+9 条守卫，其余用例数不变）。

---

## 2. 命令面与可达性

### 2.1 页签分布（ribbon，共 164）

| 页签 | 命令 | 页签 | 命令 | 页签 | 命令 |
| --- | --- | --- | --- | --- | --- |
| 设计 design | **72** | 修复 repair | 7 | 详细 detail | 9 |
| 显示 display | 11 | 准备 prepare | 5 | 梁/焊件 beam | 3 |
| 组件 assembly | 11 | Workbench | 2 | 安全 safety | 1 |
| 测量 measure | 3 | 仿真 simulation | 7 | 工具 tools | 3 |
| 分面 facets | 5 | 标记 markup | 2 | KeyShot | 1 |
| 增材 additive | 4 | 曲面 surface | 6 | 文件 file | backstage 12 |
| | | 钣金 sheet | 12 | QAT | 5 |

波次分布（目录声明的里程碑，不是完成度）：**M1 22 / M2 20 / M3 25 / M4 44 / M5 53**。

### 2.2 三个口径的关系（D3）

- `ribbon 命令 164` = 18 个 ribbon 页签内所有按钮；
- `目录全集 178` = `all_commands()` = 164 ribbon + 12 backstage + 5 QAT − 3 重复 id
  （`file.new` / `file.open` / `file.save` 同时出现在 backstage 与 QAT，同名同 id，去重后 178）；
- `live` = `live_commands()` = `M1_LIVE`（29）∪ M2..M5（内核可用时）→ **29 / 177**；
- 两个 live 数在 D1 修复前**在任何解释器里都读 177**（因为生成器问的是「跑它的解释器」），
  修复后由 M1 清单直接给出 29，且 `--check` 不再依赖解释器。

### 2.3 可达性（本轮新增不变量）

- `scdm_gui.py` 的派发是 `getattr(self, "_do_" + cmd_id.replace(".", "_"))`（第 617 行）；
- **156 个 `_do_*` 处理器 / 0 个孤儿**（每个处理器都能追到目录或 live 里的 id）；
- 22 个目录 id 没有 `_do_*`：`tool.*`（3）、`mode.*`（3）、`show.*`（5）、`style.*`（4）、
  `measure.dist`、`gfx.*` 之外的分支处理项，以及 `safety.tab`（空壳）——**全部是刻意的**，
  由 `tests/test_g1.py` 的 `BRANCH_HANDLED` / `INTENTIONAL` 白名单固定；
- 覆盖率台账 `tests/test_coverage_ledger.py`：**55 条豁免声明 + 126 条被测试提及**，新增命令若不
  覆盖或不声明即失败。

---

## 3. SpaceClaim 对标（官方基线为 P3 实测，未重测）

### 3.1 官方规模（P3 实测）

| 来源 | 数值 |
| --- | --- |
| `Commands.dll`（6.3 MB） | 2,806 类型；**692 个 `*Command` 类**（剔除内部类后 **602**）；131 接口 |
| `SpaceClaim.Api.V19.dll` | 3,490 类型（剔编译器生成后 1,243）；**183 个 `I*` 接口** |
| `SpaceClaim.Api.V19.xml` | 612 个文档化类型 / 4,100 成员 |
| 命令关键字归类 | 直接建模 ~153 · CAE 网格/求解 ~90 · 钣金 ~89 · 修复检查 ~55 · 草图/2D ~46 · 梁/焊件 ~43 · 工程图/标注 ~42 · 渲染 ~39 · 其他 ~200 |
| 域 API 类型数 | 工程图/标注/GD&T 132 · 钣金 103 · 成形/孔/螺纹 101 · 互操作 82 · 装配 70 · 网格/CAE 70 · 渲染 62 · 参数/特征 55 · 结构/视图 38 · 梁/焊件 37 |

**量级结论**：官方用户可见命令面 ≈602 类，我们 **164 条 ribbon 命令**；粒度不可逐条对齐，
但**广度差 ≈4×**，且官方在「整域」维度上仍有 3 个域我们没有（§4.2）。

### 3.2 页签级对照（更新 P3 表）

| 官方页签（journal 实测） | 我们的对应 | 判定 |
| --- | --- | --- |
| Design | 设计 **72** 命令 / 10 组 | 有，广度仍小于官方（~153 命令类） |
| View | 显示 11 | 有 |
| Measure | 测量 3（测量/质量属性/干涉） | 覆盖主要手段 |
| Facets | 分面 5 | 有 |
| AdditiveMfg | 增材 4 | 命令数相当（官方 4 个 Additive*） |
| CaeRepair / CaePrepare | 修复 7 / 准备 5 | 有；官方各 ~55 / ~90 命令类 |
| Analysis | 仿真 7（数据模型 + 网格） | 有网格（面/体/报告），无求解链（NYI-4） |
| Workbench | Workbench 2 | 仅参数/发布 |
| SheetMetal | 钣金 **12** | 官方 ~89 命令类，深度仍差 |
| Detailing | 详细 **9** | 官方 ~42 命令类 + 132 API 类型 |
| GetKeyShot | KeyShot 1 | 仅入口（NYI-5） |
| Assembly | 组件 **11**（含配置保存/应用） | P3 期「缺整域」已不成立（§7） |
| **Insert** | 无独立页签（散在 设计▸插入） | **仍缺页签**（形态差异，低优先） |
| **AssemblyConfigurations** | 组件页 2 命令（`asm.config` / `asm.config_apply`） | 有最小实现（配置=可见性/抑制/属性/数量快照） |
| EditSketch | 无专用模式页签 | 形态不同（不高优先） |
| Journal / RS | 工具 3（脚本/录制/自定义） | 部分对应 |
| 梁/焊件（官方并入 Design/Detailing） | 梁/焊件 **3** + `beams.py` 583 行 | **P3 期「整域缺失」已不成立**（§7） |

### 3.3 域级深度对照（本轮口径：域 → 我们的实测实现 → 深度）

| 功能域 | 我们的实测（文件 / 公开 API / 命令） | 深度 | 关键缺口 |
| --- | --- | --- | --- |
| scdoc 读端 | `import_sab.py` 2,270 行 / 11 API；22 类 SAB 记录字段级解码；官方库 6/6 | **L3-** | 读端不产字节 |
| scdoc 写端 | `scdoc_write.py` 2,056 + `sab_emit.py` 1,717 + `sat_write.py` 467；官方双门禁 | **L2+** | 字节恒等（NYI-1 信息论不可行） |
| 互操作 | STEP/IGES/STL/OBJ/3MF/VRML/BREP/DXF/SVG/PNG 读写 + X_T 官方管线 | **L2** | CATIA/Parasolid 直读、PMI（NYI-2/6） |
| 直接建模 | `kernel.py` 106 API；pull_auto、变半径圆角、多厚度抽壳、中性面拔模、路径/填充阵列、分割、替换、填充 | **L2** | Detach/Merge/Extend/Unroll/MakeThin 等命令族 |
| 草图与约束 | `sketch.py` 21 API + `sketch_solver.py` LM 求解（12 类约束、DOF/冗余/冲突）；13 图元命令全 live | **L2-** | 无 3D 草图；曲线编辑（trim/extend/offset）仍薄 |
| 装配与配合 | `mates.py` 7 类运动副 + DOF 表；`kdoc` `Component`/`Configuration`/`instances`；11 命令 | **L2-** | 无齿轮/齿条副；配置语义只到可见性/抑制/属性 |
| 参数与特征 | `features.py` `FeatureStack`（每体）+ `FeatureHistory`（文档级）；**20+ 录制点**；`replay_document`；参数改动重放有测试 | **L2-** | GUI 特征编辑闭环、特征重排/抑制、设计历史树语义（§5.2） |
| 钣金 | `sheetmetal.py` 756 行 / 19 API；K 因子、多弯链展开、撕裂、角释放、折弯槽口、jog、卷边、加强筋、接缝、十字压筋、圆锥/轴向折弯；12 命令 | **L2-** | 折弯表标准化、成形特征库、展开图工程化输出 |
| 曲面 | `surface.py` 9 API：untrim/extend/offset/thicken/多约束 patch/blend-loft | **L1+** | face-face blend、曲线网络、trim-by-surface |
| 修复与检查 | 6 检出器 + 自动修复 + 未封闭度报告（真缺口/缝边/自由环）+ 7 命令 | **L2-** | 去毛刺、标准孔/成形识别、模型清理命令族 |
| 测量 | 点点/边边/面面（距+夹角）/柱面半径 + 质量属性 + 干涉 | **L2-** | 投影面积等专业量 |
| 工程图/标注 | `drawing.py` 16 API + `annotation.py` `Leader`/`GdtFrame`/`Datum` + `dimchain.py` 尺寸链（极值/RSS + 链线）；DXF/SVG 双导出 | **L2-** | 孔标注/中心线/粗糙度/剖面线填充、局部/旋转剖 |
| CAE 准备与网格 | `mesh.py` 12 API（面网格/体素四面体/质量报告）+ `simprep.py` 载荷/支撑/接触 | **L1+** | 网格控制/Blocking/求解链（NYI-4） |
| 增材 | `additive.py` 5 API：构建体/取向/支撑/点阵 | **L1** | 切片/机输出/悬垂分析 |
| 渲染/外观 | VTK 着色/边/透明/剖面 + KeyShot 入口 | **L1** | 材质库/光照/光线追踪（NYI-5） |
| 结构树/图层/视图 | 结构树 + 图层 tab + 命名选择 + 用户组 + `saved_views`（视图 tab） | **L1+** | 用户图层系统、配置树、选择集历史 |
| 梁/焊件 | `beams.py` 583 行 / 11 API：7 类截面 + 15 条 GB 规格（含槽钢 C）+ 焊接符号 | **L2-** | 型材库扩展、节点/组元管理 |

---

## 4. 完整性评估

### 4.1 覆盖

- **用户路径覆盖（自评）**：新建→草图→直接建模→特征→钣金/曲面→装配→工程图→导出 的主链**已连通**，
  每一环都有 e2e 或行为测试；官方库 6/6 可解析、写端过官方双门禁。
- **命令级验证**：126/178 被测试提及，其余 55 条逐条在台账里写明理由（GUI 对话框 / 宿主组件 / 共享实现）。
- **未实现占位**：仅 `safety.tab`（1 条，按设计保留空壳，DEV_PLAN §17）。

### 4.2 仍未覆盖的整域（更新 P3 结论）

P3 期列的 7 个缺失整域，现状：

| P3 期结论 | 现状（本轮实测） |
| --- | --- |
| 梁与焊件 | **已落地**：`beams.py` 583 行 / 11 API / 15 条 GB 规格 / 焊接符号 + 3 命令 |
| 标准孔/螺纹/成形 | **已落地**：简单/沉头/锥沉/攻丝孔 + 凸台/凹坑/百叶/敲落/角撑/舌片 |
| PMI/GD&T 标注 | **已落地（2D 图纸侧）**：`Leader`/`GdtFrame`/`Datum` + DXF/SVG；3D PMI 读取仍为 NYI-6 |
| CAE 网格 | **部分落地**：面网格 + 体素四面体 + 质量报告；Blocking/求解链仍缺 |
| 制造（去毛刺/刀路） | **仍缺**（整域） |
| 命名视图 | **部分落地**：`session.saved_views` + 视图 tab 保存/调用；无缩略图/动画 |
| 装配配置 | **最小实现**：`Configuration`（可见性/抑制/属性/数量）；无替换件/驱动尺寸 |
| （P3 未列）参考图像 | **仍缺**（插参考图/标定比例） |
| （P3 未列）用户图层系统 | **仍缺**（图层仅存在于 DXF/SVG 注释层） |

### 4.3 边界项（NYI）复核

`docs/NYI_INVENTORY.md` 6 条产品边界（字节恒等、CATIA/Inventor/DWG 直读、ACIS 数值 bit 等价、
ANSYS 求解语义、KeyShot 材质库、PMI 读取）**本轮复核仍成立**，无需改动；TODO 列表中仅
TODO-4 的 face-face blend 仍挂「另立项」。

---

## 5. 深度评估（比命令条数更重要）

### 5.1 真机制（有独立数学 / 求解器 / 闭式验收）

| 机制 | 证据 |
| --- | --- |
| scdoc 写端 FIFO 遍历 | 官方 141 记录 golden 复现 + SabSatConverter restore + SpaceClaim 打开 bodies=1/2 |
| 导入未封闭度 | 缺口/缝边/自由环三量 + 缺口点；R84 容差 1e-6→1e-5（缺口 −58、面数零损失） |
| 裁剪修复 | 候选 V2/V3/V5 + 便宜优先闸门（BRepCheck 0.003 s → GProp 0.049 s）+ 按导入缓存（79→41 次） |
| 草图求解 | LM（数值 Jacobian）+ DOF = rank 缺额 + 冗余行 + 冲突检测 |
| 装配运动副 | 7 类 + DOF 表 + 闭式变换矩阵；爆炸位移三种公式可数、帧位移 = 终态 × t |
| 特征重放 | `FeatureStack.apply` 按序重放 20+ op；参数改动重放、栈 round-trip 有测试 |
| 钣金展开 | K 因子 + 中性层展开长；多弯链「各平板恰一次 + Σ 折弯余量」；圆锥/轴向折弯各有 allowance |
| 尺寸链 | 极值 + RSS 并列 + 链线注记，DXF/SVG 端到端断言 |
| 网格质量 | 面积对拍 / 退化计数 / 长宽比·最小角·雅可比分布；体素四面体体积闭式对拍 |
| 性能 | `perf.py` 峰值/常驻内存 + 基线 JSON + 五条交互路径回归 |

### 5.2 仍薄的部分（门面风险）

| 部分 | 实测 | 风险 |
| --- | --- | --- |
| 撤销/重做 | `history.py` **47 行**，Shape 快照栈（limit 50） | 与特征栈并存但**不联动**：改参数不会自动重放整链 |
| 参数化构造器 | `params.py` 201 行，仅 box/cylinder 两个 `build` | 参数驱动仍集中在特征栈，GUI 参数表只驱动 parametric 体 |
| 选择模型 | `selection.py` 49 行；捕捉只「栅格」参与拾取 | 端点/中点/重合捕捉仍未进拾取（P3 期结论仍成立） |
| 3D 草图 / 曲线编辑 | `sketch.py` 21 API；trim/offset 有实现，extend 无 | 草图域天花板 |
| 3D PMI / 参考图像 / 用户图层 | 无 | 整域缺口（§4.2） |
| 巨文件 | `scdm_gui.py` 5,443 行 / 297 个 `def` | 维护性风险（P3 期 4,208 行，仍在增长） |

### 5.3 深度自评（更新 P3 表）

| 层 | P3 期 | 本轮 | 变化依据 |
| --- | --- | --- | --- |
| 格式/互操作 | L2+～L3- | **L2+～L3-**（≈95%+） | 无变化，仍是唯一对等层 |
| 域广度（vs 官方 ≈602 类） | 20–25% | **≈25%**（164/602，粒度不可逐条对齐） | 命令面 130→164 |
| 域深度（共享域） | 集中 L1–L2 | **集中 L1+～L2-，钣金/工程图/特征三域各上一个台阶** | §3.3 逐域证据 |

---

## 6. 本轮实测缺陷与处置

### 6.1 D1 快照门禁口径随解释器变化（**已修**）

- **现象**：提交块记为 `177 live（内核不可用）`（与「内核可用」同值）；
  `python tools/gen_devplan_snapshot.py --check` → `snapshot STALE - run --update`（exit 1）；
  同一命令在 `occ` 解释器下 → `snapshot current`（exit 0）。
- **根因**：生成器用 `len(live_commands())` 填「内核不可用」格——它回答的是**跑它的解释器**，
  而不是「内核不可用」这一条件；提交块由 `occ` 环境生成，两格于是相同。
- **真值**：内核不可用时 live = `M1_LIVE` = **29**（默认解释器实测）。
- **修复**：新增 `live_counts()`，用 M1/M2..M5 清单直接算两格（**不再调用进程内 `live_commands()`**）；
  `tests/test_snapshot_tool.py` 增加两条：monkeypatch `available()` 双向验证 29 的不变性与
  「两格必须不同且都出现在行里」。
- **验收**：两种解释器 `--check` 均 `exit 0`；提交块改为 `**29 live（内核不可用）** / **177 live（内核可用）**`。

### 6.2 D2 已实现、已 live、无入口（**已修**）

- **现象**：`con.perp`（垂直）与 `con.mid`（中点）在 `M3_LIVE` 中、在 `scdm_gui.py` 有真实
  处理器（`kind == "perp"` / `"mid"` 分支，含两条线段的参数校验），但 ribbon「约束」组只有 7 个按钮，
  且目录里是两条**合并按钮**：`con.par` 名为「平行垂直 / Par/Perp」、`con.fix` 名为「中点固定 / Mid/Fix」。
  后果：**按钮承诺的功能只实现了一半**（平行做了、垂直没按钮），而垂直/中点两条真实路径**从 UI 不可达**，
  `all_commands()` 也不列它们（覆盖率台账因此漏算）。
- **修复**：拆成四条独立命令 `con.par / con.perp / con.mid / con.fix`（名称/英文名同时纠正），
  在 `scdm/gui/icons.py` 补 `perp`（直角 + 方框标记）与 `mid`（线段 + 中点实心点）两个矢量图标；
  `tests/test_g1.py` 新增不变量 **live ⊆ 目录**（`test_every_live_id_has_a_command_entry`）。
- **验收**：ribbon 命令 162→**164**、目录 176→**178**；快照自动块同步；`--check` 通过；
  新增不变量在旧代码上必失败（`con.perp`/`con.mid` 不在目录）。

### 6.3 D3 命令面数字混用（**已收口**）

130/162/176/177 在 `CODE_STATE_VS_SPACECLAIM.md`（130）、旧 `DEV_PLAN.md` §21.1（130/144/162/177）、
`analysis_and_plan.md`（125/113）等处并存且**未标口径**。本轮：§1.1/§2 统一为
**ribbon 164 / 目录 178 / live 29·177**，并让 `tools/state_inventory.py` 成为这些数字的唯一来源
（`DEV_PLAN.md` §21.1 自动块同步刷新；手写补充行里过期的 `kernel 80 → 106`、`ops 33 → 52` 一并修正）。

---

## 7. 对 P3 期对标文档的修正（过期结论清单）

| P3 期结论（`CODE_STATE_VS_SPACECLAIM.md`） | 本轮实测 |
| --- | --- |
| §5.1「没有设计历史（最大结构差）」：`KernelDoc` 只有 bodies/sketches/components/mates/parametrics/… | **已过期**：`KernelDoc` 现有 `features`（每体 `FeatureStack`）、`document_features`（`FeatureHistory`）、`instances`、`configurations`、`active_configuration`、`weldments`、`properties`、`meshes`、`import_report`；`replay_document()` 可整档重放 |
| §5.2「参数化名不副实」：只有 box/cylinder 两个构造器 | **部分过期**：`params.py` 仍是 2 个构造器，但**特征栈**已覆盖 20+ op（pull/shell/draft/hole 族/dimple/louver/knockout/beam/gusset/tab/junction/cross_break/boss/fillet/chamfer + mirror/pattern），参数改动重放有测试（`test_features.py::test_feature_history_replays_on_parameter_change` 等 5 条） |
| §5.3「装配是扁平列表，无 PartDef/实例/配置」 | **已过期**：`kdoc` 有 `Component`/`Configuration`/`instances` + `add_instance`/`instances_of`/`sync_instances`/`apply_configuration`/`capture_configuration`/`config_issues`/`bom`；`mates.py` 7 类运动副 + DOF 表 |
| §5.6「`kdoc.Component` 重复定义 `lightweight` / `lightweight_body_ids()`」 | **已修**：现各定义一次（本轮回读 30–52 行确认） |
| §3「官方有、我们没有的整域」：梁焊件、标准孔/螺纹、PMI/GD&T | **三域已落地**（§4.2）；仍缺：制造/去毛刺、参考图像、用户图层、3D PMI 读取、装配替换件/驱动尺寸 |
| §6「命令面 130 条」 | 现 **164 ribbon / 178 目录**（口径见 §2.2） |
| §1「测试 244 passed / `def test_` 236」 | 现 `def test_` **680**、CI 口径 **694 passed**（本轮改动前） |

---

## 8. 复现命令

`@powershell
$py = "$env:USERPROFILE\.conda\envs\occ\python.exe"   # OCC 只在 occ 环境

# 1) 状态清单（本轮新增，唯一来源）
python tools/state_inventory.py
python tools/state_inventory.py --json

# 2) 命令面快照门禁（两种解释器都必须 exit 0）
python tools/gen_devplan_snapshot.py --check
& $py tools/gen_devplan_snapshot.py --check

# 3) 本轮新增/加固的门禁
& $py -m pytest tests/test_state_inventory.py tests/test_snapshot_tool.py tests/test_g1.py -q

# 4) 全量（CI 口径）
$env:QT_QPA_PLATFORM='offscreen'
& $py -m pytest tests/ -m "not official" -q
`@

---

## 9. 一句话结论

**格式层已经对等（L2+～L3-，有官方双门禁背书），命令面广度约 1/4，域深度集中在 L1+～L2-；
P3 期指出的三个结构性短板（设计历史、参数化、装配结构）已从「没有」变成「有骨架、缺闭环」，
下一步的 ROI 不在再加命令，而在把已有的机制接到 UI 闭环上（特征编辑/配置/配合），
并把剩余的未封闭度（SampleModel4 335/72、samplemodel2 990/195）继续压下去。**
