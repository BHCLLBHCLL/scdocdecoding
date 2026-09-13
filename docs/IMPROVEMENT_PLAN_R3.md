# 改进规划 R3（2026-09-12 立）

> 生成规则：**每完成一轮改进，立即以最新实测重新基线并产出下一轮规划**。本轮（R2 = P9–P12）交付见
> `docs/P0_P8_IMPROVEMENTS_20260912.md` 的 R2 节。
> 规划方法沿用 `docs/CODE_STATE_AUDIT_20260912.md`：先实测取证，再排 ROI，每项带**验收判据**。

---

## 1. R2 结束时的实测基线

| 口径 | 实测值 |
|---|---|
| 命令面 | 17 ribbon 页签（+1 backstage）/ **140 命令** / **154 live**；占位 2（prep.small、safety.tab） |
| 测试 | **321 条** `def test_`（本轮全量 **328 passed / 1 skipped / 7 deselected · 55.3 s**） |
| 官方门禁 | `official_gate` **5 passed**；`official_open` 单体 1 + 装配 1（本轮未重跑装配） |
| 命令级覆盖 | 测试提及 **99/154**；其余在 `tests/test_coverage_ledger.py` 逐条声明理由 |
| 特征历史 | 可重放 op **7 类**（hole/hole_cbore/hole_csink/boss/shell/fillet/chamfer） |
| 文档防漂移 | `gen_devplan_snapshot.py --check` 已可判定 §21.1 是否过期 |

## 2. 本轮新证据（R3 排序依据）

1. **官方库文档加载大面积失败（最高优先）**：`scdm.document.load_scdoc` 对官方 6 个 SrModels
   实测 **5 失败 / 1 通过**（samplemodel6 无几何）：
   - SampleModel1 → `edge table entry not (id,0,doc): (16008, 1, 16052)`
   - SampleModel4 / samplemodel2 / samplemodel3 → `bad body section header`
   - samplemodel5 → `body terminator (1,1) != (1,0)`
   - samplemodel2 的 `facets.bin` 头部字：`[14, 37, 1, 2, 399, 161, 8681, 5, 93, 2, 14089, …]`
   **口径修正**：`references/scan_library.py` 的「6/6」只证明 SAB tokenizer 能解，**不证明文档级
   加载可用**；此前审计报告的 6/6 表述已在 R2 记录中修正。
2. **薄壁圆角可原生崩溃**：1mm 壁厚抽壳体 + 1mm 圆角 → OCCT 访问违例，Python 无法捕获，整个测试
   进程挂掉（R2 实测）。GUI 的 `_fillet_or_chamfer` 固定 1mm，普通用户一键即可能触发。
3. **多实例未落地到文件**：P8 只做了模型/位姿层；`write_scdoc_multi` 仍"一体一 part"。
4. **特征历史覆盖面窄**：7 类 op 可重放，而目录里阵列/镜像/拔模/偏移/合并/分割等编辑命令
   **不进历史**，参数改动后不重建。

---

## 3. R3 工作项（P13–P20，ROI 降序）

### P13 · 官方多体 facets 解析 → 文档级加载 6/6（最高优先）

- **现状**：见 §2-1，5/6 失败；两条现有假设（单流 per-body `[bid,0,upd,5,nface,0]` 与 legacy
  单体布局）都不匹配官方多体流。
- **动作**：①以 samplemodel2/5 的 facets.bin 为样本，逐字段确认多体段结构（体段头、面分隔、
  体终止符、边表第二字的真实语义——SampleModel1 显示它不是恒 0）；②修 `scdoc_parser/facets.py`
  的解析分支；③补"官方库 6/6 加载"回归（体数/面数下限对照 SAB 计数）。
- **验收**：`load_scdoc` 对 6 个 SrModels 全通过；samplemodel2 `bodies=37`、samplemodel5
  `bodies=80`；解析耗时有预算（samplemodel2 < 10 s，当前 SAB tokenize 已 3.46 s）。
- **成本**：0.5–1 天（含逆向确认与回归）。

### P14 · 圆角/倒角前置安全校验（防原生崩溃）

- **现状**：见 §2-2；GUI 固定 1mm，薄壁件一键即崩。
- **动作**：调用 `fillet_edges/chamfer_edges` 前做几何预检（最短边/壁厚估计 + `BRepCheck_Analyzer`），
  超限则抛可捕获的 `KernelError` 并给 GUI 明确提示；特征历史重放同样走该预检。
- **验收**：新增测试——1mm 壁厚 + 1mm 圆角被**拒绝**且进程不崩溃；0.25mm 正常通过。
- **成本**：0.5 天。

