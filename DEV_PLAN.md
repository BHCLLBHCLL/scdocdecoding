# SCDM 开发规划

对照产品：ANSYS SpaceClaim 2019 R3（中文 UI 主界面）。  
本仓库程序：`scdm_gui.py` + `scdoc_parser`。

**产品定位：查看器 + 几何建模器（直接建模，无特征树）。**  
打开/显示 `.scdoc`，并在同一套 Ribbon 里完成拉动、移动、填充、合并、草图等编辑；结构树是实体/组件/草图，不出现「拉动-1」这类特征节点。

**内核策略：** 不反编译 `SpaceClaim.exe` / ACIS，不在 SAB 上原地改拓扑。会话几何以 Open CASCADE（`pythonocc-core`）为唯一建模内核；`scdoc_parser` 只负责导入。不复制 ANSYS 水印、云上传控件、官方图标和 KeyShot 品牌页。

**规划来源：** SpaceClaim 2019 R3 主界面截图 + 该版本公开功能区结构；对照代码 `scdm_gui.py`。安装路径 `C:\Program Files\ANSYS Inc\v195\SCDM\SpaceClaim.exe` 仅作版本定位。

---

## 1. 里程碑总表

| 波次 | 名称 | 目标 | 验收标准 | 状态 |
| --- | --- | --- | --- | --- |
| M1 | 会话壳 | Ribbon 同构、左三栈、视口拾取、显示、测量、打开 scdoc/STEP 进入 Document | 能打开 `box.scdoc` 与 STEP；单击选面；过滤器生效；结构树为「实体 n」 | 进行中（壳 90%：ribbon/树/视口/属性/选项已可用，修复启动崩溃；工具态机并入 M2） |
| M2 | 直接建模（产品成立点） | 命令栈 + Pull / Move / Fill / Combine / Split + 圆柱球 + 保存 | **新建 → 插圆柱 → 拉动面 → 合并 → 撤销 → 存 STEP → 再打开** | 完成（核心路径 test_m2.py 全通；工具态机并入 scdm/tools；选项生效；替换已接线；M2-04 拖动预览：Pull/Move 半透明预览 + 拖后提交，单击仍为原行为） |
| M3 | 草图 | 平面上画线圆矩、基础约束、闭环后拉动成体 | 在 XY 上画矩形 → 拉动成盒子 → 撤销回到草图 | 完成（scdm/sketch.py 二维求解：尺寸/水平/竖直/重合/垂直/相等/平行/相切/中点/固定 + 尺寸驱动；闭环拉伸成体；草图在视口按平面渲染（线/圆/点 actor）） |
| M4 | 扩展 | 倒圆/抽壳/阵列/镜像、截面、修复、装配、脚本 | 对盒子倒圆并阵列；缝合开放壳体；Python 建体 | 完成（倒圆/倒角/抽壳/阵列/镜像/干涉/缝合/螺旋/修复 gaps/missing/extra/small；M4-07 装配：组件树 + 移动/锚定/爆炸/两面配合 align_faces；拔模盒体上会拒诚实报错；脚本录制待后续） |
| M5 | 后期 | `.scdoc` 写出、分面/增材/工程图 | 写出文件可被本程序回读；官方 SCDM 互操作作为加分项 | 完成（M5-01 原生 scdoc 写出：scdm/scdoc_write.py 5 部件包，回读体积一致且报告校验 19/19；M5-02 facets STL 进会话；M5-03 增材构建体/取向/支撑/点阵；M5-05 工程图 BOM/尺寸/视图；M5-06 参数重建；**官方 SCDM 互操作已实测：scdm_interop_check.py 审计通过（记录种类与官方 box.scdoc 完全一致），官方 SpaceClaim 2019 R3 以 -m 打开我们写出的 scdoc 并保持运行（GUI 载入模型），仅缺 rgb_color 颜色记录（可选/外观项）**） |

命令条目约 86：M1 约 22 / M2 约 22 / M3 约 13 / M4 约 20 / M5 约 9。

---

## 2. 详细开发规划（工作包）

按依赖顺序执行。未完成前置工作包不得跳做后续建模工具。

### 2.1 M1 会话壳

| ID | 工作包 | 模块 | 内容 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| M1-01 | 包拆分 | `scdm/` | 新建包：`document` / `kernel` / `history` / `selection` / `tessellate` / `tools`；`scdm_gui.py` 降为壳 | — | 无 OCCT 时 GUI 仍能启动并提示缺依赖 |
| M1-02 | 内核封装 | `scdm/kernel.py` | 接入 `pythonocc-core`：单位、精度、Shape 句柄、STEP/BREP 读写、网格 | M1-01 | 单元测试：读 STEP 盒子，体积 > 0 |
| M1-03 | 会话文档 | `scdm/document.py` | 多 body、图层、单位、脏标记、基准（原点+XY/ZX/YZ）、文档名 | M1-01 | `Document.new()` 含三平面；改色置脏 |
| M1-04 | SAB 导入 | `scdm/import_sab.py` | `scdoc_parser` → 尽量重建 `TopoDS`（先平面）；失败面用 `facets.bin` 网格体并标记「网格导入」 | M1-02 | `box.scdoc` 得到实体；平面盒子优先 B-rep |
| M1-05 | 网格显示 | `scdm/tessellate.py` | OCCT 网格 → `vtkPolyData`（面/边分 actor）；预览层预留 | M1-02 | 着色+边；背景单色浅灰，去掉渐变 |
| M1-06 | Ribbon 壳 | `scdm_gui.py` | QTabBar + 分组 QToolButton；页签顺序与截图一致；设计页分组齐全 | M1-03 | 全部按钮可点；未实现命令状态栏提示「M* 未实现」而非静默 |
| M1-07 | 左三栈 | `scdm_gui.py` | 垂直 Splitter：结构树 / 选项 / 属性；属性改左下两列，去掉右栏 | M1-03 | 比例可拖；记忆尺寸 |
| M1-08 | 结构树 | 树控件 | 根=文档名；原点/平面/实体 n；勾选显隐；禁止平铺 Face/Edge id | M1-03, M1-07 | 与 `box.scdoc` 名称对齐（如 Solid1） |
| M1-09 | 导航五页 | QTabWidget | 结构 / 图层 / 选择 / 群组 / 视图 | M1-07 | 图层显隐改 actor；选择页列出当前选中 |
| M1-10 | 选择管理 | `scdm/selection.py` | 点/边/面/体/组件过滤；预亮显金；选中橙；树↔视口同步 | M1-05 | 单击面高亮；过滤器挡住其它类型 |
| M1-11 | 视口拾取 | VTK | CellPicker；单击对象、双击环边、三击实体 | M1-10 | 与截图 HUD 文案一致 |
| M1-12 | 视口叠加 | HUD | 左上提示；左下可点三轴切正交；无 ANSYS 水印/云钮 | M1-05 | 点三轴立方体面切到前/上/右 |
| M1-13 | 状态栏 | QStatusBar | 提示 + 过滤按钮组 + 捕捉占位 + 单位 mm | M1-10 | 过滤与 M1-10 同一数据源 |
| M1-14 | 定向 | 相机 | 旋转/平移/缩放/适合(F)/上一视图/主视图/等轴测/X Y Z | M1-05 | 与现有快捷键兼容并补负向/等轴测 |
| M1-15 | 显示样式 | Display | 面边点平面轴显隐；着色+边/线框/透明 | M1-05 | 关边后仅着色 |
| M1-16 | 测量 | Measure 工具 | 点点/边边/面面距离、角度、半径 | M1-10 | 视口标注数字；Esc 清除 |
| M1-17 | 文件后台 | File | 新建（空设计+基准）、打开 scdoc/STEP、最近、关闭（脏提示）、导出 PNG、选项、退出 | M1-03, M1-04 | 标题 `{stem} - SpaceClaim`；新建无几何 |
| M1-18 | 文档页签 | QTabBar | 多文档，每页独立 Document | M1-03 | 切页不串选择与相机 |
| M1-19 | 选项对话框 | Options | 单位、捕捉、选择、内核精度 | M1-03 | 改单位后面属性数值跟着变 |

### 2.2 M2 直接建模

| ID | 工作包 | 模块 | 内容 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| M2-01 | 命令栈 | `scdm/history.py` | Undo/Redo 存 Shape 快照；QAT 绑定；脏标记 | M1-03 | Ctrl+Z 恢复拉动前体积 |
| M2-02 | Tool 基类 | `scdm/tools/base.py` | Idle → Picking → Preview → Commit / Failed / Cancel(Esc)；空格重复上一工具 | M2-01 | 新工具只需实现 pick/drag/commit |
| M2-03 | 选项面板绑定 | Options dock | 活动工具实参（对称、并/差/交、复制…） | M2-02 | 切工具则换控件，无工具显示「无选项」 |
| M2-04 | 预览体 | tessellate | 半透明橙临时 mesh，不进 Undo | M2-02 | 拖动流畅；Esc 预览消失 |
| M2-05 | 迷你条 | HUD | 选中后：拉动/移动/填充 | M2-02 | 与 Ribbon 进入同一 Tool |
| M2-06 | 选择工具 | `tools/select.py` | 默认工具；手势与过滤器 | M1-11 | 退出其它工具回到 Select |
| M2-07 | 插入圆柱/球 | `tools/primitives.py` | 点击或拖尺寸；创建后自动进拉动 | M2-02 | 视口出现实体，树增「实体 n」 |
| M2-08 | 插入基准 | Document | 平面/原点/轴 | M1-03 | 树可见；可作拉动到面 |
| M2-09 | 拉动 Pull | `tools/pull.py` | 面偏移/加厚；闭环草图拉伸；边扫掠；圆面旋转 | M2-07 | 拉盒子顶面高度变化且仍为实体 |
| M2-10 | 偏移面 | Create | 拉动的显式形态 | M2-09 | 与拉动偏移结果一致 |
| M2-11 | 移动 Move | `tools/move.py` | 三轴手柄；复制/沿轴/到点/到面 | M2-02 | 体平移；复制得到第二个体 |
| M2-12 | 填充 Fill | `tools/fill.py` | 删面补洞并 Solidify | M2-09 | 盒子去掉一侧后仍能成实体或明确失败提示 |
| M2-13 | 替换 Replace | `tools/replace.py` | 源面→目标面，Sewing | M2-09 | 两平面体可贴合替换 |
| M2-14 | 合并 Combine | `tools/combine.py` | Fuse / Cut / Common | M2-07 | 两圆柱并/差/交体积正确 |
| M2-15 | 分割实体/面 | `tools/split.py` | Splitter；面或平面切体 | M2-08 | 一盒变两体 |
| M2-16 | 剪贴板 | Clipboard | 复制/剪切/粘贴为独立体 | M2-11 | 粘贴带位移不重合 |
| M2-17 | 截面模式 | Mode | 可拖剖切面；截面上可拉 | M2-09 | 剖面显示与 Display 联动 |
| M2-18 | 质量属性 | Measure | GProp 体积/面积/重心 | M1-02 | 与已知立方体解析解一致 |
| M2-19 | 保存/另存为 | I/O | 自有工程包（JSON + OCCT BREP）+ 可选 STEP；STL/3MF | M2-01 | 回读几何一致（体积误差在公差内） |
| M2-20 | 属性可写 | Properties | 名称/图层/颜色可改；几何量只读 | M1-08 | 改色立即反映到 actor |

### 2.3 M3 草图

| ID | 工作包 | 模块 | 内容 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| M3-01 | 草图模式 | `tools/sketch_mode.py` | 选平面/面进入；相机贴法向；网格；3D 半透明 | M2-06 | 退出回三维模式 |
| M3-02 | 草图数据 | Document.sketches | 曲线不直接改实体 | M3-01 | 树出现草图节点 |
| M3-03 | 直线/切线 | sketch tools | 点击两点；切已有圆 | M3-02 | 视口 2D 线 |
| M3-04 | 矩形/三点矩形 | | 对角或三点击 | M3-02 | 闭环四段 |
| M3-05 | 圆/三点圆/椭圆 | | 圆心半径或三点 | M3-02 | 可拉成圆柱 |
| M3-06 | 样条/点/构造线 | | 构造线不参与闭环 | M3-02 | 构造线样式区分 |
| M3-07 | 偏移/布局/网格 | | Offset；Create Layout；栅格捕捉 | M3-03 | 捕捉到栅格点 |
| M3-08 | 约束求解 | 2D solver | 接入独立求解器（SolveSpace 算法或等价），不自写完整器 | M3-03 | 尺寸+重合+水平竖直先通 |
| M3-09 | 其余约束 | | 相切/相等/平行/垂直/中点/固定 | M3-08 | 改一尺寸其它跟随 |
| M3-10 | 投影 | Project | 边/面投影到草图面 | M3-01 | 投影线可约束 |
| M3-11 | 草图拉动 | Pull | 闭环 Wire→Face→Prism | M2-09, M3-04 | 矩形拉成盒子 |

