# 改进点优先级盘点

> **最新刷新：2026-09-06（P0-2 闭环 + 环境解锁）**
> 依据：工作区代码实测 + `DEV_PLAN.md` §19/§20/§21 + `function_gap_analysis.md`
> + `docs/NYI_INVENTORY.md` + `DEV_SUMMARY.md`。
>
> 口径：只列**能改变产品可用性或结论可信度**的项；纯研究型、边界项（NYI-1~6）不重复列入。
> 每项带「证据指针 / 价值 / 成本 / 验收」，按 ROI 降序，可直接当 roadmap 用。

---

## 0. 一句话结论（刷新版）

**TODO-9 已关闭（官方哨兵 `bodies=2`），装配域升到 99%/L2——但这张成绩单是在 2 体样本上取得的。
按 `_assembly_document_xml` 的 id 表达式复算：体数 ≥4 时 `0:202/0:203` 必然撞号（ComponentDef
vs 体 PartDef/BodyDef），官方表现为「组件静默丢失」，正是 TODO-9 阶段定位过的症状 3。这是当前第一优先项。**

排在其后的两项没变：**任意实体存不了原生 .scdoc**（写端几何覆盖），以及**任何结论我无法在本机复跑**
（无依赖声明与锁文件）。三者都属于「功能域百分比测不出来」的类别。

---

## 1. 状态刷新（相对 09-05 那版盘点）

| 上版判断 | 现在 |
| --- | --- |
| P0-1 在途 TODO-9 未提交（440 行） | **已关闭** ✅ 三次提交：`1d3f46f`（六项绑定要求，官方 `bodies=2`）、`1f4288b`（DEV_SUMMARY 攻坚记录）、`a62c6ef`（容器 part / XACIS wstring 链 / 官方多体 facets）。NYI TODO-9、gap §2.7（装配 99%/L2）已同步；根目录 50 个 `_v*.scdoc` 二分产物已清理 |
| 测试 180 条 | **192 条**（新增 `tests/test_todo9_assembly.py` 12 项），lastfailed 空；DEV_SUMMARY 记「191 passed, 1 skipped」 |
| P0-3 环境不可复现 | **未变**——我仍然跑不了测试（无 pythonocc/pytest 环境）。本页所有「实测」均为代码与缓存读取，非执行验证 |
| P1-3 仓库卫生 | 部分缓解：临时 scdoc 已清；仍剩 `_asm.scdoc`/`_t.sab`/`_t.sat`/`_t.scdoc`、`laptop_3d_geom.stp`(1.5MB)+`.x_t`(2.3MB)，`.gitignore` 未扩 |
| 文档漂移 | gap / NYI / DEV_SUMMARY 已同步；**`DEV_PLAN.md` §21.1 仍记「14 页签/125 命令/123 live/99 测试」，且无 TODO-9 记录**（实测 18 页签/144 命令全 live/192 条） |
| 巨型文件 | 未变：`scdm_gui.py` 3987 行、`scdoc_write.py` 1775（`_assembly_document_xml` 383 行且本轮又增）、`sab_emit.py` 1477、`kernel.py` 1468；>150 行函数 10 个 |

---

## 2. P0 · 立即做

### P0-1 ★ ~~装配 document.xml 的 id 分配器（≥4 体必撞号）~~ ✅ 已关闭（2026-09-06）

> `_DocIdAllocator`（官方布局优先 + 冲突避让）落地；`_allocate_assembly_ids`
> 生成文档全局 id plan，由 document.xml / 每 part SAB attribs（Makers.doc_ids）
> / facets.bin / rels 四方共同消费，永不分歧。参数化测试 1..8 体 × {box, cyl}
> 断言全文档 id 唯一 + refId↔PartDef 对应 + 2 体官方编号保持。209 tests。
> 提交 `ae30cd5`。

### P0-1 ★ 原始记录（已解决）

- **证据**：`scdm/scdoc_write.py:1349` `_assembly_document_xml` 用硬编码算术分配 id——
  体 `gi`：part `22+60gi`、body `23+60gi`、faces `27+3k+60gi`、edges `45+3k+60gi`、
  captions `85/86+60gi`；组件 `200+gi`；容器 part/组件/caption `240/260/280+ci`。
  `write_scdoc_multi`(:1225) 每体一组 ⇒ **组件数 == 体数**。
- **复算结果**（按上述表达式穷举，box 6面/12边 与 cyl 3面/3边 两种体都算）：

  | 体数 | 冲突 |
  | --- | --- |
  | 2 / 3 | 无 |
  | **4** | `0:202` PartDef(体3) = ComponentDef(组2)；`0:203` BodyDef(体3) = ComponentDef(组3)；`0:240` Edge(体3) = ContainerPart（box 型体） |
  | 8 | 再加 `0:205/206/207` Caption/Face(体2/3) = ComponentDef(组5/6/7) |

  `202/203` 两处**与体类型无关（无条件触发）**；`240` 在体 3 边数 ≥6 时触发。
