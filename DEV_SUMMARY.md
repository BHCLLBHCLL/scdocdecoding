# DEV_SUMMARY — 攻坚记录

## 🏆 2026-09-06 决胜成果：整装配写回官方打开 bodies=2 —— TODO-9 关闭

> 起点：上轮已达成单体原生链路官方打开 bodies=1，且装配写回的实例态字段、rels
> moniker、体 part 编号已与官方样本机制对齐；但**我们的整装配官方打开仍 bodies=0**
> （哨兵修正后官方样本 bodies=2）。本轮以「官方样本 ↔ 我们的产物」双向差分定位收
> 掉最后一环，官方哨兵实测 `done bodies=2`，提交 `1d3f46f`，187 tests 绿。

### 0. 方法论：双向差分定位

- 哨兵升级：`references/verify_open2.py`（part 级富诊断）——逐 part 计体数与面数
  （box=6 面 / cyl=3 面，可识别"活着的是哪一个体"）、逐组件计 `GetBodies()`。
  原 verify_open 只数根部件直属体 + 组件体，无法区分三种失败形态。
- 三种失败形态（症状分级）：
  1. **整文档落空**：`doc.Parts` 只剩空白根部件（"设计1"）——读者 schema 反序列化
     失败后静默回退空文档（不报错）；
  2. **part 有体、组件空壳**：`doc.Parts` 显示体已载入 part，但组件 `GetBodies()`
     抛空引用——组件 source moniker 解析失败；
  3. **组件静默丢失**：`components` 计数比 ComponentDef 少——id 撞号。
- 空间约束：SpaceClaim 单实例，验证链必须串行；每次官方开档 ~1.5–2 分钟，
  全程 50+ 个变体（`_v1.._v57` 差分包）逐步收敛。

### 1. 被对拍反证的假设（上轮 TODO-9 主假设不成立）

| 假设 | 实验 | 结论 |
|---|---|---|
| renderlist.xml 按实例 `Path="0:27"` 逐体挂渲染条目（上轮 TODO-9 解锁路径） | 官方样本**删掉 renderlist part + rel** 仍 bodies=2；我们的 renderlist 换进官方样本仍 2 | 与体绑定无关（纯显示元数据） |
| facets.bin 体绑定 | 官方样本换入我们 facets（体号 23/83 与其文档 30/107 不符）仍 bodies=2 | 读端不校验 facets 体号 |
| checksums.bin/rels 完整性 | 官方样本 checksum rel Id 全部打乱仍 bodies=2（且实测 Id 非目标内容 SHA1） | 不参与绑定 |
| windows.xml 整体 | 官方样本换入我们 windows 仍 bodies=2 | 仅其中**文档 GUID** 有影响（见 §2-3） |
| SAB 实体序号（先怀疑、后证实无害） | 柱体 body seq 0→19 单独打补丁不改变结果 | 序号并非绑定键，但仍按官方布局补齐（§2-4） |

### 2. 六处真实绑定要求（逐一定位与修复）