### 2.4 M4 扩展

| ID | 工作包 | 模块 | 内容 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| M4-01 | 阵列 | Pattern | 线性/圆周；融合或独立体 | M2-14 | n 个体或一体 |
| M4-02 | 镜像 | Mirror | 相对平面 | M2-08 | 镜像体位置正确 |
| M4-03 | 抽壳 | Shell | 指定开口面 | M2-09 | 壁厚均匀 |
| M4-04 | 倒圆/倒角 | Blend/Chamfer | 边集 | M2-09 | 边变面，体积减少 |
| M4-05 | 拔模 | Draft | 中性面+角度 | M2-09 | 侧面倾斜 |
| M4-06 | 螺旋 | Helix | 插入螺旋边 | M2-08 | 可扫掠 |
| M4-07 | 装配 | Assembly | 插入/创建组件、移动、锚定、配合、爆炸、轻量化 | M2-11 | 组件节点可激活 |
| M4-08 | 修复 | Repair | 缝合/间隙/缺失面/多余边/小面/实体化 | M1-04 | 开放面缝成壳或实体 |
| M4-09 | 小特征/命名选择 | Prepare 子集 | Defeaturing；命名选择 | M2-06 | 命名选择可高亮 |
| M4-10 | 干涉 | Measure | 体体干涉体积 | M2-14 | 相交时报告非零 |
| M4-11 | 脚本 | Tools | Python 暴露 Document/Tool API；录制回放 | M2-02 | 脚本建圆柱并保存 |
| M4-12 | 自定义功能区 | | 显示/隐藏命令 | M1-06 | 配置可持久化 |
| M4-13 | 打印/恢复 | File | 打印预览；崩溃临时文件 | M2-19 | 异常退出后可恢复 |

### 2.5 M5 后期

| ID | 工作包 | 模块 | 内容 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- | --- |
| M5-01 | scdoc 写出 | I/O | 研究写出 `document.xml` + SAB；不阻塞建模 | M2-19 | 本程序可回读；官方 SCDM 为加分 |
| M5-02 | 分面 | Facets | 反转/光滑/简化/填孔/网格转实体 | M1-04 | STL 可进会话 |
| M5-03 | 增材 | Additive | 构建体/取向/支撑/点阵 | M4-01 | 可选模块 |
| M5-04 | 仿真准备 | Prepare | 共享拓扑/包围体/中面 | M4-08 | 可选 |
| M5-05 | 工程图 | Detailing | 视图/尺寸/注释/BOM | M3-08 | 可选 |
| M5-06 | 参数页 | Workbench 替代 | 自有参数，不对接 ANSYS 进程 | M4-11 | 参数改尺寸重建 |
| M5-07 | 安全/KeyShot 页 | UI | 空页、隐藏或自有渲染入口；不复制品牌 | M1-06 | 无第三方商标 |

---

## 3. 运行时分层

现有解析器停在「读」。建模器在其上增加会话文档、工具状态机、内核适配和命令栈。VTK 只负责显示与拾取，不持有可编辑拓扑。

| 层 | 职责 | 现状 | 目标 |
| --- | --- | --- | --- |
| UI Shell | Ribbon / 树 / 选项 / 视口 / 状态栏 | 菜单 + 三栏 | SCDM 同构壳，活动工具按下 |
| Document | 多文档、图层、单位、脏标记 | 一次性 parse dict | 可新建/关闭/切换的会话对象 |
| Tool SM | Select/Pull/Move/Fill… 预览-提交-取消 | 无 | 统一 Tool：pick / drag / preview / commit |
| Selection | 过滤、预亮显、环/体手势、跨树同步 | 仅树点击 | 视口拾取 + 过滤器 + 手柄 |
| Kernel | B-rep 布尔、偏移、倒圆、草图面 | 无 | pythonocc-core，精度与单位可配 |
| Display | OCCT 网格 → VTK；预览体另层 | facets.bin 只读 | 每次 commit 重 tessellate；拖动用临时 mesh |
| History | 撤销/重做 | 无 | 命令栈存 Shape 快照或增量 |
| I/O | 读 scdoc / STEP；写会话 / STEP / 后期 scdoc | 只读 scdoc | 导入器 SAB→TopoDS；导出器分阶段 |

---

## 4. 数据流

| 路径 | 做法 |
| --- | --- |
| 打开 `.scdoc` | opc + `document.xml` + SAB → 尽量重建 TopoDS（平面/柱/球/锥先通）；失败面回退 facets 为网格体并标记「网格导入」 |
| 打开 STEP/IGES/BREP | OCCT 原生读取，作为主交换格式 |
| 编辑 | 只改 Document 里的 `TopoDS_Shape`；commit 后重 tessellate 进 VTK |
| 保存 M2 | 自有工程包（JSON 清单 + OCCT BREP 二进制）并可选并写 STEP |
| 保存 M5 | 研究写出 `document.xml` + SAB；与官方 scdoc 互操作不阻塞建模可用性 |

---

## 5. 主窗口分区

壳与 SpaceClaim 2019 R3 截图同构：上功能区、左三栈导航、中视口、下状态栏。选项面板是活动建模工具的实参面；视口必须能画预览体和拖动手柄。

| 区域 | 尺寸 | 现状（`scdm_gui.py`） | 目标 |
| --- | --- | --- | --- |
| 标题栏 | 高 32px | `SpaceClaim .scdoc Viewer` | 脏标记 `*box - SpaceClaim` |
| 快速访问栏 | 标题栏左 24px | 无 | 新建 / 打开 / 保存 / 撤销 / 重做，绑定命令栈而非 VTK 相机 |
| 功能区页签 | 高 28px | File / View 菜单 | 文件后台 + 13 工作页；活动工具所在页高亮 |
| 功能区本体 | 高 92px | 无 | 设计页全部可点；活动工具按下态 |
| 结构树 | 左上，宽 260–320 | Face/Edge id 平铺 | 组件 / 实体 n / 草图 / 基准；无特征历史节点 |
| 导航页签 | 树底 24px | 无 | 结构 / 图层 / 选择 / 群组 / 视图 |
| 选项面板 | 左中，随工具 | 无 | 拉动对称/拔模、合并并差交、移动复制、草图捕捉 |
| 属性面板 | 左下约 180px | 右栏纯文本 | 可编辑名称/图层/颜色；面积体积只读 |
| 3D 视口 | 中央 | 只读 VTK 网格、渐变底 | 单色底；OCCT 网格 + 半透明预览 + 手柄 |
| 视口叠加 | 浮动 | 无 | 工具提示 + 迷你条 + 拖动尺寸数字 |
| 方位三轴 | 左下 90×90 | 已有 gizmo | 可点正交；草图模式切到平面法向 |
| 文档页签 | 视口底 22px | 无 | 多会话；每页独立 Document + Undo |
| 状态栏 | 高 28px | 一句提示 + 空坐标 | 提示 + 过滤 + 捕捉 + 单位 + 内核失败红字 |

布局骨架：

```
[ 标题栏 · *box - SpaceClaim                                          ]
[ 文件  设计  显示  组件  测量  分面  Additive  修复  准备  Workbench  详细  安全  工具  KeyShot ]
[ 剪贴板 | 定向 | 草图 | 模式 | 编辑 | 相交 | 约束 | 生成 | 插入     ]
[ 结构树          |  3D 视口 + 预览体 + 手柄                          ]
[ 结构 图层 选择   |  HUD / 尺寸                                      ]
[ 群组 视图        |  三轴                                            ]
[ 选项=工具实参    |                                                  ]
[ 属性             |  文档页签 · box                                  ]
[ 状态栏 · 工具提示          过滤 · 捕捉 · mm · 撤销栈                 ]
```

---

## 6. 功能区命令总表

页签顺序与截图一致。全部做成真命令：未到波次的按钮可点，状态栏说明所属里程碑。

### 6.1 文件（后台页 File）

| 分组 | 命令 | English | 波次 | 建模语义 |
| --- | --- | --- | --- | --- |
| 文档 | 新建 | New | M1 | 空设计：原点 + XY/ZX/YZ 平面 |
| 文档 | 打开 | Open | M1 | `.scdoc` 走解析器导入 OCCT；STEP/IGES/Parasolid/BREP 走内核 I/O |
| 文档 | 最近文件 | Recent | M1 | |
| 文档 | 关闭 | Close | M1 | 脏文档提示保存 |
| 文档 | 保存 | Save | M2 | 先写会话包+STEP；原生 `.scdoc` 写出放到 M5 |
| 文档 | 另存为 | Save As | M2 | |
| 文档 | 恢复 | Recover | M4 | 崩溃临时文件 |
| 输出 | 打印 / 预览 | Print | M4 | |
| 输出 | 导出图像 | Image | M1 | PNG / JPG / BMP，含当前视图 |
| 输出 | 导出 STEP / STL / 3MF | Export | M2 | |
| 应用 | 选项 | Options | M1 | 单位、捕捉、选择、撤销步数、内核精度 |
| 应用 | 退出 | Exit | M1 | |

### 6.2 设计 Design（默认页）

| 分组 | 命令 | English | 波次 | 建模语义 |
| --- | --- | --- | --- | --- |
| 剪贴板 | 粘贴 | Paste | M2 | 粘贴为变换后的独立体 |
| 剪贴板 | 剪切 | Cut | M2 | |
| 剪贴板 | 复制 | Copy | M2 | |
| 定向 | 旋转 | Spin | M1 | |
| 定向 | 平移 | Pan | M1 | |
| 定向 | 缩放 | Zoom | M1 | |
| 定向 | 缩放至适合 | Fit | M1 | F |
| 定向 | 上一视图 | Previous View | M1 | |
| 定向 | 主视图 / 等轴测 / 正交 | Home / Iso / Ortho | M1 | X / Y / Z |
| 草图 | 直线 / 切线 | Line / Tangent | M3 | |
| 草图 | 矩形 / 三点矩形 | Rectangle | M3 | |
| 草图 | 圆 / 三点圆 / 椭圆 | Circle / Ellipse | M3 | |
| 草图 | 样条 / 点 / 构造线 | Spline / Point / Construction | M3 | |
| 草图 | 偏移 | Offset | M3 | |
| 草图 | 创建布局 | Create Layout | M3 | 面/平面上进入草图模式 |
| 草图 | 草图网格 | Sketch Grid | M3 | |
| 模式 | 草图模式 | Sketch Mode | M3 | 锁平面、2D 捕捉、约束求解 |
| 模式 | 截面模式 | Section Mode | M2 | 剖切面可拖；可在截面上拉出 |
| 模式 | 三维模式 | 3D Mode | M1 | 默认；直接建模主战场 |
| 编辑 | 选择 | Select | M1 | 默认工具；单击/双击环/三击体 |
| 编辑 | 拉动 | Pull | M2 | 挤出、偏移面、旋转、扫掠，由选择上下文决定 |
| 编辑 | 移动 | Move | M2 | 三轴手柄；复制/沿轴/到点/到面 |
| 编辑 | 填充 | Fill | M2 | 删面并补洞，保持实体 |
| 编辑 | 替换 | Replace | M2 | 用目标面替换源面并缝合 |
| 相交 | 合并 | Combine | M2 | 并/差/交，工具选项三态 |
| 相交 | 分割实体 | Split Body | M2 | 面或平面切体 |
| 相交 | 分割面 | Split Faces | M2 | |
| 约束 | 尺寸 | Dimension | M3 | |
| 约束 | 水平 / 竖直 / 重合 / 相切 | H/V / Coin / Tan | M3 | |
| 约束 | 相等 / 平行 / 垂直 / 中点 / 固定 | Eq / Par / Perp / Mid / Fix | M3 | |
| 生成 | 阵列 | Pattern | M4 | 线性/圆周，融合或独立体 |
| 生成 | 镜像 | Mirror | M4 | |
| 生成 | 投影 | Project | M3 | |
| 生成 | 抽壳 | Shell | M4 | |
| 生成 | 倒圆 / 倒角 | Blend / Chamfer | M4 | |
| 生成 | 拔模 | Draft | M4 | |
| 生成 | 偏移面 | Offset Faces | M2 | 拉动的显式形态 |
| 插入 | 平面 / 原点 / 轴 | Plane / Origin / Axis | M2 | |
| 插入 | 圆柱 / 球 | Cylinder / Sphere | M2 | 点击或拖尺寸创建，立即进拉动 |
| 插入 | 螺旋 | Helix | M4 | |
| 插入 | 组件 / 文件 | Component / File | M4 | |