- **为何关键**：DEV_SUMMARY §2-6 与「续」节断言「组件编号专用区间 `200+i` 与 `22+60n`
  体体系**永不交叉**」「240/260/280 永不交叉」——**该断言只在体数 ≤3 时成立**。
  而 TODO-9 定位的「症状 3：组件静默丢失」正是 id 撞号的表现，官方读者不报错、只悄悄丢组件。
  现有回归 `test_component_ids_outside_body_part_id_ranges` 只对 2 体装置断言，测不出。
- **动作**：三处硬编码算术换成**单调 id 分配器**（区段预留 + 顺序发放，或按体数动态抬高组件
  区段基线）；补**参数化**测试：体数 1..8 × {box, cyl} 断言全文档 id 唯一；
  再在 SpaceClaim 内建一个 **4 体官方样本**（一次性人工）跑 `verify_open2.py`，
  期望 `components=4`、`TOTAL=4`。
- **成本**：0.5–1 天（+ 官方样本 0.5 天人工）
- **验收**：4/6/8 体装配结构级无撞号；官方打开 components 与 TOTAL 与体数一致。

### P0-2 · 原生 .scdoc 写出的几何覆盖兜底 ✅ 已关闭（2026-09-06）

> 触发率实测：**3/3 全通过**（倒圆盒 / 打孔盒 / 圆锥台各写 .scdoc 成功，
> `tools/_p02_e2e.py` 临时探针）。兜底代码已在位：`_extract_solid` 的
> `ConvertToBSpline` 预处理 + `_bsurface_data` 的 `GeomConvert_ApproxSurface`
> 逼近（tol=bbox 对角线 1e-6 量级）；仅 IMPROVEMENT_PRIORITIES 未记录（文档滞后）。
> 收尾动作（本批）：①三条回归（tests/test_p02_coverage.py ×4，含
> DeprecationWarning 断言）②DeprecationWarning 修复（shapecustom 实例
> 访问器 → 静态方法）③**.sat 降级路径**：GUI `.scdoc` 保存失败自动写
> `.sat` 并明确提示（不丢几何）。
> 环境注（P0-3 关联）：`scdm` / `occ` conda env 均有 OCC+pytest——全量
> **212 passed / 1 skipped**；唯一失败 `test_todo9_assembly::test_official_open_assembly_bodies_two`
> 为官方 SpaceClaim `/RunScript` 哨兵超时（外部应用依赖），非代码回归。


- **证据**：`write_scdoc`(:1685) 分派 `_cyl_info`（要求恰好 3 面）→ `_sphere_info`（1 面）
  → `_torus_info`（1 面）→ `_extract_solid`(:302)；后者对非平面面走 `_bsurface_data`(:246)，
  而它**只接受原生 `GeomAbs_BSplineSurface`**（:257），否则 :348
  `raise ValueError("仅支持平面/双样条面的实体写出")`；全文件无 `GeomConvert` 逼近兜底
  （09-06 三次提交未触碰此路径，已复核）。
- **后果**：倒圆/倒角/打孔/锥台等含**解析**圆柱·锥·球面的体存 .scdoc 直接失败；
  `scdm_gui.py:681` 仅状态栏提示，**无 SAT/STEP 降级**。装配链路越完整，这个缺口越显眼——
  用户能把两体装配存成官方可开文件，却存不了一个带倒圆的零件。
- **动作**：①先做 10 分钟触发率实测（倒圆盒 / 打孔盒 / 圆锥台各存一次）；
  ②`_bsurface_data` 前加 `GeomConvert_ApproxSurface` 转 `Geom_BSplineSurface`
  （容差取体包围盒对角线 1e-6 量级），失败再抛；③保存失败自动降级 `.sat` 并明确提示。
- **成本**：1–2 天 + 降级 0.5 天
- **验收**：任意 OCCT 实体可存 .scdoc，或明确降级且不丢用户工作；三条新回归（倒圆/孔/锥）。

### P0-3 · 环境与门禁可复现（未变）

- 无 `requirements.txt` / `pyproject.toml` / 锁文件 / CI；历史跑出 192 条用例的
  cpython-311/312 + pythonocc 环境不可定位；本机 3.13/3.14 均无 OCC 与 pytest。
  `tests/` 20 处依赖 ANSYS / SabSatConverter / RunScript。
- **动作**：钉依赖版本 → `conftest.py` 按能力 skip（OCC / PyQt5 / SabSatConverter /
  SpaceClaim 四档）→ 官方门禁统一 `@pytest.mark.official` → CI 跑 `-m "not official"`。
