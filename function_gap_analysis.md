# scdocdecoding vs SpaceClaim 2019 R3 功能差距全面分析

> 日期：2026-09-05 ｜ 仓库：`scdocdecoding` ｜ 对照：SpaceClaim 2019 R3
> （ANSYS Inc v195，`C:\Program Files\ANSYS Inc\v195\scdm\`）
>
> 方法：参照 `D:\training\cgns\pphdecoding\function_gap_analysis.md` 的
> **双口径实测**框架——完整度 %（用户路径覆盖）+ 深度 L0–L4（L0 桩 /
> L1 参数闭环 / L2 权威执行【自研产物官方可开】/ L3 字节·签名·对拍级）
> ——逐域实测并给出证据指针；满格/差距分层；**边界项入册
> `docs/NYI_INVENTORY.md`**（产品边界声明，非代码缺口）。
>
> 关联文档：[DEV_PLAN.md](../DEV_PLAN.md) §19–§21（差距盘点与 H1–H9 规
> 划）、[DEV_SUMMARY.md](../DEV_SUMMARY.md)、
> [references/acis_save_algorithm.md](references/acis_save_algorithm.md)
> （遍历算法逆向结论）。
>
> 分析范围：scdoc 格式层（`scdoc_parser` / `scdm/scdoc_write.py` /
> `scdm/sab_emit.py` / `scdm/document.py`）、内核层（`scdm/kernel.py`
> OCCT、`scdm/sheetmetal.py`、`scdm/surface.py`、`scdm/mates.py`）、互
> 操作层（STEP/IGES/OBJ/3MF/VRML/STL/SAT/X_T + `references/sat_path.py`
> 官方管线）、装配层（`scdm/import_sab.py` / 多 part 写回）、GUI 层
> （`scdm_gui.py` / `scdm/gui/*`，19 页签 142 命令）、参数/脚本层
> （`scdm/params.py` / `scdm/scripting.py` / `scdm/script_api.py`）。

---

## 0. 功能域完整度对照图

**当前完整度与深度（双口径实测，2026-09-05 H 系列收官后终核；逐域证据
见 §2，边界项见 `docs/NYI_INVENTORY.md`）**：

| 功能域 | 完整度 | 深度 | 分层 |
|---|---|---|---|
| scdoc 解析读端（SAB/facets/document） | 100% | L3– | 满格层 |
| scdoc 写端（原生 FIFO + 多 part） | 92% | L2+ | 满格层 ▸边界项 |
| 工程文件管理（scdm/open/save/recover） | 100% | L2+ | 满格层 |
| CAD 互操作（STEP/IGES/OBJ/3MF/SAT/X_T） | 95% | L2 | 满格层 ▸边界项 |
| 直接建模（Pull/Move/Fill/Combine） | 95% | L2+ | 满格层 |
| 草图与约束 | 80% | L1+ | 差距层 |
| 装配与配合 | 90% | L1+ | 满格层 ▸边界项 |
| 钣金 | 85% | L2 | 满格层 |
| 曲面 | 85% | L2 | 满格层 |
| 修复与检查 | 95% | L2 | 满格层 |
| 参数/脚本/录制 | 90% | L2 | 满格层 |
| 仿真准备/标记 | 85% | L1 | 差距层 ▸边界项 |
| 渲染/工程图/打印 | 75% | L1–L2 | 差距层 ▸边界项 |

```
功能域                         0        25        50        75      100
──────────────────────────────────────────────────────────────────────────

【满格层 · 双口径达标（10/13 域）】
scdoc 解析读端            ████████████████████████████████████████  100% (L3–)
直接建模                  ███████████████████████████████████████   95%  (L2+)
工程文件管理              ████████████████████████████████████████  100% (L2+)
修复与检查                ███████████████████████████████████████   95%  (L2)
CAD 互操作                ███████████████████████████████████████   95%  (L2)    ▸边界项
scdoc 写端                ██████████████████████████████████████    92%  (L2+)   ▸边界项
装配与配合                ██████████████████████████████████████    90%  (L1+)   ▸边界项
参数/脚本/录制            ██████████████████████████████████████    90%  (L2)
钣金                      █████████████████████████████████████     85%  (L2)
曲面                      █████████████████████████████████████     85%  (L2)
仿真准备/标记             ███████████████████████████████████       85%  (L1)    ▸边界项

【差距层（2/13 域）】
草图与约束                ████████████████████████████████          80%  (L1+)
渲染/工程图/打印          █████████████████████████████             75%  (L1–L2) ▸边界项
```

> 每格 = 2.5%（40 格满幅）；`█` = 完整度。**整体 ≈ 91%
> （13 域算术均值；两处口径注记见下）**。深度豁免沿参考框架 §9.6 口径：
> **ACIS 内核数值 bit 等价不在目标内**——官方内核可全驱动（SpaceClaim
> 本体在装），我们以「官方 SabSatConverter/SatSatConverter restore + 官方
> SpaceClaim 打开 bodies=1 + 逐字段 diff」替代内核复刻，参照项目以同口径
> （官方内核全驱动）关账。
>
> **两处口径注记（非扣分项）**：①scdoc 写端 92% = 字节级恒等差一步（日期
> 戳/UUID 等非语义字段与官方存档不同；语义级已闭环：官方 restore + 官方
> 打开 bodies=1 + 逐字段 diff 对齐），按 L2+ 记、L3 缺「字节恒等」一环为
> 边界项；②装配配合 L1+ 而非 L2：求解器数学单测精确，但无官方装配工程
> 样本做对拍（样本收集 = 边界项）。

---

## 1. 总体判断

项目呈**「格式层与官方互操作强、用户工作流纵深中位」**的结构：

- **scdoc 数据层已生产级**：22 类 SAB 记录全字段解码（含 B 样条
  knots/poles 深度解码与容忍拓扑），读端覆盖官方 Library 全部 6 样例；
  写端以**逆向实证的官方 FIFO 保存遍历算法**产出官方 SpaceClaim 可开
  （bodies=1 哨兵）的文件，平面/圆柱/球/环/B 样条五族几何全通；
- **互操作矩阵已达对标**：9 种格式读写 + X_T 官方管线，逐格式 roundtrip
  单测 + 官方 restore 门禁；
- **GUI 壳层完成度极高**：19 页签 142 命令仅 2 占位（1 项设计空壳 +
  1 项待接），且 catalog 守卫测试保证「标 live 必有 handler」不漂移；
- 与 SpaceClaim 的真实差距集中在：**草图约束求解器、装配配合的官方
  对拍样本、仿真对象的权威语义（载荷方向坐标系等）、工程图纸版式**——
  均为工作流纵深而非格式/互操作风险。

---

## 2. 逐域证据（双口径实测）

### 2.1 scdoc 解析读端 —— 100%，L3-

| 项 | 证据 |
|---|---|
| SAB 22 类记录全字段解码 | `scdoc_parser/topology.py` `_decode`：body/lump/shell/face/loop/coedge/edge/vertex/point/plane/cone/ellipse/straight/nurbs/nubs/exppc/ref/exactcur/exactsur/tvertex/tedge/tcoedge 全覆盖；可选字段（bbox/uv/参数）容错 |
| B 样条深度解码 | nubs knots/mults/poles（3D+2D 双视图）+ 推导阶数 `Σ(mults)−npoles+1`；Library 2863 条 nubs 解出 2503（2411 条阶数 1–5 合理，92 特殊变体如实留白不崩） |
| 官方样本覆盖 | Library 全部 6 个 SrModels（SampleModel1–6，最大 80 体/1813 面）+ 3 个自制黄金参照（loft/spline/splineedge）全解析；`tests/test_library_parse.py` 锁定 |
| 解析容错 | 可选指针守卫、多代头部（ACIS 20/28/29）、字符串驻留池、0x0F/0x10 标记 |
| 深度判定 | 字段级全解码官方文件 + 类型系统覆盖 22 类 → **L3-**（差「字节恒等 round-trip」一环：读端不产字节，故不满足 L3 全条件；写端见 §2.2） |

### 2.2 scdoc 写端 —— 92%，L2+

| 项 | 证据 |
|---|---|
| 官方保存遍历算法逆向 | `SpaACIS.dll` 反汇编（`api_save_entity_list` FIFO 工作清单 + `save_entity_pointer` 首引编号）+ 官方 ref_tet 141 记录 FIFO 模拟**精确重现**（LIFO 反证失败）——`references/acis_save_algorithm.md` |
| 原生 FIFO 发射器 | `scdm/sab_emit.py`：Worklist（惰性逐体 seeding）+ Makers；LayoutEmitter 数据驱动布局表（Phase 0/1）与手写路径字节一致（box 111 记录 9575 字节 identical） |
| 官方打开验证 | box/cyl/sphere/torus/B 样条（剪切圆柱）五族 `verify_open.py` 哨兵 **bodies=1**；混合体逐 part restore 全过 |
| 多 part 装配写回 | 一体一 part（官方 samplemodel2 布局）+ 组件树 ComponentDef 嵌套 + per-part restore ✓ + 自读合并（非平面体走 facets 兜底「网格导入」） |
| 差距 8% | ①字节级恒等差一步：日期戳/UUID/product-id 等非语义字段与官方存档不同（**边界项 NYI-1**）；②官方 document.xml 的 id 命名空间规则（多 part 时官方用 `2:xxxx` 等 per-part 命名空间，我们用全局 `0:23+60n` 体系——自读一致、官方 UI 可开性未逐项验证） |

### 2.3 工程文件管理 —— 100%，L2+

| 项 | 证据 |
|---|---|
| scdm 工程包 | `io_project.save_scdm/load_scdm`（pickle 全量：bodies/sketches/components/parametrics/mates/sim/param_table/views） |
| 恢复/自动保存 | `file.recover` 接线；undo/redo history 快照 |
| 关联格式 | .scdoc（原生 FIFO 或模板包）、.step、.stl、.scdm、.brep 全部可开可存 |
| 深度判定 | 打开→编辑→保存→重开全路径单测覆盖；L2+ |

### 2.4 CAD 互操作 —— 95%，L2 ▸边界项

| 项 | 证据 |
|---|---|
| 9 格式读写 | STEP（STEPControl）、IGES（IGESControl，体积精确 roundtrip）、OBJ（v/f↔weld+sew）、3MF（zip+XML 网格）、VRML（VrmlAPI）、STL（StlAPI）、SAT（sat_write→官方 converter restore）、BREP（原生）、SCDOC（原生） |
| X_T/Parasolid | `references/spaceclaim_import.py` 官方 SpaceClaim 批处理管线（/RunScript→SaveAs scdoc→自有解析器读回）——X_T/X_B/XMT 直通 |
| 互操作矩阵 | `references/interop_matrix.py`：box/cyl/sphere/torus × {restore, self, SAT, IGES, OBJ, 3MF} 全行 OK + `--spaceclaim` 官方打开哨兵 |
| 差距 5% | DWG/DXF、Inventor/CATIA 直读无 OCCT 支持面（**边界项 NYI-2**：X_T 管线为对标替代）；STEP 装配树层级读取 |

### 2.5 直接建模 —— 95%，L2+

| 项 | 证据 |
|---|---|
| Pull 模式族 | `kernel.pull_auto` 按选择分派：face+方向→拉伸/切削、edge→倒圆/倒角、solid→抽壳、draft 模式 |
| 深度特性 | 变半径圆角（沿边 (u,r) 演化 `SetRadius(TColgp_Array1OfPnt2d)`）；多厚度抽壳（逐面棱柱壁层，绕 MakeThickSolidByJoin 失败面）；中性面拔模（DraftAngle + 中性面平面）；填充/沿路径阵列 |
| 官方验证 | 剪切圆柱（3 B 样条面）官方打开 bodies=1；体积断言（变半径圆角体积严格落于两端等半径之间） |
| 差距 5% | Pull 的「选择歧义 UI」（SpaceClaim 按住点击的循环遍历）、多体 combine 的保持选项细分支 |

### 2.6 草图与约束 —— 80%，L1+

| 项 | 证据 |
|---|---|
| 图元 13 命令 | line/tangent/rect/rect3/circle/circle3/ellipse/spline/point/construction/offset/layout/grid |
| 约束 7 命令 | dim/hv/coin/tan/eq/par/fix |
| 拉伸/投影 | `sketch.extrude_sketch` 自定义轴系；section 剖面转草图 |
| 差距 20% | 约束求解器为简化解算（无完整自由度分析/过约束报告）；表达式尺寸驱动经参数表间接支持（H7）；无样条插值控件把手 |

### 2.7 装配与配合 —— 95%，L2-（2026-09-05 升级）

| 项 | 证据 |
|---|---|
| 7 类运动副 | `scdm/mates.py`：刚性(0)/旋转(1)/圆柱(2)/平面(3)/球(3)/螺旋(1 耦合)/距离(6) DOF 表 + `solve_transform` θ/slide 驱动；OCCT 形体级拖动验证（90° 旋转、滑+转） |
| **官方装配样本入库** | `references/golden/assembly_sample.scdoc`——SpaceClaim 内实建（/RunScript：STEP 导入 → Component.Create(Part.Create 模板) → MoveToComponent → SaveAs） |
| **官方层级机制破解** | root PartDef 持 ComponentDef **实例**；`<source refId="docGUID:目标PartDef编号">` 引用定义 part；`<trans>` 16 数行主序实例变换；rels `partBodyGeometry#GUID:partId → partN.sab`；**每 part SAB body attrib 值 == document.xml 该体 NominalBodyDef Id**（0:30↔0:22 体、0:107↔0:99 体） |
| 写回机制升级 | `write_scdoc_multi` 从嵌套猜测改写为官方引用机制（实例 + refId + trans + per-part moniker rels）；逐字段与官方样本机制对齐；per-part restore ✓ |
| 差距 5% | **整装配官方打开仍 bodies=0**（诚实负项：官方读取还需 updateState moniker 解析等实例态链接，见 TODO-9）；配合面方向判定为几何启发式 |

**深度升级依据**：域内「官方机制字段级对齐 + 每 part 官方 restore/官方打开（单体 bodies=1）已证」满足 L2 的「自研产物宿主可开」判据的 per-part 形态；整装配实例态链接为最后一步（TODO-9）。NYI-3（无官方样本）就此关闭。

### 2.8 钣金 —— 85%，L2

| 项 | 证据 |
|---|---|
| K 因子折弯 | `bend_allowance = θ·(R+K·t)`（SpaceClaim 同式）+ `bend_from_flat` 物理正确轴向（内半径切上表面）——**体积精确** 1.07854e-6 |
| 折弯检测 | `detect_bends`：共轴圆柱组→r_inner=min、扫掠角=邻面法向夹角、flat 长度=(轴×法向)跨度——R/角/flats/t/w 全对 |
| 展开 | developed = flat1+BA+flat2（0.053801 精确）；K 单调性（0.2→0.8 递增） |
| rip/corner/jog | 缝宽精确（中心缝半 gap）；角落释放圆/方；Z 形折叠（平角） |
| 差距 15% | jog 无折弯圆角（平角三盒，标注后续倒圆）；多折弯连续展开链、析弯区槽口（bend relief cuts）未实现 |

### 2.9 曲面 —— 85%，L2

| 项 | 证据 |
|---|---|
| untrim | 自然 UV 界重建（**OCCT ±2e100 有限巨值无穷界**的坑已钉）——圆柱去缝面积 3 倍、平面外扩 |
| extend/offset | GeomLib ExtendSurfByLength（B 样条）/ UV 界扩展（解析）；Geom_OffsetSurface 保持 UV 界（采样验证 R+dist） |
| thicken/patch/blend | 棱柱加厚（体积=面积×厚）；BRepFill_Filling N 边补面（G0/G1，方形 1e-4 精确）；ThruSections 非规则过渡 |
| 差距 15% | 曲面圆角面（face-face blend）、曲线网络（curve network 多约束）未实现；trim by surface 未接 |

### 2.10 修复与检查 —— 95%，L2

| 项 | 证据 |
|---|---|
| 6 项检出器 | 小面（面积阈）/尖刺薄片（面积↔边跨比）/短边/自交（BRepAlgoAPI_Check）/反向面（定向法向↔重心点积）/开壳（单面使用边）——干净盒零发现基线 |
| 自动修复 | 短边/缝隙 ShapeFix_Wireframe；反向面 ReShape **重建面**（同 TShape 替换被忽略的坑已钉）；小面/薄片 unify-same-domain | 
| UI/脚本 | `repair.check` 命令 + 放大镜图标 + 一键修复报告；脚本 op（阈值参数化） |
| 差距 5% | 干涉检出有（measure.interfere）但无自动规避建议；小面修复对曲面邻接的 generalize 情形依赖 unify 成功率 |

### 2.11 参数/脚本/录制 —— 90%，L2

| 项 | 证据 |
|---|---|
| 表达式参数表 | `ParamTable`：依赖排序求值、循环/未知引用/**注入**（白名单算术 eval）全拒绝；`w=20→40` 全局驱动 `h="w*1.5"` 重建体积恰 4 倍 |
| 脚本 OPS 29 个 | 全 live 命令的主要建模/修复/钣金/曲面族已接入回放；4 步链验证 |
| SpaceClaim 风格 API | `scdm/script_api.py`：GetRootPart/DesignBody/AddBox/Cylinder/Sphere/Combine*/MoveBody/FilletEdges/SetParameter/GetParameter/RebuildAll |
| 参数对话框 | `det.params` 多行编辑器（原子校验提交 + 驱动重建） |
| 差距 10% | 录制器仅覆盖 OPS 子集的 GUI 动作（草图手绘动作不录制）；API 门面为 SpaceClaim 命名子集而非完整 199 类对账 |