| # | 要求 | 症状/定位实验 | 修复 |
|---|---|---|---|
| 1 | **sectionId 是读者固定节键**：Design=`6ab505a9-1afc-4b43-a7db-eb0258edde3e`、PresentationDef=`595f79a0-e194-4d77-946d-55f551b8663a`、DocumentSettingsDef=`0ac8f8e0-608c-4b1e-a830-61e2a4bad599`——所有官方文档同一组 GUID | 我们自造的 `11111111…/22222222…` 节键 → 症状 1（整文档落空）；单换回官方节键立即复活 | `_assembly_document_xml` 改用官方常量 |
| 2 | **sctype moniker 字符串逐字精确**：`BasicMoniker`1[[…]]` 多一个反斜杠即无效 | 症状 2（组件 GetBodies 空引用）；新文档生成器转录时混入转义反斜杠 | 逐字对齐官方字符串 + 回归断言 |
| 3 | **versions.xml / windows.xml 必须载文档 GUID**：模板包里是 fc598e53，我们的 moniker GUID 是 9d32a3b4 | windows 带模板 GUID → 开档脚本级失败；versions 带模板 GUID → 与 moniker 链断裂 | 写回时替换两份文件中的 GUID |
| 4 | **SAB body/face/edge token#1 = 文档级实体序号**：官方 box 体=0、面=1..6、边=7..18；cyl 体=19、面=20..22、边=23..25（每 part 体→面→边，跨 part 连续） | 我们全 0/-1 也开档成功（v26 实测），但官方布局即此；补齐零风险且字段级对齐 | `sab_emit` 新增 `_SeqCounter`，`write_scdoc_multi` 跨 part 共享 |
| 5 | **柱面 part 文档与 SAB 边数一致**：SAB 发 3 边（两圆 + seam），document.xml 只写 2 条 NominalEdgeDef | 文档缺 `0:111` 边定义 | 边计数按类型修正（cyl=3/sphere=1/torus=2） |
| 6 | **ComponentDef 编号避让面/边 id**：官方首组件编号 0:27 恰与我们体 part 面 id 0:27 撞号 → 该组件静默丢失（症状 3） | v15/v16 单侧交换定位：我们的 box 侧组件死亡、官方侧全活 | 组件编号专用区间 `200+i`，与 22+60n 体体系永不交叉 |

### 3. document.xml 按官方存档骨架重建

除上述六项，`_assembly_document_xml` 整体重写为官方保存骨架（官方样本逐字段转录）：

- 文档级：`isNotCompletable/loadTime/locked/originalToReplacements…`（实测
  `EncryptedData/importSource` 非必需）；Design 级 `updateState/nextId`；
- PresentationDef：`AttributeTableDef + LayerDef + RootCaptionDef + CaptionDef`
  （官方 `<type version="82">Normal</type>`；旧 `PresentationDef2/SavedViewsDef/
  <type>Mutable</type>` 废弃）；
- DocumentSettingsDef：完整 units + DocumentDetailSettingsDef 逐字段转录；
- rels 增加 `versionHistory` 条目。

### 4. 验证与测试

- **官方 SpaceClaim 2019 R3 哨兵：`done bodies=2`**（root 0 体 + 两组件各 1 体，
  与官方样本同构；part 级面数 box=6 / cyl=3 全部对上）
- 全量测试：**187 passed, 1 skipped**（新增 8 项回归，见下）
- 官方开档端到端测试进入常规套件：`test_official_open_assembly_bodies_two`
  （SpaceClaim 缺失时自动 skip）

### 5. 文件清单

| 文件 | 内容 |
|---|---|
| `scdm/scdoc_write.py` | document.xml 官方骨架重建 + 六项绑定修复 + 共享序号计数器接线 |
| `scdm/sab_emit.py` | `_SeqCounter` + body/face/edge 全部构建器（含数据驱动 layout）序号字段 |
| `tests/test_todo9_assembly.py` | 8 项回归：节键常量/sctype 逐字/GUID 一致性/柱面 3 边/组件编号避让/文档级序号/单体序号/官方开档端到端 |
| `references/verify_open2.py` | part 级富诊断哨兵（逐 part 体数+面数、逐组件 GetBodies） |
| `docs/NYI_INVENTORY.md`、`function_gap_analysis.md` | TODO-9 关闭；§2.7 装配域升级 99%、L2 |

### 6. 诚实遗留 → 本轮三项已闭环

- ~~容器组件 part 未发~~ **已发**：每 kdoc 组件 → 空 PartDef（0:{240+ci}）+ 根
  ComponentDef（0:{260+ci}）+ caption（0:{280+ci}）；官方打开 components=3
  （两体 + 空容器）✅；
- ~~`wstring_attrib` 未复刻~~ **已复刻**：body [XACIS_NAME string, XACIS_ID
  wstring, XSTEP wstring] + lump [%9/%11/%6] + 面/边 [%6 string + %9 wstring]
  + 顶点 [%9] + 环 [常量 '1VFBE']；记录数逐类等于官方样本（box 19/37、cyl
  7/16）；**关键发现：带 wstring 的流必须用官方内核类号表**（shell=10/face=12/
  loop=13/cone=14/surface=15/plane=16/coedge=17/edge=18/vertex=19/ellipse=20/
  curve=21/straight=22/point=23，wstring_attrib=8）——旧 box.scdoc 表（shell=9…）
  与 wstring 混用 → SabSatConverter "Sat file indexing mechanism failed"；
  xacis 模式经 `CID_MAP` 切换，单体路径保持旧表；
- ~~多体 facets.bin 官方布局未复刻~~ **已复刻**：magic+版本+n_bodies+[1,0] →
  逐体段头 [体号,0,updateState,5,面数,0] → 面节点 [面号,0,节点号,角数] + 角×8
  float + [三角数][打包对] + [边界数][打包对] + [边行数][(mesh_id,2k,1)] +
  面间 0 分隔 → 体尾边表 [(mesh_id,0,边号)] → 非末体 [1,0] 终结；mesh_id 全局
  自 8 递增、跨面共享（同 B-rep 边同 id）；平面面全官方结构，曲面面单节点整
  网格（官方侧面节点 84 角同构）；`scdoc_parser/facets.py` 同步升级双格式兼容
  （官方 4 字头 + 旧 5 字头）；box/cyl 单体 + 装配官方打开复验 ✅；
- `_emit_bytes` 身份序重序列化有损（0x0F 嵌套簇不往返）——仍遗留，需字段级
  改 SAB 时先修 token 往返。

---

## 2026-09-06 续 · 三项保真度打磨闭环（容器 part / wstring / 多体 facets）

- **容器组件 part**：官方样本的"空 Assembly1 part + 组件实例"布局复刻——根持
  逐体组件 + 容器组件，容器 part 空体；id 专用区间 240/260/280 与体体系 22+60n
  永不交叉；官方哨兵 components=3、TOTAL=2。
- **wstring_attrib（XACIS 身份链）**：逐实体链结构、0 基链指针（t2=NEXT/
  t3=PREV/t4=OWNER）、名称驻留（首全名后续 %N）全部逐字对齐官方样本；值生成
  '1V' + Crockford-base32（LCG 扩散）+ 60 字符产品号；**官方内核类号表为
  SabSatConverter 硬要求**（见 §6 关键发现），`CID_MAP` 按 xacis 模式切换。
- **多体 facets.bin**：完整官方布局解码（段头/面节点/尾边表/[1,0] 终结/0 分隔/
  mesh_id 共享语义）并重写 `_facets_bytes`；自读解析器双格式兼容；单体 + 装配
  官方打开复验通过。
- 验证：**191 passed, 1 skipped**（+4 回归：容器结构/wstring 链/类号表/单体旧
  布局守夜）；官方 SpaceClaim 哨兵：单体 box bodies=1、cyl bodies=1、
  装配 bodies=2。

---

## 2026-09-05 轮 · 决定性成果：官方打开 0 bodies 问题彻底解决（原生链路，bodies=1）


### 1. 逆向 ACIS 内部保存遍历算法（SpaACIS.dll 反汇编）

真正的内核 DLL 是 **`SpaACIS.dll`**（SpaceClaim 安装目录）。解题链：

1. **PE 导出解析**（`references/disasm/pe_exports.py` + `pdata.py`）：导出表给出每个类的 `save(ENTITY_LIST&)` 地址，`.pdata` 异常目录提供精确函数边界
2. **驱动函数反汇编**（`api_save_entity_list` @0x18116b010 + `save_entity_pointer` @0x1811d4060）：
   ```
   worklist = FIFO 队列（调用者以 BODY 为 seed）
   while worklist 未耗尽:
      e = 出队
      e->save_data(worklist)   # 写记录 + 对每个实体指针字段调 save_entity_pointer
   save_entity_pointer(ent): 首次引用 → 登记新编号并追加队尾；写编号进流
   ```
   **记录编号 = 首次引用时分配；记录字节 = 出队时写入**——FIFO 下二者恒等。
3. **决定性验证**：官方 golden `ref_tet.scdoc` 141 条记录上做 FIFO 模拟，出队序列 == 0..140 **精确一致**（LIFO 反证失败）→ 官方交错序列是**指针字段序的涌现结果**，无任何硬编码模板。

详见 [references/acis_save_algorithm.md](references/acis_save_algorithm.md)。

### 2. 原生 SAB 发射器（scdm/sab_emit.py）

`Worklist` 类 = 算法直译；`Makers` = 按实体 key 提供记录模板（全部字段布局抄官方流）。效果：
- box / cyl / mixed 全部 FIFO 自检通过（tests/test_sab_worklist.py）
- 移除旧 `_BOX_KIND_SEQ` 手工模板与 `_reorder_to_template` 二次重排
- `scdoc_write._build_sab` 委托（旧静态实现删除）

### 3. 官方打开链路的四个前置条件（本轮逐一定位）

| # | 条件 | 证据 |
|---|---|---|
| 1 | FIFO 遍历序（见上） | 141 记录精确重现 |
| 2 | **XACIS 名字字符串驻留**：attrib name_tag 首个全名 `ATTRIB_XACIS_NAME%6`、后续 `%6` | 全名版 SabSatConverter 报 `Sat file indexing mechanism failed`；驻留版恢复成功 |
| 3 | **document.xml 与 SAB attrib Id 体系一致**：模板包 `NominalBodyDef 0:23` / faces `0:27..` / edges `0:45..` 须匹配 SAB string_attrib 值（box.scdoc 模板 0:23 体系 ✓；ref_tet 0:22 体系 ✗ 0 bodies） | 0:23 模板 + 我们 SAB → bodies=1 |
| 4 | 面定向 flag：我们 loop 逆时针，face 记录首 flag = **flag_b（forward）**；官方 box 交替只是其 loop 走向不同 | face_metrics 语义 + converver 版全 flag_b 对照 |

外加：facets.bin 必须存在且与 SAB 面序一致（模板自带 facets 不匹配时也导致 facet 校验失败——已改为**始终生成与 SAB 一致的 facets**；顺带修复 `_facets_bytes` 边界边映射 bug：mid/doc_num 用边序号而非顶点号）。

### 4. 最终验证

- **官方 SpaceClaim 打开：`done bodies=1`** ✅（references/verify_open.py 哨兵）
- 本机全量测试：**92 passed, 1 skipped** ✅
- 原生 box（10mm）自读：体积/面数/度数全部校验通过

### 5. 文件清单

| 文件 | 内容 |
|---|---|
| `scdm/sab_emit.py` | FIFO 工作清单发射器（核心交付） |
| `scdm/scdoc_write.py` | `_build_sab` 委托 + 模板包策略 + facets 始终生成 |
| `references/disasm/pe_exports.py` `pdata.py` | PE 导出/函数边界解析 |
| `references/disasm/verify_sab_order.py` | FIFO 算法机器验证 |
| `references/disasm/{bisect_kinds,record_swap,reserialize,hybrid_native_golden}.py` | 二分/消融诊断链 |
| `references/acis_save_algorithm.md` | 算法结论文档 |
| `tests/test_sab_worklist.py` | 回归测试（box/cyl/mixed FIFO + roundtrip） |

### 遗留

- 纯 cyl 原生路径的官方打开（coedge/环序 与官方 cyl 参照的差异）——测试覆盖（FIFO 自检 + 自读网格回退），官方验证留作后续
- SabSatConverter 中转方案保留为备选（SAT 路径仍可用）