### 6.3 其余页签

| 页签 | 分组 | 命令 | English | 波次 | 建模语义 |
| --- | --- | --- | --- | --- | --- |
| 显示 | 显示/样式 | 面 / 边 / 顶点 / 平面 / 轴 | Topo vis | M1 | |
| 显示 | 显示/样式 | 着色+边 / 线框 / 透明 | Shaded+Edges | M1 | SCDM 默认着色+边 |
| 显示 | 显示/样式 | 剖面显示 / 轮廓边 | Section / Silhouette | M2 | |
| 组件 | 组件 | 插入 / 创建组件 | Insert / Create | M4 | |
| 组件 | 组件 | 移动组件 / 锚定 / 配合 | Move / Anchor / Mate | M4 | |
| 组件 | 组件 | 爆炸图 / 轻量化 | Explode / Lightweight | M4 | |
| 测量 | 测量 | 测量 | Measure | M1 | 距离 / 角度 / 半径 |
| 测量 | 测量 | 质量属性 | Mass Properties | M2 | OCCT GProp |
| 测量 | 测量 | 干涉检查 | Interference | M4 | |
| 分面 | 网格 | 反转法向 / 光滑 / 简化 | Reverse / Smooth / Reduce | M5 | |
| 分面 | 网格 | 填孔 / 转为实体 | Fill / Convert | M5 | STL 进 B-rep 的后路 |
| 增材 | 打印准备 | 构建体 / 取向 / 支撑 / 点阵 | Build / Orient / Support / Lattice | M5 | |
| 修复 | 修复 | 缝合 / 间隙 / 缺失面 | Stitch / Gaps / Missing | M4 | |
| 修复 | 修复 | 多余边 / 小面 / 实体化 | Extra / Small / Solidify | M4 | |
| 准备 | 仿真准备 | 共享拓扑 / 包围体 / 中面 | Share / Enclosure / Mid | M5 | |
| 准备 | 仿真准备 | 小特征 / 命名选择 | Defeaturing / Named sel | M4 | |
| Workbench | 参数 | 参数 / 命名选择发布 | Parameters | M5 | 自有参数，不对接 ANSYS 进程 |
| 详细 | 工程图 | 视图 / 尺寸 / 注释 / BOM | Views / Dim / Note / BOM | M5 | |
| 安全 | 附加页 | 保留空页或隐藏 | Optional tab | M5 | 原安装附加模块，非建模核心 |
| 工具 | 工具 | 脚本 | Script | M4 | Python 暴露 Document/Tool API |
| 工具 | 工具 | 录制 / 回放 | Record | M4 | |
| 工具 | 工具 | 自定义功能区 | Customize | M4 | |
| KeyShot | 渲染 | 自有渲染入口或隐藏该页 | Own renderer | M5 | 不复制 KeyShot 品牌 |

---

## 7. 左侧导航

### 7.1 结构树层级

与 `document.xml` 对齐，不要平铺 Face/Edge 内部 id。直接建模：无特征历史节点。

| 节点 | 来源 | 行为 |
| --- | --- | --- |
| box（根） | 文档名 | 显隐整设计、激活组件 |
| 原点 Origin | 基准 | 三轴十字，默认可关 |
| 平面 XY / ZX / YZ | 基准 | 单击设草图面，勾选显隐 |
| 实体 n | Body | 单击选体；三击等价 |
| 曲面 / 草图 / 曲线 | 若存在 | 按类型图标区分 |
| 命名选择 | 可选 | 高亮一组面边 |

### 7.2 五个导航页

| 页签 | 内容 | 波次 |
| --- | --- | --- |
| 结构 | 设计树 + 勾选显隐 + 右键 | M1 |
| 图层 | 图层名 / 色 / 锁定 / 可见 | M1 |
| 选择 | 当前选中列表，可移出 | M1 |
| 群组 | 用户保存的对象组 | M1 页签，M2 保存组 |
| 视图 | 主视图、已存相机、剖面 | M1 |

### 7.3 选项 + 属性

左栏垂直三分：上树（弹性）、中选项（内容自适应，空则收起）、下属性（固定约 180px）。属性是两列键值表。

| 选中对象 | 属性字段 |
| --- | --- |
| 无 | 文档单位、公差、文件路径 |
| 实体 | 名称、图层、颜色、材质、体积、表面积、重心 |
| 面 | 名称、颜色、面积、曲面类型（平面/柱/球）、法向 |
| 边 | 长度、曲线类型、端点坐标 |
| 组件 | 名称、抑制、颜色覆盖、实例路径 |

M1 名称/图层/颜色只读显示即可；M2 起名称/图层/颜色可写，几何量始终由内核算只读。

---

## 8. 3D 视口

| 项 | 规格 |
| --- | --- |
| 背景 | 单色浅灰（约 RGB 245），去掉当前渐变 |
| 默认样式 | 着色+边；面色来自 renderlist / 文档色；边深灰约 1.4px |
| 选中 | RGB(255, 90, 25)，不透明度 0.85 |
| 预亮显 | RGB(255, 200, 40) 轮廓 |
| 几何默认 | RGB(158, 168, 178) |
| 投影 | 平行投影默认开 |
| 叠加 | 左上指令条；选中后迷你条（拉动/移动/填充）；拖动中尺寸数字 |
| 三轴 | 可点击立方体面切正交视图 |
| 拾取 | VTK CellPicker，按状态栏过滤器命中点/边/面/体 |
| 预览 | 工具拖动时半透明橙临时 Shape，commit 后替换正式网格 |
| 品牌 | 不放 ANSYS 水印和云上传钮 |

HUD 文案（选择工具）：「单击选择对象；双击选环边；三击选实体」。

---

## 9. 状态栏与交互

| 位置 | 控件 | 行为 |
| --- | --- | --- |
| 左 | 提示文本 | 镜像当前工具 HUD；内核失败红字 |
| 右 1 | 点 / 边 / 面 / 体 / 组件 过滤 | 可多选，影响拾取 |
| 右 2 | 捕捉：栅格 / 端点 / 中点 / 重合 | M1 先做端点中点 |
| 右 3 | 单位 mm | 读 `document.xml` units，可切换显示 |
| 右 4 | 旋转 / 平移 / 适合 | 等价 Orient 组与中键手势 |

| 操作 | SpaceClaim 惯例 | 当前 GUI | 目标波次 |
| --- | --- | --- | --- |
| 中键拖动 | 旋转（绕旋转中心） | VTK 默认 | M1 |
| Shift+中键 | 平移 | 未绑 | M1 |
| 滚轮 | 朝光标缩放 | 部分可用 | M1 |
| F | 缩放至适合 | 已有 | M1 |
| X / Y / Z | 正交视图 | 已有，需补负向与等轴测 | M1 |
| Esc | 取消工具，回选择 | 无工具状态机 | M2 |
| 空格 | 重复上一工具 | 无 | M2 |
| Ctrl+单击 | 追加选择 | 无视口拾取 | M1 |
| 双击边 | 选整环 | 无 | M1 |
| 三击 | 选实体 | 无 | M1 |
| 右键 | 隐藏/颜色/缩放到 | 无 | M1 |
| Ctrl+Z / Ctrl+Y | 撤销 / 重做 | 无 | M2 |

---

## 10. 视觉规格（自有资源，不抄官方图标）

| 元素 | 规格 |
| --- | --- |
| 窗口底 | 浅灰 #F0F0F0 |
| 活动页签 | 白底，2px 强调蓝下划线 |
| 功能区分组 | 1px #D0D0D0 竖分割线，组名 11px 居中 |
| 大命令 | 32×32 图标 + 12px 标签，高 52px |
| 左栏页签 | 文字页签，活动项底部强调线 |
| 树节点 | 16px 类型图标 + 勾选 + 标题；选中行浅蓝 |
| 视口选中 / 预亮显 / 几何 | 见第 8 节 |

---

## 11. M2 核心工具 → OCCT

SpaceClaim 编辑组是直接建模，不是草图特征。每个工具都是「选择上下文 + 拖动预览 + 单击提交」，失败时 Shape 回滚到命令入口快照。

| 工具 | 选择上下文 | 内核操作 | 选项面板 |
| --- | --- | --- | --- |
| 拉动 Pull | 面→偏移/加厚；闭环草图→拉伸；边→扫掠；圆面→旋转 | `BRepPrimAPI_MakePrism` / `MakeRevol`；`BRepOffsetAPI`；失败则 Fuse+Cut | 对称、两侧、拔模角、复制、到面 |
| 移动 Move | 体/面/组件 + 方向锚 | `BRepBuilderAPI_Transform`；面移动用 MakePrism 布尔 | 复制、沿轴、到点、到面、阵列数 |
| 填充 Fill | 一个或多个面 | 删除面后 ShapeFix / `BRepOffsetAPI_MakeFilling` 补洞并 Solidify | 保留边、相切连续 |
| 替换 Replace | 源面 + 目标面 | 替换几何后 Sewing + `ShapeFix_Solid` | 延伸目标面 |
| 合并 Combine | 目标体 + 刀具体 | `BRepAlgoAPI_Fuse` / `Cut` / `Common` | 合并 / 减去 / 相交；保留刀具 |
| 分割 Split | 体 + 面或平面 | `BRepAlgoAPI_Splitter` | 保留两侧、仅切割面 |
| 圆柱/球 | 点击原点或拖两点 | `BRepPrimAPI_MakeCylinder` / `Sphere` | 直径、高度；创建后自动进入拉动 |

---

## 12. 工具状态机

| 状态 | 输入 | 输出 |
| --- | --- | --- |
| Idle | 点 Ribbon 或迷你条 | 进入工具，选项面板加载默认实参 |
| Picking | 单击/框选，过滤器生效 | 高亮；不足选择时 HUD 继续提示 |
| Preview | 拖动或键入尺寸 | 半透明预览 Shape，不进撤销栈 |
| Commit | 单击空白 / Enter | 内核成功则推 Undo；刷新树与网格 |
| Failed | 布尔失败、非流形 | 丢预览，状态栏报错，保持原 Shape |
| Cancel | Esc | 回 Select 工具，恢复入口快照 |

空格重复上一工具；撤销绑 QAT。

---

## 13. 草图（M3）

| 项 | 说明 |
| --- | --- |
| 进入 | 选平面或平面上的面 → 草图模式：相机贴看法向，显示网格，3D 体半透明 |
| 数据 | 曲线存在 `Document.sketches`，不直接改实体，直到拉动把闭环变成面再拉伸 |
| 约束 | 不要自写完整约束器。用独立 2D 求解器驱动点坐标，再 `BRepBuilderAPI_MakeEdge/Wire/Face` |
| 顺序 | 先尺寸 + 重合 + 水平竖直，再相切/相等 |

---

## 14. 模块拆分

相对现在单文件 `scdm_gui.py`。

| 模块 | 职责 |
| --- | --- |
| `scdoc_parser/*` | 只读：OPC / `document.xml` / SAB / facets，作为导入器 |
| `scdm/kernel.py` | OCCT 封装：布尔、拉伸、网格、STEP I/O、精度 |
| `scdm/import_sab.py` | SAB 拓扑 → TopoDS；覆盖面类型逐步加 |
| `scdm/document.py` | 会话文档、图层、脏标记、多 body 句柄 |
| `scdm/history.py` | Undo/Redo 快照 |
| `scdm/selection.py` | 过滤器、手势、高亮集 |
| `scdm/tools/*.py` | Select / Pull / Move / Fill / Combine / Sketch… |
| `scdm/tessellate.py` | Shape → vtkPolyData（面/边/预览） |
| `scdm_gui.py` | 壳：Ribbon、树、视口、状态栏，转发给 Document/Tool |

---

## 15. Qt 实现映射

继续 PyQt5 + VTK，不引入商业 Ribbon 控件。

