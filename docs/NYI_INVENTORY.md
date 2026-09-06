# NYI_INVENTORY — 边界项与未实现项入册

> 判定口径：**产品边界** = 依赖官方闭源组件/外部宿主/信息论不可行，且存在
> 明确的对标替代路径（非代码缺口）。**暂缓** = 有代码路径可走，按投入产
> 出排序待排期。参照 `function_gap_analysis.md` §4。
>
> 维护纪律：新边界项必须带「理由 + 替代路径（已实现）」两列；GUI 中的
> 对应入口保持可见或灰显 + 理由（不静默删除命令）。

---

## A. 产品边界项（永久豁免，双口径不计分）

| # | 项 | 类别 | 理由 | 替代路径（已实现） |
|---|---|---|---|---|
| NYI-1 | scdoc 写端**字节级恒等** | 信息论不可行 | 官方存档内嵌随机 UUID、实时时间戳、机器指纹 product-id——逐字节复刻不可能也不必要 | 语义级闭环：官方 SabSatConverter restore ✓ + 官方 SpaceClaim 打开 bodies=1 ✓ + 逐字段 diff 对齐 ✓（五族几何） |
| NYI-2 | CATIA / Inventor / DWG·DXF 直读 | 宿主组件许可 | OCCT 无支持面；Datakit 转换链为 SpaceClaim 宿主内置许可组件 | **X_T 官方管线**（`references/spaceclaim_import.py`，实测直通）+ STEP/IGES 万国格式 + OBJ/3MF |
| NYI-3 | ACIS 内核数值 bit 等价 | 官方可全驱动 | SpaceClaim 本体在装即官方内核；内核复刻既不可行也无必要（参考框架 §9.6 同口径） | 官方 SabSatConverter restore 门禁 + 官方打开哨兵双检 |
| NYI-4 | ANSYS Mechanical/Fluent 求解与后处理语义 | 独立宿主产品 | 求解器/后处理器为 ANSYS 独立安装组件，非 scdoc 格式范畴 | 仿真准备数据模型全量（载荷/支撑/接触/标记）+ Workbench 页（wb.*）+ 脚本导出 |
| NYI-5 | KeyShot 材质库与渲染内核 | 闭源第三方渲染器 | KS6 集成为官方插件路径，材质库二进制闭源 | `ks.render` 集成入口（超采/背景/边参数化）+ PNG 离屏渲染 |
| NYI-6 | PMI（GD&T）标注读取 | 宿主转换组件 | PMI 走 `SpaceClaimAcisPmiTranslator.exe` 宿主组件 | 几何与 B-rep 全量读写不受影响；PMI 可经官方管线转换后按需扩展 |

## B. 暂缓项（有代码路径，待排期）

| # | 项 | 现状 | 解锁路径 | 预估 |
|---|---|---|---|---|
| TODO-1 | 官方装配工程对拍样本 | 装配配合 L1+（求解器数学单测精确），缺官方装配 .scdoc 做 diff | SpaceClaim 内手工建装配（两体 + 配合）存档入库 → 逐字段对拍 | 0.5 天（一次性人工） |
| TODO-2 | 多折弯连续展开 | `unfold` 当前单弯精确 | `detect_bends` 多弯序列化 + 逐弯反向回展 | 2–3 天 |
| TODO-3 | 折弯槽口（bend relief cuts） | jog 平角三盒（已标注） | 弯折线端部槽口布尔（复用 corner_relief 机制） | 1–2 天 |
| TODO-4 | 曲面圆角面 / 曲线网络 | blend_loft 已覆盖双线框过渡 | `BRepFill_Filling` 多约束 + face-face blend（ChFi3d） | 3–5 天 |
| TODO-5 | 工程图图幅版式 | HLR 三视图 + BOM/尺寸已有；无标准图幅 | 解析 Library/DrawingFormats A0–E 官方图框 → 模板 | 3–5 天 |
| TODO-6 | 命名选择组（NamedSelection）写回 | **已闭环（P1-1）**：官方格式（BeamProfiles/Circular.scdoc 10 样本）——读端 parse_document 还原 name/selections/sectionPlane；写端 `_inject_named_selections` 注入 StoredSelectionTableDef（buckets+name+plane+PullToolProxyDef 官方结构）；`<selections/>` 空成员（moniker GUID 链路未建，读回名字对称已锁测试） | 成员绑定=moniker GUID 子项延后 | ✅ |
| TODO-7 | 保存视图读回 | **边界定档（P1-1 复核）**：SavedViewsDef 在写端代码与全机官方库（scdm 安装树）均为零命中——「写端已生成」系过时记录；无官方样本则不可凭想象写格式（纪律闸门）。解锁路径=SpaceClaim RunScript（建视图→存→diff document.xml，make_official_ref 基建在位） | 解锁后 1 天 | ⏸ 边界 |
| TODO-8 | 草图约束完整求解器 | **已关闭**：sketch_solver.py LM 求解器（DOF/冲突/表达式） | — | ✅ |
| TODO-9 | 整装配官方打开 | **已关闭**：官方 SpaceClaim 2019 R3 哨兵实测 `done bodies=2`（box+cyl 装配，根 0 体 + 两组件各 1 体） | 差分定位链（tests/test_todo9_assembly.py 固化）：①sectionId 是读者固定节键（未知 GUID → 整文档落空）；②sctype moniker 字符串逐字精确（多一个反斜杠 → 组件源解析失败 GetBodies 空引用）；③versions.xml/windows.xml 必须载文档 GUID；④SAB body/face/edge token#1 为文档级实体序号；⑤柱面 part 3 边（两圆+seam）文档与 SAB 计数一致；⑥ComponentDef 编号专用区间，避让面/边 id（官方首组件 0:27 与我们的面 id 0:27 撞号→组件静默丢失）。renderlist 挂体/checksums/facets 经证与开档无关 | ✅ |

## C. GUI 占位（2 项，均非功能缺口）

| # | 命令 | 状态 | 说明 |
|---|---|---|---|
| 1 | `safety.tab` | 设计空壳 | 安全页整体为占位架构（DEV_PLAN §17 载明） |
| 2 | `prep.small` | 待接 | 小面修复已由 `repair.check` 全项检查覆盖（含小面检出+自动修复），此入口待重定向到统一检查向导 |