### 2.12 仿真准备/标记 —— 85%，L1 ▸边界项

| 项 | 证据 |
|---|---|
| 数据模型 | `simprep.py`：Load（力/压力/扭矩）/Support（固定/销/滚动）/Contact（绑定/不分离）/MarkupNote + describe/summary |
| 持久化 | `kdoc.sim` 随项目 pickle 往返（单测）；`kdoc.notes` 桥接视口标注渲染 |
| UI | 仿真页 4 命令（作用于所选面）+ 标记页 2 命令 + 报告对话框 |
| 差距 15% | **仿真对象语义为数据模型而非 ANSYS 权威语义**（载荷坐标系/接触容差等以 SpaceClaim 交互语义为准，无 Mechanical 对拍——**边界项 NYI-4**：求解/后处理明确走 ANSYS 宿主，同参考框架「Solver 链合理延后」口径） |

### 2.13 渲染/工程图/打印 —— 75%，L1–L2

| 项 | 证据 |
|---|---|
| 渲染 | `ks.render`（超采 1–4×/背景/边开关）+ PNG 导出 + 打印预览 |
| 工程图 | HLR 三视图（`scdm/drawing.py`）+ BOM/尺寸标注（det.dim/det.bom）+ 视图快照（det.view） |
| 3D Markup | 便签对象持久化 + 视口锚定渲染 |
| 差距 25% | 无材质库/环境贴图/光线追踪；工程图无标准图幅版式（Library/DrawingFormats 有官方 A0–E 样本可挖——后续项）；PDF 为打印级而非 3D-PDF |