- **成本**：0.5–1 天｜**验收**：克隆后两条命令跑通非官方门禁；官方门禁有独立入口与说明。

---

## 3. P1 · 护栏

| # | 项 | 证据 / 动作 | 成本 |
| --- | --- | --- | --- |
| P1-1 | **自写自读元数据闭环** | NYI TODO-6（NamedSelection 写端未生成）、TODO-7（写端已生成 `SavedViewsDef`，读端 `scdoc_parser/document.py` 未还原）→ 自己存的文件回读丢元数据 | 2–3 天 |
| P1-2 | **端到端任务门禁** | `tests/` 20 个文件全按模块切分，无跨模块任务链；DEV_PLAN §20.8 的演练路径未自动化。P0-2 这类「每个功能都在、串起来走不通」的缺口只有 e2e 能测出 | 1 天 |
| P1-3 | **CID_MAP 全局可变状态显式化** | `sab_emit.py:80` 模块级 `CID_MAP`，由 `Makers.__init__`(:244) 按 `xacis` 赋值，`_cid()` 在**序列化时**读全局。当前「构造即发射」顺序正确（`build_sab_for` 内构造→`wl.run`），所以没炸——但契约是隐式的：一旦有人先构造多个 Makers 再统一序列化、或复用/缓存 Makers，就会静默用错类号表（SabSatConverter indexing failed）。改为显式传参或 contextmanager + 两条断言测试 | 0.5 天 |
| P1-4 | **DEV_PLAN 同步** | §21.1 仍是旧快照（14 页签/125 命令/123 live/99 测试），且无 TODO-9 与保真度记录；补 §21.7，并把「页签/命令/live/测试数」改为自动生成块 | 0.5 天 |
| P1-5 | **已知遗留落表** | DEV_SUMMARY §6：`_emit_bytes` 身份序重序列化有损（0x0F 嵌套簇不往返）——字段级改 SAB 前必须先修。另：`tests/test_sab_worklist.py` 的 FIFO 惰性播种改动**仍未提交** | 0.5 天 |
| P1-6 | **仓库卫生收尾** | `.gitignore` 扩 `_*` 产物族；清理 `_asm.scdoc`/`_t.*`；`laptop_3d_geom.{stp,x_t}`（3.8MB）迁 `references/` | 0.5 天 |

---

## 4. P2 · 域纵深（沿用 NYI 暂缓项）

| # | 项 | 现状 → 目标 | 成本 |
| --- | --- | --- | --- |
| P2-1 | 钣金多弯连续展开 + 折弯槽口（TODO-2/3） | `unfold` 单弯精确；多弯链与 bend relief 未做。85% → 95% | 2–5 天 |
| P2-2 | 曲面圆角面 / 曲线网络（TODO-4） | `blend_loft` 已覆盖双线框过渡；缺多约束 `BRepFill_Filling` 与 face-face blend | 3–5 天 |
| P2-3 | 工程图图幅版式（TODO-5） | HLR 三视图 + BOM/尺寸已有；缺 A0–E 图框（官方 `Library/DrawingFormats` 有样本） | 3–5 天 |

## 5. P3 · 持续复利

巨型文件拆分（`scdm_gui.py` 3987 / `scdoc_write.py` 1775 / `sab_emit.py` 1477 /
`kernel.py` 1468；>150 行函数 10 个）——**只在下次触碰某文件时顺带拆**。
`scdoc_write.py` 拆出 `scdoc_asm_xml.py` 与本轮 P0-1 的 id 分配器天然同批，不单独立项。

---

## 6. 建议执行顺序

1. **P0-1** 装配 id 分配器 + 参数化唯一性测试（0.5–1 天）——成绩单刚拿到，先把它的适用边界
   从 2 体扩到 N 体，否则下一次真实装配会撞同一个坑；
2. ~~P0-2 触发率实测 + 兜底 + 保存降级（1.5–2.5 天）~~ **已闭环**（2026-09-06 见 §2）；
3. **P0-3** 环境与门禁（0.5–1 天）——此后每条结论都可复核；
4. **P1-2 e2e + P1-3 CID_MAP + P1-4/5/6**（合计 ~3 天）；
5. **P1-1 元数据闭环** → **P2-1/2/3** 域纵深；**P3** 随改动自然消化。

纪律沿用 `function_gap_analysis.md` §5：无官方哨兵不宣称「官方打开」；边界项先入册
`docs/NYI_INVENTORY.md` 再从完整度口径剔除；测试非全绿不关账。

**本轮新增一条纪律**：「永不交叉」这类绝对断言必须配**参数化扫描测试**（体数 1..8）。
2 体样本验证过的机制，不等于 N 体成立。