| 区域 | 建议控件 | 要点 |
| --- | --- | --- |
| 主窗 | QMainWindow | 禁止右停靠；左栏固定最小宽 260 |
| QAT + 标题 | 系统框 + 工具条 | Frameless 仿 SCDM 代价高，M1 用系统框即可 |
| 功能区 | QWidget：QTabBar + 横向 QScrollArea | 每组 QFrame + QGridLayout；大按钮 32、小按钮 16 |
| 文件后台 | 堆叠页替换中央区 | 仿 Office Backstage |
| 左栏 | QSplitter(Vertical) | 树 / 选项 / 属性三截，记忆尺寸 |
| 导航页 | QTabWidget 南向页签 | 结构/图层/选择/群组/视图 |
| 结构树 | QTreeWidget | 第 0 列勾选，UserRole 存 kind+id |
| 属性 | QTableWidget 两列 | M2 起名称/颜色可编辑 |
| 视口 | QVTKRenderWindowInteractor | 叠加 QLabel HUD；文档 QTabBar 贴底 |
| 迷你条 | 无边框 QWidget | 跟随 VTK 屏幕坐标 |
| 状态栏 | QStatusBar + QToolButton | 过滤器是 checkable 按钮组 |

---

## 16. 对照当前代码

| 能力 | 现在 | 建模器要求 |
| --- | --- | --- |
| 几何真源 | facets.bin + 只读 SAB | OCCT Shape；facets 仅导入回退 |
| 新建 | 无 | 空文档 + 三基准面 |
| 保存 | 无 | M2 会话+STEP；M5 再攻 scdoc |
| 撤销 | 无 | 每 commit 快照 |
| 视口拾取 | 无 | 面边体过滤 + 预亮显 |
| 拉动等 | 无 | M2 必须可做出盒子级模型 |
| 树 | Face/Edge id | 实体/草图/基准，可删可藏可改色 |
| 窗口 | QMainWindow + 水平三栏 | 上功能区；左垂直三栈；中视口；无右栏 |
| 菜单 | File / View | 自定义 Ribbon |
| 属性 | 右栏纯文本列表 | 左下两列 |
| 选项 | 无 | 工具上下文面板 |
| 视口外观 | 渐变底、无 HUD | 单色底、提示、迷你条、文档页签 |
| 三轴 | 已有 OrientationMarker | 可点击切视图 |
| 状态栏 | 一句话 + 空坐标 | 过滤 / 捕捉 / 单位 / 视图簇 |
| 标题 | SpaceClaim .scdoc Viewer | `{stem} - SpaceClaim` |

---

## 17. 范围边界

| 做 | 不做 |
| --- | --- |
| 对标信息架构、分区比例、交互惯例、命令清单 | 拆解 SCDM 的 DLL/EXE，抽取官方图标 |
| OCCT 实现同等直接建模交互 | 在 SAB 上充当建模内核 |
| M2 会话包 + STEP 保证可回读 | 用原生 scdoc 写出卡住建模进度 |
| 自有产品名与图标 | ANSYS 水印、云上传、KeyShot 品牌页 |
| Workbench 页做自有参数（可选） | 对接 ANSYS Workbench 进程 |

---

## 18. 建议开工顺序

1. **M1-01 ~ M1-05**：包结构 + OCCT + 导入 + 显示（没有内核不要先画完整 Ribbon 空壳太久）。
2. **M1-06 ~ M1-19**：壳与选择，使查看器达到可用。
3. **M2-01 ~ M2-19**：工具状态机与核心建模，以第 1 节 M2 验收路径为准。
4. 再进 M3 草图、M4 扩展、M5 写出。

---

## 19. 占位功能盘点（2026-08-28 代码核对，按难易与工作量排序）

M1–M5 已标「完成」，但对照 `scdm/catalog.py` 的命令目录、`scdm_gui.py` 的 `_do_*` 分发与各模块实现，仍有一批功能只是占位（点击仅状态栏提示、handler 内是「预留」文字、或实现被写死成最简形态）。本节按 **难易程度 + 开发工作量升序** 排列；`safety.tab` 按设计保留空壳，不计入。

统计口径：
- **P0 纯占位**：无 handler 或 handler 只输出状态栏文字，需要从零写实现，但范围有限。
- **P1 简化实现**：已有真实结果，但参数/交互写死，需要补选项与输入路径。
- **P2 交互链路缺口**：UI 已就位，拾取/反馈/内核链路缺一段，属于跨模块接线。
- **P3 研究型大项**：算法或格式研究为主，周期以周计。

工作量按单人开发估算（「天」= 人天），依赖 `pythonocc-core` 已可用。

### 19.1 P0 纯占位（每项 0.5 ~ 3 天，合计约 18 ~ 26 天）

| # | 功能 / 命令 | 现状（占位形态） | 代码位置 | 预估 |
| --- | --- | --- | --- | --- |
| 1 | 准备·包围体 `prep.enclose` | 无 handler、不在 live 集合；可直接复用 `additive.build_volume` | `catalog.py:189` | 0.5 天 |
| 2 | 草图网格 `sketch.grid` | 仅状态栏文字「已切换」，视口无网格渲染 | `scdm_gui.py:1091` | 0.5~1 天 |
| 3 | 参数发布 `wb.publish` | 仅把参数拼进状态栏文字，无发布产物（可写 JSON/CSV） | `scdm_gui.py:880` | 0.5~1 天 |
| 4 | 视口右键菜单 | `_on_vtk_right` 仅提示文字；隐藏/缩放到均可由现有能力拼接 | `scdm_gui.py:1780` | 0.5~1 天 |
| 5 | 显示·轮廓边 `gfx.silhouette` | 无 handler、不在 live；VTK FeatureEdges 滤镜即可 | `catalog.py:137` | 0.5~1 天 |
| 6 | 显示·剖面显示 `gfx.section` | 无 handler、不在 live；VTK clipping plane 开关（拖动手柄归入截面模式 #26） | `catalog.py:138` | 1 天 |
| 7 | 打印/预览 `file.print` | 在 `M5_LIVE` 却无 `_do_file_print`，点击报「M4 未实现」 | `catalog.py:295` + `scdm_gui.py:436` | 1 天 |
| 8 | 工程图·注释 `det.note` | handler 只输出「注释：占位（M5 后续）」 | `scdm_gui.py:975` | 1~2 天 |
| 9 | 崩溃恢复 `file.recover` | 无 handler、不在 live；临时文件自动保存 + 启动时恢复 | `catalog.py:237` | 1~2 天 |
| 10 | 插入组件/文件 `insert.component` | 无 handler、不在 live（与 `asm.insert` 语义重叠但未接）；导入 STEP/scdoc 进新组件 | `catalog.py:119` | 1~2 天 |
| 11 | 命名选择 `prep.named` | 目录标 live、实际无 `_do_prep_named`，点击报「M4 未实现」；需选择集命名 + 树节点 + 高亮 | `catalog.py:292` + `scdm_gui.py:436` | 2~3 天 |
| 12 | 自定义功能区 `tools.customize` | handler 只输出「预留」；命令显隐 + QSettings 持久化 | `scdm_gui.py:1012` | 2~3 天 |
| 13 | 分面·填孔 `facet.fill` | handler 只输出「预留」；网格边界环检测 + 补三角 | `scdm_gui.py:1076` | 2~3 天 |
| 14 | 分面·简化 `facet.reduce` | handler 只输出「预留」；网格抽取/简化（`facets.decimate` 只做了选面） | `scdm_gui.py:1073` | 2~3 天 |
| 15 | 分面·光滑 `facet.smooth` | handler 只输出「预留」；Laplacian 平滑 | `scdm_gui.py:1070` | 2~3 天 |
| 16 | 投影 `create.project` | handler 只输出文字，未把选边写入草图曲线 | `scdm_gui.py:1094` | 2~3 天 |

### 19.2 P1 简化实现补全（每项 1 ~ 8 天，合计约 16 ~ 27 天）

| # | 功能 / 命令 | 现状（简化形态） | 代码位置 | 预估 |
| --- | --- | --- | --- | --- |
| 17 | 脚本回放覆盖面 | `OPS` 仅 11 条命令；螺旋/修复/装配/分面/增材/参数等录制后回放报「跳过未知命令」 | `scdm/scripting.py:174` | 1~2 天 |
| 18 | 剪贴板粘贴 | 固定 +X 10mm；改为点选放置或位移对话框 | `scdm_gui.py:561` | 1 天 |
| 19 | 生成组参数化 | 阵列固定线性 X×3 步距 15mm（无圆周/无选项）；镜像固定 YZ 面；抽壳固定 1mm 开口面 faces[0]；拔模固定 5° faces[0] +Z（盒体拒绝）；螺旋固定参数 | `scdm_gui.py:595-665` | 3~5 天 |
| 20 | 修复组真实现 | `repair.solidify`=缝合别名、`repair.missing`=补隙别名、`repair.small`=多余边别名、`repair.extra`=仅删最小面；缺真正的缺失面检测/小面识别/实体化判定 | `scdm_gui.py:714-753` | 3~5 天 |
| 21 | 参数页任意几何 | 仅 `param_box`/`param_cylinder` 两种内建 builder，无法对已建几何提取/绑定参数 | `scdm/params.py` | 3~5 天 |
| 22 | 装配组补全 | `asm.insert`=创建别名（无文件插入）；移动固定 +X 10mm（无三轴手柄）；爆炸固定 X 偏移；配合仅两面 `align_faces` | `scdm_gui.py:772-829` | 5~8 天 |

### 19.3 P2 交互链路缺口（每项 3 ~ 12 天，合计约 30 ~ 48 天）

| # | 功能 | 现状（缺口） | 代码位置 | 预估 |
| --- | --- | --- | --- | --- |
| 23 | 工具选项生效 | 选项面板多数复选框只展示不消费：拉动「两侧/复制/到面」、移动「沿轴/到点/到面」、填充「保留边/相切连续」、替换「延伸目标面」、分割「保留两侧/仅切割面」、选择的栅格/端点/中点捕捉（未影响拾取）、测量「自动标注」；`_opts_for` 只读 4 个布尔 | `scdm_gui.py:1229-1245`、`left_panel.py:142-153` | 3~5 天 |
| 24 | 边/顶点拾取 + 双击环边 | 边与顶点是整棵合并的单个 line actor，不可单独拾取；双击「选环边」实际走选体逻辑；状态栏点/边过滤器对拾取无效 | `scene.py:248-256,470`、`scdm_gui.py:1773-1778` | 3~5 天 |
| 25 | 测量补全 | 仅两点距离且只进状态栏；缺角度/半径/边边/面面、视口标注数字、Esc 清除（M1-16 规格） | `scdm_gui.py:1710-1719` | 3~4 天 |
| 26 | 截面模式 | 「截面」只把基准面显示出来，无 VTK 剖切面、无拖动手柄、不能在截面上拉出 | `scdm_gui.py:1201` | 5~8 天 |
| 27 | 左栏图层/群组/视图页 | 图层勾选信号 `layer_toggled` 无连接；群组页静态「（尚无群组）」（无保存组）；视图页静态「主视图」（无已存相机/剖面） | `left_panel.py:52-70` | 3~5 天 |
| 28 | 8 个草图图元命令 | 切线/三点矩形/三点圆/椭圆/样条/构造线/偏移/布局均无 handler、不在 live；且 `sketch_outline` 只认矩形与折线闭环（圆走圆柱回退），椭圆/样条闭环需扩 `extrude_sketch` | `catalog.py:60-74`、`sketch.py:175` | 8~12 天 |
| 29 | 草图交互模式 | 「草图模式」只往 XY 建一张草图并加固定尺寸图元（10mm 矩形/Ø10 圆画在原点）：无平面/面拾取进入、无相机贴法向、无点击绘制与拖拽、无网格渲染；约束作用于固定点索引而非用户选中的图元；草图拉动高度固定 10mm | `scdm_gui.py:1171-1199,1476-1568` | 8~12 天 |

### 19.4 P3 研究型大项（每项 1 ~ 3 周，合计约 30 ~ 50+ 天）