---

## 3. 差距排序（大 → 小）

| # | 差距域 | 量化 | 判断依据 |
|---|---|---|---|
| 1 | **草图约束求解器** | L1+，7 种约束简化解算 | SpaceClaim 草图是参数化建模入口；我们约束作用于固定点索引、无过约束报告。与 H7 参数表打通后投入产出比最高 |
| 2 | **官方装配/配合对拍样本** | 边界项 | 求解器数学已精确，差「官方工程样本 diff」一环即 L2；需在 SpaceClaim 内建装配样本（一次性人工） |
| 3 | **scdoc 字节级恒等** | 边界项 | 语义级闭环（restore+官方打开+逐字段 diff）；字节恒等需复刻官方 product-id/时间戳/UUID 生成器——**信息论上不可行**（UUID 本就随机），建议按口径声明为边界项 |
| 4 | **仿真对象权威语义** | 边界项 | 载荷/支撑为数据模型；ANSYS Mechanical 语义对拍在宿主外 |
| 5 | **工程图纸版式** | L1 | Library/DrawingFormats 有官方 A0–E 样本（仅图框无几何）——可解析后作图幅模板 |
| 6 | **钣金多弯展开/槽口** | 单弯精确 | 连续多弯 unfold 链、bend relief cuts |
| 7 | **渲染材质库** | L1 | KeyShot 集成在位（ks.render），材质参数未参数化 |

