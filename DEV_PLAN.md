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
| M2 | 直接建模（产品成立点） | 命令栈 + Pull / Move / Fill / Combine / Split + 圆柱球 + 保存 | **新建 → 插圆柱 → 拉动面 → 合并 → 撤销 → 存 STEP → 再打开** | 进行中（核心路径已通：test_m2.py 在 kernel/tool/history 层跑通接受路径；工具态机并入 scdm/tools；选项生效：拉动对称/移动复制+沿面法向/分割取面/合并三态；替换 Replace 已接线） |
| M3 | 草图 | 平面上画线圆矩、基础约束、闭环后拉动成体 | 在 XY 上画矩形 → 拉动成盒子 → 撤销回到草图 | 进行中（scdm/sketch.py：二维约束求解（尺寸/水平/竖直/重合/垂直）+ 闭环线段/矩形拉伸成体；约束命令已接线；草图视口渲染待补） |
| M4 | 扩展 | 倒圆/抽壳/阵列/镜像、截面、修复、装配、脚本 | 对盒子倒圆并阵列；缝合开放壳体；Python 建体 | 未开始 |
| M5 | 后期 | `.scdoc` 写出、分面/增材/工程图 | 写出文件可被本程序回读；官方 SCDM 互操作作为加分项 | 未开始 |

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