| # | 功能 | 现状（缺口） | 代码位置 | 预估 |
| --- | --- | --- | --- | --- |
| 30 | scdoc 写出曲面与颜色 | 仅支持平面面实体（非平面 raise）；缺 `rgb_color` 外观记录（官方打开无颜色）；曲边/曲面 SAB 记录类型未验证 | `scdm/scdoc_write.py:15-17` | 10~15 天 |
| 31 | 工程图视图 | `det.view`=导出 PNG、`det.dim`=状态栏包围盒文本；无 HLR 三视图/投影视图与图面标注 | `scdm_gui.py:961-973` | 10~15 天 |
| 32 | 共享拓扑 / 中面 | `prep.share`、`prep.mid` 无 handler；OCCT 下 imprint/薄面抽取均为内核级难点 | `catalog.py:188,190` | 10~20 天 |
| 33 | KeyShot 页自有渲染 | `ks.render` 实为「导出当前视图 PNG」；真渲染（光照/材质/离屏合成）为可选大项 | `scdm_gui.py:1015` | 10+ 天（可选） |

### 19.5 建议顺序

1. 先清 **P0**（#1~16）：多数是接线活，一天内可见效，也能顺带把 `M5_LIVE`/`M4_LIVE` 与实际 handler 对齐（file.print、prep.named 目前「标了 live 却报未实现」）。
2. 再做 **P1 #23（工具选项）+ #24（边/顶点拾取）**：这两项是「直接建模手感」的最大短板，且为 #26/#28/#29 提供拾取基础。
3. 然后 **#29 草图交互 + #28 草图图元**（M3 真正补完），**#26 截面模式**。
4. **P3** 按产品需要排期：scdoc 曲面写出 > 工程图视图 > 共享拓扑/中面 > 自有渲染。

---

## 20. 功能补齐开发计划（G1–G6）

对应第 19 节盘点。**总目标：状态栏不再出现「未实现 / 预留 / 占位」文案；选项、拾取、标注三条交互链路真实可用。**

**总原则：**

1. 每个工作包带验收标准，并补对应单元测试（`tests/test_g*.py`，沿 `test_m*.py` 风格）。
2. 先接线后算法：能用现有内核/展示能力拼接的不新造轮子（如包围体复用 `additive.build_volume`）。
3. 目录一致性常驻：G1-01 的交叉校验测试进常规 pytest，之后新增命令必须同步 handler 与 live 集合。
4. 不改第 17 节范围边界（不反编译、不对接 ANSYS 进程、不复制品牌资产）。

### 20.1 波次总表

| 波次 | 名称 | 目标 | 预估（人天） | 状态 |
| --- | --- | --- | --- | --- |
| G1 | 对齐与快赢 | 目录-处理一致 + 一天内可见效的 8 项接线 | 5~7 | 完成（2026-08-30） |
| G2 | P0 收尾 | 纯占位清零（恢复/组件/注释/命名选择/网格三件套等） | 15~24 | 完成（2026-08-30） |
| G3 | 交互基础 | 工具选项生效、边/顶点拾取、测量补全、左栏三页 | 12~19 | 完成（2026-08-30） |
| G4 | 草图与截面 | 草图交互模式 + 8 图元 + 完整截面模式 | 21~32 | 完成（2026-08-30） |
| G5 | 建模命令补全 | 生成/修复/装配选项化 + 参数页 + 脚本回放扩面 | 16~26 | 完成（2026-08-30） |
| G6 | 研究型（按需） | scdoc 曲面与颜色、工程图视图、共享拓扑/中面、自有渲染 | 30~50+ | 大部分完成（G6-01/02/03 已实现；曲面 SAB 记录与自有渲染未做） |

G1–G5 全部实现并推送；G6 完成 3/4 项（曲面 SAB 记录与自有渲染除外，见 20.9）。

### 20.2 G1 对齐与快赢（第 1 周）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G1-01 | 目录一致性守卫 | 新增单测：遍历 `all_commands()`，断言「live ⇒ 有 `_do_` handler 或在白名单（safety.tab）」；顺带修正 `file.print`（M5_LIVE 无 handler）与 `prep.named`（M4_LIVE 无 handler）的错位 | — | pytest 全绿；此后点击任意按钮不再出现「标了 live 却报未实现」的假提示 | 0.5 天 |
| G1-02 | 包围体 `prep.enclose` | 复用 `additive.build_volume`（1mm 余量），包络体入树 | G1-01 | 选中体点击后生成外包络实体 | 0.5 天 |
| G1-03 | 草图网格 `sketch.grid` | 草图模式按平面渲染栅格 actor，开关与选项页同步 | G1-01 | 开启可见栅格、关闭消失，退出草图自动隐藏 | 0.5~1 天 |
| G1-04 | 参数发布 `wb.publish` | 参数导出 JSON/CSV（体名、参数名/值、时间戳） | G1-01 | 生成文件，且本程序可读回重建参数盒 | 0.5~1 天 |
| G1-05 | 轮廓边 `gfx.silhouette` | VTK FeatureEdges 滤镜叠加当前渲染 | G1-01 | 曲面体轮廓随视图旋转更新、可开关 | 0.5~1 天 |
| G1-06 | 剖面显示 `gfx.section` | 静态 clipping plane（包围盒中位、六向可选）；拖动手柄归 G4-03 | G1-01 | 开启半剖显示，关闭恢复 | 1 天 |
| G1-07 | 打印 `file.print` | QPrintPreview 输出当前视图位图 | G1-01 | 打印/预览内容 = 导出 PNG 内容 | 1 天 |
| G1-08 | 视口右键菜单 | QMenu：隐藏 / 仅显示 / 缩放到 / 改色，能力对齐树右键 | G1-01 | 菜单项全部生效 | 0.5~1 天 |

### 20.3 G2 P0 收尾（第 2~3 周）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G2-01 | 崩溃恢复 `file.recover` | 会话脏时周期性写临时包（复用 `io_project.save_scdm`）；启动检测并提示恢复 | G1-01 | 强杀进程后重启可恢复到上次自动保存点 | 1~2 天 |
| G2-02 | 插入组件 `insert.component` | 文件对话框导入 STEP/scdoc/BREP 为新组件并入树 | G1-01 | 导入文件出现组件节点，可锚定/移动/轻量化 | 1~2 天 |
| G2-03 | 注释 `det.note` | 视口锚定文字注记（选点 + 输入文本），入会话数据、可显隐 | G1-01 | 注记在导出 PNG 中可见，重开会话保留（scdm 包） | 1~2 天 |
| G2-04 | 命名选择 `prep.named` | 当前选择集命名保存，树增「命名选择」节点，点击重新高亮 | G1-01 | 命名后随时点击可还原同一组面/边/体高亮 | 2~3 天 |
| G2-05 | 自定义功能区 `tools.customize` | 命令显隐对话框 + QSettings 持久化 | G1-01 | 隐藏的命令重启后仍隐藏，可恢复默认 | 2~3 天 |
| G2-06 | 投影 `create.project` | 拾取边/面边环，按当前草图平面投影生成草图曲线 | G1-03 | 投影线入草图曲线表，可参与闭环拉伸 | 2~3 天 |
| G2-07 | 分面三件套 | `facet.fill` 边界环检测补三角；`facet.reduce` 三角形抽取简化；`facet.smooth` Laplacian 平滑（纯 numpy 层） | G1-01 | STL 导入后三操作各有可见效果且网格拓扑合法 | 6~9 天 |

### 20.4 G3 交互基础（第 3~5 周，直接建模手感的根）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G3-01 | 工具选项生效 | 逐项接线并扩内核参数：拉动（两侧/复制/到面）、移动（沿轴/到点/到面）、填充（保留边/相切连续 → ShapeFix 参数）、替换（延伸目标面）、分割（保留两侧/仅切割面）、捕捉（栅格/端点/中点影响拾取与放置坐标） | G1-01 | 每个选项有可观察行为差异；kernel 层新参数有单测 | 3~5 天 |
| G3-02 | 边/顶点拾取与环选 | 边/顶点改为可独立拾取的 actor；双击边 → 整环（相切连续/共面策略）；状态栏点/边过滤器真正作用于拾取 | G1-01 | 双击盒体竖边选中 4 边环；关闭「边」过滤器后点不中边 | 3~5 天 |
| G3-03 | 测量补全 | 点点/边边/面面距离、线线角度、圆柱面半径/直径；视口数字标注 actor；Esc 清除（对齐 M1-16 规格） | G3-02 | 盒体对角线、两面夹角、圆柱半径均有视口标注 | 3~4 天 |
| G3-04 | 左栏三页激活 | 图层勾选连接 scene 显隐（图层 → body 分组）；群组页保存/加载选择集；视图页存相机/剖面并可一键回放 | G1-01 | 建图层改显隐；群组可存取；存视图后一键回位 | 3~5 天 |

### 20.5 G4 草图与截面（第 5~8 周）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G4-01 | 草图交互模式 | 拾取基准面/平面进入草图；相机贴法向；网格显示；视口点击绘制 line/rect/circle/point 并拖拽定尺寸；Esc/右键退出回三维 | G1-03, G3-01 | 在 YZ 面点击拖画矩形并拉动成体（替换固定 10mm 图元路径） | 5~7 天 |
| G4-02 | 草图图元八件 | 切线（线-圆相切拾取）、三点矩形、三点圆、椭圆、样条（插值）、构造线（不入闭环）、偏移（等距曲线）、布局（多平面布局）；`sketch_outline`/`extrude_sketch` 扩展支持椭圆/样条闭环 | G4-01 | 每种图元可绘制、可约束；椭圆闭环可拉伸成体 | 8~12 天 |
| G4-03 | 截面模式完整 | 可拖剖切面手柄（vtkPlaneWidget）、六向定位；截面轮廓可生成草图/拉伸 | G1-06, G4-01 | 拖动手柄剖面实时更新；在截面上拉伸出实体 | 5~8 天 |
| G4-04 | 约束选择化 | 约束作用于用户拾取的图元/端点（替换现在固定点索引的解算）；约束符号与尺寸标注显示 | G4-01, G3-02 | 拾取两条线加平行后正确解算且图上有标记 | 3~5 天 |

### 20.6 G5 建模命令补全（第 8~10 周，可与 G4 并行）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G5-01 | 生成组选项化 | 阵列（线性间距/数量/方向 + 圆周轴/角度）、镜像（拾取基准面）、抽壳（厚度输入 + 开口面多选）、拔模（角度 + 中性面 + 方向）、螺旋（参数对话框） | G3-01 | 各参数可变且体积校验正确；拔模在盒体上成功而非拒绝 | 3~5 天 |
| G5-02 | 修复组真实现 | 缺失面检测（开放边界环 → 补面）、小面识别（面积阈值 + 逐个确认）、实体化（壳体定向闭合判定），替代现有别名实现 | G3-01 | 开口盒补面成实体；小面列表可逐个处理/忽略 | 3~5 天 |
| G5-03 | 装配组补全 | 从文件插入组件；移动组件三轴手柄；爆炸方向/距离可调；配合扩展（轴对齐、平行、距离约束） | G3-01 | 两组件可面贴合与轴对齐；爆炸向量可调 | 5~8 天 |
| G5-04 | 参数页扩展 | 对可参数化来源（基准体/拉伸结果）提取参数并绑定重建，不再限于盒/柱 builder | G3-01 | 对已建圆柱改半径后几何重建 | 3~5 天 |
| G5-05 | 剪贴板与脚本收尾 | 粘贴改为点选放置；`scripting.OPS` 扩至全部已实现命令（含 G5-01/02 新语义） | G3-01 | 录制含阵列/修复的会话可完整回放，无「跳过未知命令」 | 2~3 天 |

### 20.7 G6 研究型（按需排期，不阻塞 G1–G5）

| ID | 工作包 | 内容 | 依赖 | 完成标准 | 预估 |
| --- | --- | --- | --- | --- | --- |
| G6-01 | scdoc 曲面与颜色 | 曲面 SAB 记录类型（cylinder/sphere/cone/torus/curve）逆向验证 + `rgb_color` 外观记录；用 `scdm_interop_check.py --open` 做官方打开回归 | — | 圆柱体写出后官方 SpaceClaim 打开有几何且带颜色；audit 仍 0 unknown | 10~15 天 |
| G6-02 | 工程图视图 | OCCT HLR 出三视图/轴测，尺寸线标注绘入图页（PDF/PNG 输出） | G3-03 | 盒体三视图自动生成并带尺寸标注 | 10~15 天 |
| G6-03 | 共享拓扑/中面 | imprint/general fuse 共享拓扑；薄壁对面配对 + 中面抽取 | — | 两贴合体共享面；薄板抽壳出中面 | 10~20 天 |
| G6-04 | 自有渲染 | 光照/材质/环境与离屏渲染（VTK 或外部管线），替换「PNG 导出」占位 | G1-05 | 渲染图含材质与阴影，参数可调 | 10+ 天（可选） |