### P15 · 装配写回多实例（一份 part 定义 + N 个实例）

- **现状**：P8 的 `instances` 只活在内存/KernelDoc；写回仍一体一 part。
- **动作**：`write_scdoc_multi` 支持"定义 part 一份 + N 个 ComponentDef（source refId + trans）"，
  复用 TODO-9 已实证的绑定要求（节键/sctype 逐字/GUID/编号避让）。
- **验收**：`official_open` 新增"1 定义 + 3 实例"用例，官方哨兵 `bodies=3`；自读合并体数=3。
- **成本**：1–1.5 天（含官方哨兵复验，单次 ~2 分钟）。

### P16 · 特征历史扩展 + 特征树 UI

- **现状**：7 类 op；无 UI 呈现。
- **动作**：把 `create.pattern/mirror/draft/offset/tool.combine/tool.split_body` 纳入
  `FeatureStack`（含选择器/参数持久化）；左栏结构树列出特征节点（可选中、可删除后重建）。
- **验收**：参数改动后"孔+阵列+抽壳"链完整重放（体积闭式断言）；结构树显示 3 个特征节点。
- **成本**：1.5–2 天。

### P17 · 工程图：尺寸对象化 + DXF 输出

- **现状**：尺寸是视图包围盒注记，不可交互、不关联几何。
- **动作**：尺寸对象（关联边/面 + 可拖动 offset）；DXF 写出（工程图与钣金展开共用）。
- **验收**：拖动尺寸不改几何（体积不变）且标注值不变；DXF 可被第三方 CAD 读回（用 OCCT 读回自检）。
- **成本**：2 天。

### P18 · 钣金：闭口卷边 + 展开图输出

- **现状**：只有开口卷边（回卷法兰与平板留 2r 间隙）；无展开图文件输出。
- **动作**：闭口（压死）卷边几何；展开轮廓导出（SVG/DXF，复用 P17 的 DXF 写出）。
- **验收**：闭口卷边体积 = `(l1+hl)·w·t`（无弧段，rel 1e-9）；展开图轮廓面积 = 展开长×宽（rel 1e-6）。
- **成本**：1 天。

### P19 · 草图/交互补盲（曲线编辑 + 约束可视化 + 重合捕捉）

- **现状**：圆/椭圆/样条已可拉伸（R2/P10），但无 trim/extend/offset 曲线编辑；约束无符号显示；
  `tool.select` 的"重合"选项仍未消费。
- **动作**：曲线编辑三命令（在草图平面内求解交点/裁剪）；约束符号与尺寸的画布标注；重合捕捉接入 `snap_uv`。
- **验收**：trim 后闭环面积按解析值变化；视口截图（offscreen）断言约束符号 actor 数；重合捕捉单测。
- **成本**：2 天。

### P20 · 口径与文档维护（每轮必做）

- **动作**：①按 R2 后实测重写 `function_gap_analysis.md` 的逐域值（含官方 facets 加载口径修正）；
  ②把 `gen_devplan_snapshot.py --check` 加进 CI（`.github/workflows/ci.yml`）；③把 P13 发现的
  "SAB 可解 ≠ 文档可载"写成回归纪律条目。
- **验收**：CI 中出现 `--check` 步骤；gap 文档逐域值与本报告 §1 基线一致。
- **成本**：0.5 天。

---

## 4. 建议执行顺序与理由

`P13 → P14 → P15 → P16 → P17 → P18 → P19 → P20`

- **P13 第一**：它是"官方库能不能真正读进来"的根问题，且直接决定"官方对齐"口径的可信度（当前
  文档级加载 1/6）；成本最低、证据最全。
- **P14 第二**：原生崩溃是**可用性红线**（用户一点就挂进程），修起来便宜。
- **P15 第三**：兑现 P8 的产品承诺（多实例必须能存回官方可开文件），并为 P16 的特征树提供装配侧基础。
- 其余按 ROI 顺延；P20 每轮收尾执行。

## 5. 纪律（延续既有 + 本轮新增）

1. 无官方哨兵不宣称"官方可开"；无逐字段 diff 不宣称"官方对齐"。
2. **新增**：任何"解析成功率/覆盖率"结论必须写清**口径路径**（SAB tokenizer ≠ 文档加载 ≠ GUI 导入）。
3. **新增**：涉及 OCCT 几何算子的功能，测试必须包含"非法/极端参数"路径，防止原生崩溃逃逸。
4. 每轮结束：全量非官方套件 + `official_gate` 全绿；`--check` 通过；本文件随之刷新为下一轮规划。