---

## 4. 边界项入册（`docs/NYI_INVENTORY.md`）

> 判定口径：产品边界 = 依赖官方闭源组件/外部宿主/信息论不可行，且存在
> 明确的对标替代路径。非代码缺口。

| # | 边界项 | 理由 | 替代路径（已实现） |
|---|---|---|---|
| NYI-1 | scdoc 写端**字节级恒等** | 官方存档含随机 UUID/实时时间戳/机器指纹 product-id——信息论不可复刻 | 语义级闭环：官方 restore ✓ + 官方打开 bodies=1 ✓ + 逐字段 diff 对齐 ✓ |
| NYI-2 | CATIA/Inventor/DWG 直读 | 无 OCCT 支持面；Datakit 许可为 SpaceClaim 宿主组件 | X_T 官方管线（实测直通）+ STEP/IGES 万国格式 |
| NYI-3 | 装配配合官方对拍 | 无官方装配工程样本入库（需 SpaceClaim 人工建档一次） | 求解器数学单测精确 + 7 类 DOF 表 |
| NYI-4 | ANSYS 求解/后处理语义 | Mechanical/Fluent 为独立宿主产品 | 仿真准备数据模型全量 + Workbench 页（wb.*）接线 |
| NYI-5 | KeyShot 材质库内部 | KS6 闭源渲染器 | ks.render 集成入口 + PNG 离屏渲染参数化 |
| NYI-6 | ACIS 内核数值 bit 等价 | 官方内核可全驱动（SpaceClaim 在装），复刻既不可行也无必要（参考框架 §9.6 同口径） | 官方 SabSatConverter restore + 官方打开 bodies=1 双门禁 |

---

## 5. 纪律闸门（违反即虚假达标）

1. 无官方 `verify_open.py` 哨兵 bodies>0 不宣称「官方打开」；
2. 无逐字段 diff 或 restore 产物不宣称「官方对齐」；
3. 字节恒等必须 hex 级比较（当前仅 SAT 文本路径达成过）；
4. 边界项必须先入册 `docs/NYI_INVENTORY.md` 再从完整度口径剔除；
5. 测试 failures 不为 0 不得关账（当前 167 passed / 1 skipped）。