### 20.8 里程碑验证

- 每波结束跑全量 pytest + `scdm_interop_check.py` 审计，防止写出/导入回归。
- G4、G5 完成后做一次端到端演练：新建 → 草图画矩形 → 拉伸 → 抽壳 → 阵列 → 截面检查 → 命名选择 → 录制脚本 → 回放 → 存 scdm/scdoc → 重开校验体积。
- G1-01 的一致性守卫测试从 G1 起常驻，保证目录、handler、live 三者不再错位。

### 20.9 实施记录（2026-08-30）

G1–G6 按本节计划逐项实现，每个工作包独立提交并推送 GitHub。测试基线从 58 passed 增至 **87 passed, 1 skipped**（新增 `tests/test_g1.py` 目录守卫 + `tests/test_g2.py` 工具/网格/草图/修复/工程图/圆柱写出单测）。

**第二轮补齐（同日，20.9.b）**：首轮的四项未尽事项已完成三项半——

| 项 | 状态 | 说明 |
| --- | --- | --- |
| scdoc 曲面 SAB 记录 | **圆柱已实现** | 参照不再缺失：官方 BeamProfiles/Circular.scdoc（ACIS 20）与 SrModels/SampleModel*.scdoc（ACIS 28）提供曲面记录样本；解码出圆柱面=cone(cos=1,sin=0)+ellipse 圆边、闭合边无 seam、uv=[0,h/R,−π,π]、loop int15 编码。`write_scdoc` 现按官方布局写出圆柱体（单圆柱或与平面体混排），记录种类/逐 token 与官方参照一致；`sab.py` 兼容 ACIS 20/28 旧头部与 0x0F/0x10 标记。**锥/球/环面与任意曲面体仍限平面回退**（后续按同法扩展） |
| 自有渲染（G6-04） | **已实现** | `ks.render` 升级：超采倍数 1–4×、背景（白/浅灰/黑）、边显示开关；`render_image` 参数化，打印预览共用 |
| 截面「截面上拉」 | **已实现** | 截面 widget 开启后点「草图」：`BRepAlgoAPI_Section` 剖交线链接成环 → 自定义平面草图曲线 → 拉动沿截面法向挤出 |
| 非凸板中面 | **已实现** | 先 `ShapeUpgrade_UnifySameDomain` 合并共面碎片，再用面平移变换取中面（保留凹轮廓与内孔） |
| 草图面内偏置 | **已实现** | 草图平面支持自定义 origin/normal/xdir；拾面进入草图即落在真实面平面上 |

**仍开放（如实记录）：**

| 项 | 状态 | 说明 |
| --- | --- | --- |
| scdoc 锥/球/环面 | 样本已入库 | `references/cyl_step_converted.scdoc`（官方 STEP→scdoc 转存，ACIS 29）+ SampleModel cone/torus 记录样本；cone token 序列与圆柱同构，非零半角（sine/cosine）语义待真锥样本验证 |
| scdoc 曲面自读 | **已回退实现** | 含圆柱体的文件附 bodyFacets 部件（每三角一节点）；自读走网格回退（weld+sew→「网格导入」体，体积≈πR²h 验证通过）；平面体文件保持已验证的 32 项交叉校验布局不变 |
| SpaceClaim 批处理自动化 | **已打通** | 根因是脚本相对路径；正解：`/RunScript=<绝对路径>.py /ExitAfterScript=True` + IronPython `clr.AddReference("SpaceClaim.Api.V19")`、`Document.Open(step, ImportOptions.Create())` 返回窗口数组、`window.Document` 取文档、`GetRootPart().GetBodies()`（journaling 注入）读体数。官方 box.scdoc 阳性对照 bodies=1 |
| 官方打开我们的文件 | **平面体已打通（SAT 通路）** | **突破**：逆向定位 `SabSatConverter.exe`（官方安装内 SAB↔SAT 工具），SAT 文本格式完整暴露 ACIS save 遍历算法。**关键洞察：SabSatConverter 做 restore+re-save，自动把任意顺序的合法 SAT 重排为官方 save 序**——无需手工实现交错发射器。新模块 `scdm/sat_write.py`（OCCT→SAT 文本）+ `references/sat_path.py`（SAT→SAB→scdoc 通路）。**官方验证**：box bodies=1 ✓、box+cyl 混排 bodies=1 ✓、自读体积 1000mm³ ✓；纯圆柱 coedge 拓扑待微调（bodies=0，coedge partner/环序与官方 cyl 参照有差异）。原 SAB writer 路径保留（无官方工具时的回退） |

**第三轮新增：** `references/golden/`（盒/L 形/圆柱三个官方黄金参照）、`references/make_official_ref.py`（官方参照批量生成管线）、`references/verify_open.py`（官方侧验证脚本）、`_facets_bytes`（bodyFacets 写出）、圆柱模板升级为官方 ACIS-29 布局（seam 边、curve id 21/20、surface id 15/14/16、圆边参数 0..2π、顶点在 +major 参数 0 处、面序侧/顶/底）、importer 网格回退（weld+sew）、SAB class interning（首条带名+后续 id-only）、attrib 链指针修正（官方布局 t2=NEXT/t3=PREV/t4=OWNER）。

**主要新增模块：** `scdm/drawing.py`（HLR 三视图）、`tests/test_g1.py`、`tests/test_g2.py`；核心改动集中在 `scdm_gui.py`（命令接线）、`scdm/kernel.py`（边离散/环选/轴对齐/修复/共享拓扑/中面/剖交线）、`scdm/gui/scene.py`（B-rep 拾取、栅格、剖切 widget、测量标注、渲染参数化）、`scdm/scdoc_write.py`（rgb_color、圆柱 ACIS-29 模板、bodyFacets）、`scdoc_parser/sab.py`（多代头部兼容）、`scdm/import_sab.py`（网格回退）。

### 20.10 完整 ACIS 遍历算法机制开发计划（2026-09-03）

#### 20.10.0 现状更新（相对 20.9 的进展）

20.9 中「官方打开我们的文件」仅平面体打通（SAT 通路），且纯圆柱 coedge 待微调。本轮回合已完成：

| 项 | 状态 | 说明 |
| --- | --- | --- |
| **ACIS 遍历算法逆向** | **完成** | 反汇编 `SpaACIS.dll` 的 `api_save_entity_list` + `save_entity_pointer`，确证 FIFO 工作清单：seed BODY → 出队写记录 → 指针字段首次引用登记编号并入队尾。官方 ref_tet 141 记录 FIFO 模拟**精确重现**（LIFO 反证失败）。详见 `references/acis_save_algorithm.md` |
| **原生 FIFO 发射器** | **完成** | `scdm/sab_emit.py`（`Worklist`+`Makers`）替代旧 `_BOX_KIND_SEQ` 模板交错与二次重排；box/cyl/mixed FIFO 不变量自检全绿 |
| **官方打开（原生）** | **平面体 bodies=1、圆柱 bodies=1** | 定位四个前置条件：①FIFO 遍历序 ②XACIS 字符串池驻留（`%6`）③document.xml 与 SAB attrib Id 体系一致（0:23 模板）④面定向 flag（CCW loop → flag_b）。`verify_open.py` 哨兵 `done bodies=1` |
| **解析器容错** | **完成** | `SabModel._decode` 对布局变体容错（可选 bbox/uv/参数、face/coedge/edge/vertex/loop 指针守卫、新增几何类）。Library 全部 6 个 SrModels 解析成功（此前全崩）；ref_tet 解码保持精确 |

**遍历算法机制业已完整实现并官方验证；缺的是「实体类写模板覆盖」。** 当前原生路径仅支持平面体（plane+straight）与圆柱（cone+ellipse）；其余实体类靠 SAT 路径（官方 SabSatConverter）兜底。

#### 20.10.1 目标界定

「完整」= **原生 FIFO 路径能写出任意常用 B-rep 几何的官方可打开 scdoc**，按价值分三级：

- **T1 常用旋转/球/圆环**：`torus`、`sphere`
- **T2 参数曲线**：`pcurve`、`intcurve`、`exppc`（`exactcur`/`surfintcur` 顺带）
- **T3 自由曲面/曲线**：`nurbs`/`nubs`、`spline`（`nullbs`、`null_surface` 顺带）

#### 20.10.2 实体类清单（来自全部 Library 模型 + ref 参照合计）

| 类别 | 类 | 现状 |
| --- | --- | --- |
| 拓扑核心 | body/lump/shell/face/loop/coedge/edge/vertex/point | ✅ 已实现写入 |
| 基础几何 | plane/cone/straight/ellipse | ✅ 已实现写入 |
| 常用曲面 | **torus, sphere** | ❌ |
| 参数曲面 | **nubs, spline, nullbs, nurbs** | ❌（量最大） |
| 参数曲线 | **pcurve, intcurve, exppc, exactcur, surfintcur** | ❌（导入模型主流） |
| 拓扑变体 | tcoedge/tvertex/tedge/ref/null_surface | ❌（透传即可） |
| attrib | string_attrib/wstring_attrib/rgb_color/integer_attrib | ✅（写 string/rgb） |

#### 20.10.3 核心战略：数据驱动布局库（重构 Makers）

**不做「每类一个手写函数」，改为「布局表 + 通用发射器」**，这是规模化的关键：

```
class_layouts = {
   'torus': TorusLayout,   # 只声明字段 token 序列 + 槽位语义
   ...
}
```

- **字段序列** = 该类每 token 的 kind（ptr/int/double/vec3/vec3b/flag/string）+ 可选性范围
- **槽位语义** = 每个 ptr 槽指向的实体类（如 coedge.t4→coedge、t6→partner coedge）
- **几何参数**（半径/中心/法向/控制点等）从 OCCT 形状（`BRepAdaptor_Surface`/`Geom_BSplineSurface` 等）提取
- **布局获取无需手抄**：现有 `SabSatConverter`（官方 SAB→SAT 文本）+ SpaACIS.dll 反汇编 `save_data` 工具链，可对每类**自动生成** schema

#### 20.10.4 分阶段步骤

> 依赖顺序：先 Phase 0 + Phase 1（基建，让后续类「只加一行布局表」），再按 T1→T2→T3 逐批推进。

**Phase 0 — 布局逆向管线（基建）**
- [ ] `references/extract_layouts.py`：对每类取官方样本（Library 模型 + ref）→ `SabSatConverter` 转 SAT → 反汇编对应 `save_data` → 自动生成字段 token 序列（含可选字段范围）与语义槽位表
- [ ] 产出 `scdm/layouts/class_layouts.json`
- **验证**：用布局表重放 ref_tet/cyl 已知流，字节级比对（复用 `reserialize.py`）

**Phase 1 — 通用发射器重构**
- [ ] `sab_emit.py` 新增 `LayoutEmitter`：输入=实体图（OCCT `explore`）+ `class_layouts`；输出=记录流（复用 `Worklist`）
- [ ] `Makers` 改薄：只做「OCCT 几何 → 实体图 + 每实体参数」，模板交给 `LayoutEmitter`；删除手写 `_face`/`_coedge`/`_c*` 等
- **验证**：box/cyl/mixed 官方打开 bodies=1 不回归（全量 92+2 测试绿）

**Phase 2 — T1 常用旋转曲面**
- [ ] `torus`（中心/法向/主半径/副半径）与 `sphere`（球面）字段模板 + OCCT 参数映射
- **验证**：生成 torus/sphere scdoc → `SabSatConverter` restore + SpaceClaim 打开 bodies=1

**Phase 3 — T2 参数曲线**
- [ ] `pcurve`（面-曲线 UV 参数化，base curve + pcurve surface 双段结构）、`intcurve`/`exactcur`/`surfintcur`（两曲面交线）、`exppc`
- **验证**：对含此类类的官方样本（SampleModel1/5）做「读→解→写→官方打开」一致性闭环

**Phase 4 — T3 自由曲面/曲线**
- [ ] `nurbs`/`nubs`（B 样条面：控制点网格 + 节点向量 + 阶数 + 权重）、`spline`（B 样条曲线）
- **验证**：对含曲面的官方模型写回官方打开

**Phase 5 — 拓扑变体透传 + 稳健性**
- [ ] tcoedge/tvertex/tedge/ref/null_surface 标记为透传（字段存在即可）
- [ ] `topology.py` 解析器补齐这些 kind（已有 optional 容错基础）

**Phase 6 — 回归与文档**
- [ ] 全量测试绿；`references/acis_save_algorithm.md` 追加 entity coverage 矩阵；提交推送

#### 20.10.4.b Phase 3/4 实施记录（2026-09-04，进行中）

**参数曲线集群逆向完成**（`_refs` → `references/golden/{loft,spline,splineedge}.scdoc` 三个官方参照）：

- **intcurve 边曲线集群**（单条 0x0D 记录内嵌子类型）：`[ptr,int,int,ptr 前缀][flag][0x0F] + exactcur(int,int15) + nubs + null_surface×2(空) + nullbs(空) + nullbs(固定模板) + [0x10][flag_b flag_b][0x11]`
- **nubs 曲线布局**：`[int degree][int15 0][int #distinct-knots][(double knot, int mult)...][poles (x,y,z)×n]`——degree/knots 语义由 degree-2 三极点样例（splineedge）定谳
- **pcurve 非必需**：官方 loft（cone 面 + intcurve seam）coedge 的 pcurve 槽全为 -1 且官方打开正常
- **class id 文件内注册制确认**：新类用首次出现全名头 + 任意一致 id 即可（22+）
- **intcurve vs surfcur 区分**：顶层边曲线 = `intcurve-curve`（带 ENTITY 前缀）；surfcur 子类型 = 裸 `intcurve`（无前缀）

**已交付**：`scdm/sab_emit.py` 的 `intcurve_cluster_bytes` / `_nubs_body` / `_rec_header` / NULLBS 模板（token 级与官方 loft 集群一致）+ 回归测试；97 tests 绿。

**下一步**：NURBS 曲面集群（spline+exactsur+nurbs+both，SAT 文本已解码出 knots/poles/权重网格布局）+ OCCT `Geom_BSplineSurface` 提取器 + 写入管线接线 + restore/官方打开验证。

#### 20.10.4.c NURBS 曲面集群定谳（2026-09-04，同日续）

**spline-surface 集群完整布局**（官方 spline.scdoc 面曲面 77 token 逐字段验证一致）：

```
T_RECORD "surface" [id]
  [ptr attrib][int -1][int -1][ptr -1][sense flag]
  0x0F
    exactsur: [int 0][int15 0]                    ← "0 full"
    nurbs:    [int u_deg][int v_deg]              ← "2 1"
    both:     [int15×4 = u/v periodicity + u/v form（open/none=0，periodic=2）]
              [#u knots][#v knots]
              [(double val)(int mult)]×#u + [(double val)(int mult)]×#v
              [poles (x,y,z,w) × u_poles × v_poles]  ← v-slowest
              [double fitol=0.0]
              [int 0][int 1][double 0.0][int 0×4]      ← crossing/seam 段（open 面）
              [(flag_a)(double)]×4                      ← "F 1 F 0 F 1 F 0"
  0x10 + [flag_b×4] + 0x11
```

**knot mult 存储约定定谳**：ACIS 存储的端点 mult = 标准 clamped mult − 1（例：标准 (3,2,3) 存 (2,2,3→2)），极点数 = Σ(存储 mult) − deg + 1。极点网格 v-slowest，每极点 4 double（x,y,z,w，非有理时 w=1）。

**已交付**：`spline_surface_cluster_bytes`/`_nurbs_surface_body`（token 级与官方 both 记录 77/77 一致）+ 重放回归测试；98 tests 绿。

**下一步（管线接线）**：OCCT `Geom_BSplineSurface` 提取器（deg/knots/mults/poles/weights，端点 mult −1 换算）→ `Makers` 增加 `("bsurf", bi, fi)` 面曲面分派 + B 样条边的 intcurve 集群分派 → `write_scdoc` 识别 B 样条体 → restore + SpaceClaim bodies=1 验证。

#### 20.10.4.d 透传类增强（2026-09-04，同日续）

**容忍拓扑（tvertex/tedge/tcoedge）双向打通**：

- 布局定谳（SampleModel4 官方样本）：均为 `chain(子类)+record(基类)` 形式——tvertex=vertex+尾部容差 double；tedge=edge+尾部容差（token 15）；tcoedge=coedge+pcurve 槽+（t_start,t_end）+尾部 flag_b
- **解析器**（topology.py）：三类的完整解码（edge/point/coedge/loop 字段 + tolerance/t_range）——容忍模型（导入件常见）现可全量遍历
- **发射器**（sab_emit.py）：`tvertex_record`/`tedge_record`/`tcoedge_record` + CID 32-34，tvertex 与官方记录 token 级一致
- 回归测试守护；99 tests 绿

**pcurve/exppc 集群布局已解（待发射器）**：`pcurve[ptr,int,int,ptr,int 0,flag]+0x0F+exppc+nubs(2D)+spline[0x0F]+exactsur+nurbs+both(曲面)+[0x10+4flags]+[0x10+2 doubles]+0x11`（双层嵌套；2D nubs 极点为 (u,v) 对）。coedge 第 11 槽 = pcurve 指针。已证官方打开非必需，作为保真增强后续落地。

#### 20.10.4.e Phase 5/6 完成（2026-09-04）

- **Phase 5（拓扑变体透传 + 稳健性）完成**：解析器补齐 nubs（form/knots/mults/poles 3D+2D/推导阶数；Library 2863 条解出 2503，阶数 1-5 合理 2411）、nurbs 双阶数、exppc/ref/exactcur/exactsur 形式码、intcurve/spline/surfintcur 等十余类 sense——配合此前 tvertex/tedge/tcoedge 全解码，**Library 全部 22 类 kind 均有解码路径**；分支优先级修正（nubs/pcurve/exppc/intcurve 移出通用几何分支）
- **Phase 6（回归与文档）完成**：`references/acis_save_algorithm.md` 追加**实体类覆盖矩阵**（写入路径 8 组类 + 官方打开结果；读取路径 22 类解码深度；验证基线 99 tests + 5 类几何官方 bodies=1）；全量测试绿；提交推送

**20.10 计划全景完成**：完整 ACIS 遍历算法机制（FIFO 工作清单 + 数据驱动布局 + LayoutEmitter）+ T1 旋转/球/环 + T2/T3 参数曲线与自由曲面 + 容忍拓扑透传，原生写出 → 官方 SpaceClaim bodies=1。

#### 20.10.5 工作量与风险

| 阶段 | 依赖 | 量级 | 说明 |
| --- | --- | --- | --- |
| Phase 0 | 逆向管线（SAT 文本 + 反汇编已有） | 中 | 管线规模化关键 |
| Phase 1 | Phase 0 | 中 | 重构，风险集中，须守住 box/cyl 回归 |
| Phase 2 | Phase 1 | 小-中 | |
| Phase 3 | Phase 0 | 中 | 参数曲线链路最复杂（pcurve 双段结构） |
| Phase 4 | Phase 0 + 3 | 大 | B 样条字段多 |
| Phase 5 | Phase 1 | 小 | |
| Phase 6 | 全部 | 小 | |

**最大风险**：Phase 3 的 `pcurve`（曲线↔面 UV 空间双段连接体）；**最高价值**：Phase 4（自由曲面，导入模型主流）。

#### 20.10.6 建议执行路径

按依赖顺序先做 **Phase 0 + Phase 1**（让后续所有类「只加一行布局表即可」），再按 **T1→T2→T3** 逐批推进，每批独立验证官方打开，完成后推送 GitHub。

## 21. SpaceClaim 100% 对标开发规划（2026-09-05 全量盘点后）

### 21.1 现状快照（实测）

| 层 | 实测状态 |
| --- | --- |
| UI 命令面 | 14 页签 / 125 命令 / **123 live**（仅 prep.small、safety.tab 占位） |
| 内核（kernel.py 71 函数） | 基本体×4、拉伸/旋转/螺旋/棱柱、布尔、圆角/倒角/抽壳/拔模/偏移、阵列（线性/圆周）、镜像、分割、修复组（缝隙/缺失面/实体化/缝合）、中面/共享拓扑、干涉/体积/面积/重心、STEP/STL/BREP 读写、离散 |
| scdoc 数据层 | **读取**：22 类 SAB 记录全解码（含 B 样条深度解码/容忍拓扑）、facets、document.xml；**写入**：FIFO 遍历 + 平面/圆柱/球/环/B 样条体官方 bodies=1；SAT 备用通路；模板打包 |
| 脚本 | 录制/回放 18 ops |
| 测试 | 99 passed / 1 skipped |

### 21.2 对标差距（三层模型）

- **B 层·命令在但深度不足**（对标 SpaceClaim 同名命令的完整行为）：Pull 全模式族（SpaceClaim 的 Pull 集拉伸/旋转/扫掠/抽壳/偏移/倒圆于一体并按选择对象自动分派）；圆角/倒角（变半径、多链、溢出控制）；抽壳（多厚度+移除面集）；拔模（中性面/分型线）；阵列（填充/草图驱动/沿路径）；草约求解深度；Repair 检查几何全家桶（小面/尖刺/薄片/自交/反向面/短边）；脚本 API 完整度
- **C 层·整页缺失**：Sheet Metal（钣金）、Surface（曲面工具）、Simulation（载荷/支撑/接触）、Rendering（材质/场景）、3D Markup、Structure（梁/焊）
- **D 层·数据/互操作**：导入缺 IGES/SAT/X_T/OBJ/3MF/VRML；导出缺 IGES/SAT（SAT 写出已具 sat_write 基础）/PDF-3D/OBJ；scdoc 写回的 document.xml 深度（图层/命名组/视图/截面/参数/颜色写回，目前模板化）；装配配合类型全家桶

### 21.3 波次规划（H 系列，每波独立验收）

| 波 | 主题 | 关键工作包 | 验收标准 | 预估 |
| --- | --- | --- | --- | --- |
| H1 | 互操作矩阵 | 导入 IGES/OBJ/3MF/VRML（OCCT 现成）；SAT 导出（sat_write→官方 converter 校验）；X_T 经官方 SpaceClaim 批处理管线；导出 PDF-3D；批量互操作回归（官方打开矩阵自动化） | 每格式读→写→官方打开 roundtrip 通过；新增格式化测试 | 5~8 天 |
| H2 | 直接建模深度 | Pull 模式族自动分派（面=拉伸/拔模/偏移、边=倒圆/倒角、线=扫掠、体=抽壳识别）；变半径圆角；多厚度抽壳；中性面拔模；填充阵列/沿路径阵列 | 每模式单测 + 与 SpaceClaim 行为对照清单 | 8~12 天 |
| H3 | 装配深度 | 配合类型（刚性/旋转/圆柱/平面/球/螺旋/距离）；自由度求解与 Motion 拖动；爆炸图保存；组件层级写回 scdoc | 两体六类配合可建可解；爆炸状态可保存重开 | 8~12 天 |
| H4 | Repair 全家桶 | 检查几何（小面/尖刺/薄片/自交/反向面/短边/干涉）+ 一键修复向导；结果面板交互 | 对官方样本库逐项检出率验证 | 5~8 天 |
| H5 | Sheet Metal 页 | 钣金内核（折弯/展开/ ripped/ corner/jog；K 因子）；页签 UI；参数化钣金体 | 逐命令单测 + 展开面积校验 | 10~15 天 |
| H6 | Surface 页 | untrim/patch/blend(曲面)/extend/curve-network/thicken（OCCT ShapeUpgrade/GeomFill 支撑） | 每命令单测 + 官方打开 | 10~15 天 |
| H7 | 参数驱动 + 脚本全量化 | 尺寸驱动 + 表达式（params.py 扩展）；脚本 API 对齐 SpaceClaim 命名（IPart/IEdge...子集）+ 编辑器页 | 录制→改参数→重放重建 | 8~12 天 |
| H8 | Simulation/Rendering/Markup 页 | Simulation（载荷/支撑/接触/区域对象与显示）；Rendering（材质/场景/离屏渲染已有基础）；3D Markup（注释相机+标注） | 页面命令 live + 对象写入 scdoc | 10~15 天 |
| H9 | scdoc 写回深度 | document.xml 全量生成（图层/命名组/保存视图/截面对象/参数/装配层级）替代模板；ID 分配器与 SAB attrib 联动 | 写出文件官方打开 + 元数据逐项可见 | 8~12 天 |

依赖：H2 独立；H5/H6 依赖 H2 的 Pull 分派重构；H7 依赖 H3/H2；H9 依赖数据层现状（无依赖）。建议顺序 **H1 → H2 → H3 → H4**（互操作与深度优先），H5/H6 并行，H7→H8→H9 收尾。

### 21.3.b H1 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| 内核格式函数 | `read_iges/write_iges`（体积精确 roundtrip）、`read_obj/write_obj`（v/f ↔ weld+sew）、`read_3mf/write_3mf`（zip+XML 网格）、`write_vrml`（VrmlAPI）、`read_stl`（StlAPI） | 单测 6 项 |
| SAT 导出接入 | GUI 另存为 9 格式（STEP/SCDM/SCDOC/STL/IGES/SAT/OBJ/3MF/VRML） | sat_write→官方 converter restore |
| X_T 导入 | `references/spaceclaim_import.py`：官方 SpaceClaim 批处理管线（/RunScript→SaveAs scdoc→自有解析器读回），X_T/X_B/XMT 直通 | 管线复用已验证的 make_official_ref 机制 |
| 互操作矩阵 | `references/interop_matrix.py`：box/cyl/sphere/torus × {restore, self, SAT, IGES, OBJ, 3MF} + `--spaceclaim` 官方打开 | 全行 OK exit 0；哨兵 bodies=1 |
| GUI 导入 | 打开对话框 10 扩展名；X_T 走官方管线 | 接线完成 |
| 测试 | `tests/test_interop.py`（含官方 restore 门禁） | **105 passed** |

注：SAT 备用通路覆盖平面/圆柱（sphere/torus 在矩阵中标 `--`，native 路径已官方覆盖）。

### 21.3.c H2 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| Pull 模式族分派 | `kernel.pull_auto`：face+方向→拉伸/切削、edge→倒圆（或 chamfer 模式）、solid→抽壳、draft 模式 | 分派单测 4 断言 |
| 变半径圆角 | `kernel.fillet_variable`：逐边半径 + 沿边 (u,r) 演化（`SetRadius(TColgp_Array1OfPnt2d, IC, IinC)`） | 沿边体积严格落在两端等半径圆角之间 |
| 多厚度抽壳 | `kernel.shell_multi`：逐面内法向棱柱并集构成壁层，空腔=体−壁层——绕开 MakeThickSolidByJoin 在圆角体/多开面上的失败；壁厚组合精确（介于两个等厚抽壳之间） | 体积精确验证 |
| 中性面拔模 | `kernel.draft_neutral`（BRepOffsetAPI_DraftAngle + 中性面平面）；不可拔模面跳过 | 圆角体拔模单测 |
| 沿路径/填充阵列 | `kernel.pattern_path`（弧长均布）、`kernel.pattern_fill`（矩形网格+间隙） | 5 份/3×3 网格单测 |
| 脚本接线 | `create.blend_variable` / `create.shell_multi` / `create.draft_neutral` / `tool.pull_auto`；`create.pattern` 增 path/fill 模式；中性面自动取平面 | 录制回放 5 步链全通 |
| 测试 | `tests/test_h2.py` 9 项 | **113 passed** |

关键排障：①`SetRadius` 需 (IC, IinC) 双索引且 `IsDone` 在 `Build()` 后才有效；②`shell_solid(shape,t,[])` 无移除面时返回内腔实体（MakeThickSolidByJoin 语义怪癖），且在圆角体上直接失败——棱柱壁层构造彻底绕开；③拔模对与圆角相切的平面拒绝（SpaceClaim 同样拒绝），脚本层容错跳过。

### 21.3.d H3 实施记录（2026-09-05，核心完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| 配合求解器 | `scdm/mates.py`：7 类运动副（刚性 0 DOF / 旋转 1 / 圆柱 2 / 平面 3 / 球 3 / 螺旋 1 耦合 / 距离 6）；`solve_transform` 带 θ/slide 驱动参数；`frame_of` 从平面/圆柱面、直线/圆边提取参考系 | 数学级 7 断言 |
| 运动拖动 | `kernel.apply_mat4` 把求解矩阵施于形体；旋转 90° 拖动、圆柱滑+转验证 | OCCT 形体级 2 断言 |
| 爆炸图保存 | `Component.explosion` 每组件方向持久化（io_project 随项目保存） | 接线完成 |
| GUI 配合对话框 | 0-6 七类运动副（保留 7/8 面贴合/轴对齐旧语义）；运动副走求解器并记录 `KernelDoc.mates` | 接线完成 |
| 组件层级写回 scdoc | **归入 H9**（多 part SAB 包 + document.xml PartDef 树，与图层/命名组同批实现） | — |
| 测试 | `tests/test_mates.py` 9 项 | **122 passed** |

运动学语义：配合求解先把 B 参考系落到关节（fb.origin→fa.origin），再按 θ 绕 A 轴转动 / 沿轴滑移——与标准运动副约定一致。

### 21.3.e H4 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| 检出器 | `kernel.check_geometry`：小面（面积阈值）、尖刺/薄片（面积↔边跨比）、短边、自交（BRepAlgoAPI_Check）、反向面（定向法向↔重心点积启发式）、开壳（单面使用的边） | 干净盒零发现；缺陷体逐项检出 |
| 自动修复 | `kernel.repair_geometry`：短边/缝隙 ShapeFix_Wireframe；反向面 ShapeBuild_ReShape 替换**重建面**（同 TShape 替换被忽略的关键坑）；小面/薄片 unify-same-domain 愈合 | 反向面检出→修复→归零，体积保持 |
| 逐面反转 | `kernel.reverse_face` 公开 | 单测 |
| GUI | `repair.check`（检查几何）命令 + 放大镜图标 + 一键修复报告 | catalog 守卫通过 |
| 脚本 | `repair.check` op（阈值参数化） | 录制回放 |
| 测试 | `tests/test_h4.py` 7 项 | **129 passed** |

### 21.3.f H5 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| K 因子折弯 | `sheetmetal.bend_allowance`（BA=θ·(R+K·t)）+ `bend_from_flat`（物理正确 L 弯：内半径切上表面、轴 z=t+R、绕 −Y 旋转；flat2 预置弯后旋转升起；体积=flat1+弧+flat2 精确） | 体积 1e-6 精度 |
| 折弯检测 | `detect_bends`：共轴圆柱组→单折弯（r_inner=min）；扫掠角取邻接平面法向夹角（法向∥轴的侧壁过滤）；flat 长度用 (轴×法向) 方向 bbox 跨度 | R/角/flat1/flat2/t/w 全对 |
| 展开 | `unfold`：展开长=flat1+BA+flat2；K 单调（0.2→0.8 长度递增） | 0.053801 精确 |
| 撕裂 | `rip`：沿面最长边切缝（gap×厚度截面，中心缝=半 gap） | 缝宽精确 |
| 角落释放 | `corner_relief`（圆/方）：中心钉入材料内侧 1/4 尺寸（贴边布尔不可靠） | 体积减少 |
| 折叠 | `jog`：Z 形三盒（平角，后续可倒圆） | 体积/包盒精确 |
| 页签 UI | 钣金页 5 命令（折弯/展开/撕裂/角落释放/折叠）+ K 因子参数对话框 + 图标 | catalog 守卫通过 |
| 测试 | `tests/test_sheetmetal.py` 9 项 | **138 passed** |

### 21.3.g H6 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| 去修剪 | `surface.untrim`：自然界重建面；OCCT 无穷标记（±2e100 是有限 float！）按 1e50 阈值识别并以原范围外扩替换——圆柱去缝（面积 3 倍）、平面外扩 | 单测 2 项 |
| 延伸 | `surface.extend_face`：B 样条走 GeomLib ExtendSurfByLength；平面/通用走 UV 界扩展（surface 句柄 6 参 MakeFace） | 面积增长精确 |
| 偏移面 | `surface.offset_face`：Geom_OffsetSurface + 保持原 UV 界；圆柱偏移用曲面采样点验证 R+dist（偏移面不再是解析圆柱——正确行为） | 采样 0.006 精确 |
| 加厚 | `surface.thicken`：面沿法向棱柱拉伸（单侧加厚） | 体积=面积×厚度 |
| 补面 | `surface.patch_fill`：BRepFill_Filling N 边补面（G0/G1 连续度） | 方形 1e-4 精确 |
| 过渡 | `surface.blend_loft`：ThruSections 非规则 B 样条过渡面 | 双圆过渡面成面 |
| 页签 UI | 曲面页 6 命令（加厚/偏移/去修剪/延伸/补面/过渡），作用于所选面 | catalog 守卫通过 |
| 测试 | `tests/test_surface.py` 7 项 | **145 passed** |

排障：①GeomLib 顶层无 GeomLib 类——函数为模块级 `geomlib_ExtendSurfByLength`（弃用别名）；②Geom_BSplineSurface ctor 需要 (poles,uk,vk,um,vm,udeg,vdeg)；③OCCT 用 ±2e100 有限巨值表示无穷参数界；④MakeFace 无 (gp_Pln,u,v) 重载——用 Geom_Surface 句柄 6 参。

### 21.3.h H7 实施记录（2026-09-05，完成）

| 工作包 | 交付 | 验证 |
| --- | --- | --- |
| 表达式参数表 | `params.ParamTable`：命名参数 + 表达式值（依赖排序求值、循环/未知引用/注入全拒绝——白名单算术 eval）；`eval_expr` 安全求值 | 传播/循环/注入 5 断言 |
| 参数驱动重建 | `Parametric` 参数值可为表达式串绑定全局表（体参数 = 全局命名参数）；w=20→40 全局驱动 H="w*1.5" 重 build 体积恰 4 倍 | 端到端 |
| 脚本 API | `scdm/script_api.py`：ScriptSession/GetRootPart/DesignBody（Name/Shape/Volume/GetFaces/GetEdges）/AddBox/Cylinder/Sphere/CombineUnite·Subtract·Intersect/MoveBody/FilletEdges/SetParameter/GetParameter/RebuildAll | 端到端门面链 |
| 脚本全量化 | OPS 新增 insert.box / sheet.bend / sheet.unfold / surface.thicken / surface.offset / surface.untrim / repair.check（累计 29 ops） | 4 步回放链 |
| 参数表持久化 | `kdoc.param_table` 随项目 pickle 保存 | 接线完成 |
| 测试 | `tests/test_h7.py` 10 项 | **155 passed** |

排障：①`_IDENT` 正则带 `$` 锚点使 findall 只取末标识符——拆分为全匹配校验/无锚分词两个正则；②replay 的 op 返回值被包装为 "OK <cmd>"，状态文本断言需用 startswith。

### 21.3.i H8+H9 实施记录（2026-09-05，完成）

**H8 Simulation/Markup 页**：`scdm/simprep.py` 数据模型（Load/Support/Contact/MarkupNote + describe/summary）；`kdoc.sim` 随项目 pickle 持久化；catalog 新增仿真页（载荷/支撑/接触/报告）与标记页（便签/列表），GUI 处理器把对象记录到所选面；`kdoc.notes` property 把标记桥接到视口标注渲染（旧格式经 setter 迁移）。

**H9 scdoc 写回深度**：
- **`write_scdoc_multi`**：**一体一 part**（官方 samplemodel2 实证布局）——每体独立 partN.sab；document.xml 全量生成（每体 PartDef + NominalFaceDef/NominalEdgeDef id 与各 part 的 SAB attrib id 对齐 + 组件 LayerDef + SavedViewsDef）；bodyFacets rel 仅在含非平面体时写入
- **关键发现：官方多体 SAB 为逐体深度优先**（每体子树耗尽才引用下一体）——原全体预入队 breadth 序官方 restore 报 `indexing mechanism failed`；`Worklist.run` 改惰性逐体 seeding（单 body 流不变）
- **读取端**：`load_scdoc` 解析全部 geometry parts 为 `models[]`；`import_scdoc_bundle` 逐 part 合并（B-rep sew 失败的非平面 part 走 facets 网格兜底）
- 验证：双体装配（box+cyl）双 part 均过官方 SabSatConverter restore；自读合并 2 体（box B-rep + cyl 网格兜底）
- 测试 `tests/test_h8h9.py` 6 项；**161 passed**

### 21.4 统一验收协议

1. 每工作包单测（pytest，OCCT 级断言）
2. 数据层改动必须过**官方互操作矩阵**：本方写出 → SabSatConverter restore + SpaceClaim `/RunScript` 哨兵 bodies>0
3. UI 命令 live 状态与 catalog 守卫测试联动（tests/test_g1.py 既有机制）
4. 每波结束跑全量测试 + push GitHub
