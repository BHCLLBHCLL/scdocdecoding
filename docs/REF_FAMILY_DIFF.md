# ref 族差异表（R72/P358 实测，2026-09-12）

> 本文件回答一个问题：官方库的**唯一未精确族**（ACIS `ref` 间接曲面）到底差在哪、能不能修。
> 表由仪器自动生成、逐项可复算；结论都配**否证**（纪律 86）。机器可读记录：`docs/ref_family_diff.json`。

## 1. 复算命令

```
python tools/ref_family_diff.py --md docs/REF_FAMILY_DIFF_TABLE.md --json docs/ref_family_diff.json
python tools/ref_family_diff.py --faces SampleModel4.scdoc --md <逐面表>
python tools/import_fidelity.py            # 旧口径（体/面计数），未被本表取代
```

`path` 列是**导入器自己的分支标签**，由默认关闭的 `import_sab.trace_faces()` 钩子记录
（一个事实一个来源，纪律 84；关闭时每个面只多一次全局查询，纪律 85）。

## 2. 差异表（六个官方样例全量）

# ref 族差异表（R72/P358 实测）

复算：`python tools/ref_family_diff.py --md docs/REF_FAMILY_DIFF.md`

| 样例 | SAB 体/面 | 导入 体/面 | 重建分支 rebuild/polygons/sampled/none | 自由边/自由环 | ref 面 | ref 分支 | ref 重建/未重建 | 无边界边 | ref 曲线（有载荷/仅 ref） | 非 ref 未重建 | 包围盒丢弃 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `SampleModel1.scdoc` | 1/109 | 1/109 | 44/65/0/0 | 270/84 | 0 | 0/0/0/0 | **0/0** | 0 | 0/0 | 0 | 0 |
| `SampleModel4.scdoc` | 2/177 | 2/143 | 114/6/22/35 | 441/112 | 52 | 0/5/14/33 | **19/33** | 6 | 13/41 | plane=2 | 0 |
| `samplemodel2.scdoc` | 37/1813 | 37/1810 | 971/823/18/1 | 3542/547 | 20 | 0/19/0/1 | **19/1** | 0 | 2/38 | 0 | 3 |
| `samplemodel3.scdoc` | 1/111 | 1/111 | 0/111/0/0 | 0/0 | 0 | 0/0/0/0 | **0/0** | 0 | 0/0 | 0 | 0 |
| `samplemodel5.scdoc` | 80/1288 | 80/1288 | 156/1132/0/0 | 0/0 | 0 | 0/0/0/0 | **0/0** | 0 | 0/0 | 0 | 0 |
| `samplemodel6.scdoc` | 1/28 | 1/28 | 22/6/0/0 | 2/2 | 0 | 0/0/0/0 | **0/0** | 0 | 0/0 | 0 | 0 |

列口径：`重建分支`=`_rebuild_face`（解析曲面/样条）成功 / 边界面多边形 / 环采样 / 失败；
`自由边/自由环`=`TopExp` 邻接面数 < 2 的边数、`ShapeAnalysis_FreeBounds` 的闭合自由环数；
`ref 面`=曲面头拥有 `ref` 载荷的面；`ref 曲线`=**同样的间接引用落在边上**（有可用载荷 / 载荷只有 `ref`）。

## 3. 五条实测结论

1. **ref 族只占 3 个样例**：SampleModel4 52 面、samplemodel2 20 面，其余 4 个样例 0 面（表内 `ref 面` 列）。
   两族的曲面头 `kind` 全是 `spline`，其**唯一**载荷就是 `ref`（逐面表 `载荷` 列 52/52）。
2. **间接引用同时落在曲线上**：SampleModel4 有 54 条边的曲线头引用 `ref`（13 条另有可用载荷、41 条只有 `ref`），
   samplemodel2 40 条（2/38）。这与 R21 "表不在本 part" 的判定一致，但把影响面从"面"扩到"面+边"。
3. **"面数精确"≠"实体封闭"**：SampleModel1 109/109 面精确却有 **270 条自由边 / 84 个自由环**，
   samplemodel2 1810/1813 有 **3542/547**；只有 samplemodel3、samplemodel5 是 0/0。
   原因可数：这两个样例的曲面是按**包围盒裁出的曲面片**（`重建分支` 列），相邻片的边界不是同一条边，缝合接不上。
4. **未重建的 33 个 ref 面连边界都不完整**：6 个面**没有任何边界边**（环里没有 coedge），2 个只有 1 条边，
   其余 25 个 2–8 条边；全部 33 个的最后尝试分支都是 `sampled`。
5. **两条非 ref 未重建面**（SampleModel4 `plane=2`）与 ref 族无关，单独计数、不清零。

## 4. 候选修法与否证（每条都是本轮实测）

| 候选修法 | 否证 | 数字 |
|---|---|---|
| **别名法**：未重建面其实是另一已建面的"同面"，复用其曲面 | 未重建 ref 面的边集合**没有一个**与其他面相同（同模型内按边 idx 集合比对） | 命中 0 / 29（另 6 个无边界） |
| **边界填面**：只用边界曲线 `BRepOffsetAPI_MakeFilling` 补面 | 20 次尝试（边数 ≥ 3 的未重建 ref 面）**全部被拒**：`WireFromList: can't find the next edge`（线框不闭合），接受 0 个 | 接受 0 / 尝试 20 |
| **提高缝合容差**：`sew_bodies(tol)` 1e-7→1e-3 | SampleModel1 自由环 84→**83**、samplemodel6 2→**2**（纹丝不动）；SampleModel4 112→38 但壳数 33→29（悄悄改变实体划分） | 见下 |
| **逐面载荷**：从未重建面自己的曲面头取几何 | 33 个未重建面的曲面头载荷**只有 `ref`**（无 `nubs`/`nurbs`/`exactsur`） | 0 / 33 |

缝合容差扫描（`K.sew_bodies(faces, tol)`，面数不变、壳数与自由环变化）：

| tol | SampleModel1 自由边/环 | SampleModel4 自由边/环（壳） | samplemodel6 |
|---|---|---|---|
| 1e-7（现值） | 270 / 84 | 364 / 69（34 壳） | 2 / 2 |
| 1e-6 | 270 / 84 | 357 / 67（33 壳） | 2 / 2 |
| 1e-5 | 270 / 84 | 355 / 60（34 壳） | 2 / 2 |
| 1e-4 | 270 / 84 | 352 / 56（33 壳） | 2 / 2 |
| 1e-3 | 266 / 83 | 331 / 38（29 壳） | 2 / 2 |

结论：**提高容差不是修法**——1e-3（模型单位下 1 mm）都关不上 SampleModel1 的 84 个环，
而壳数从 34 变 29 说明它在悄悄改变实体划分；默认值保持 1e-7。

## 5. 逐面证据：SampleModel4 的 52 个 ref 面

| 面 | 曲面头 kind | 环 | 边 | 有曲线的边 | 分支 | 建成面 | 多边形 | 采样环 | 最后尝试 | 载荷 |
|---|---|---|---|---|---|---|---|---|---|---|
| 312 | spline | 2 | 3 | 3 | none | 0 | 1 | 0 | sampled | ref |
| 543 | spline | 1 | 5 | 5 | none | 0 | 0 | 0 | sampled | ref |
| 635 | spline | 1 | 4 | 4 | none | 0 | 0 | 0 | sampled | ref |
| 643 | spline | 1 | 8 | 8 | none | 0 | 0 | 0 | sampled | ref |
| 705 | spline | 1 | 4 | 4 | none | 0 | 0 | 0 | sampled | ref |
| 732 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 747 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 802 | spline | 1 | 2 | 2 | none | 0 | 0 | 0 | sampled | ref |
| 805 | spline | 1 | 2 | 2 | none | 0 | 0 | 0 | sampled | ref |
| 816 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 891 | spline | 1 | 2 | 2 | none | 0 | 0 | 0 | sampled | ref |
| 993 | spline | 1 | 8 | 8 | none | 0 | 0 | 0 | sampled | ref |
| 999 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 1050 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 1156 | spline | 1 | 5 | 5 | none | 0 | 0 | 0 | sampled | ref |
| 1177 | spline | 1 | 4 | 4 | none | 0 | 0 | 0 | sampled | ref |
| 1201 | spline | 1 | 4 | 4 | none | 0 | 0 | 0 | sampled | ref |
| 1212 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 1301 | spline | 1 | 2 | 2 | none | 0 | 0 | 0 | sampled | ref |
| 1427 | spline | 2 | 2 | 2 | none | 0 | 1 | 0 | sampled | ref |
| 1480 | spline | 1 | 3 | 3 | none | 0 | 0 | 0 | sampled | ref |
| 1598 | spline | 1 | 5 | 5 | none | 0 | 0 | 0 | sampled | ref |
| 1684 | spline | 2 | 2 | 2 | none | 0 | 1 | 0 | sampled | ref |
| 1900 | spline | 2 | 3 | 3 | none | 0 | 1 | 0 | sampled | ref |
| 2224 | spline | 2 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 2458 | spline | 1 | 1 | 1 | none | 0 | 0 | 0 | sampled | ref |
| 2548 | spline | 2 | 2 | 2 | none | 0 | 0 | 0 | sampled | ref |
| 2707 | spline | 1 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 2738 | spline | 2 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 3300 | spline | 3 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 3490 | spline | 1 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 3629 | spline | 1 | 0 | 0 | none | 0 | 0 | 0 | sampled | ref |
| 3834 | spline | 1 | 1 | 1 | none | 0 | 0 | 0 | sampled | ref |
| 119 | spline | 1 | 6 | 6 | polygons | 1 | 1 | 0 | - | ref |
| 694 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 760 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 878 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 931 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 1761 | spline | 1 | 4 | 4 | polygons | 1 | 1 | 0 | - | ref |
| 1815 | spline | 1 | 6 | 6 | polygons | 1 | 1 | 0 | - | ref |
| 1909 | spline | 2 | 3 | 3 | polygons | 1 | 1 | 0 | - | ref |
| 2293 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 2509 | spline | 1 | 1 | 1 | sampled | 1 | 0 | 1 | - | ref |
| 3182 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 3244 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 3390 | spline | 1 | 1 | 1 | sampled | 1 | 0 | 1 | - | ref |
| 3395 | spline | 1 | 3 | 3 | polygons | 1 | 1 | 1 | - | ref |
| 3429 | spline | 1 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |
| 3599 | spline | 1 | 1 | 1 | sampled | 1 | 0 | 1 | - | ref |
| 3651 | spline | 1 | 1 | 1 | sampled | 1 | 0 | 1 | - | ref |
| 3656 | spline | 1 | 1 | 1 | sampled | 1 | 0 | 1 | - | ref |
| 3949 | spline | 2 | 2 | 2 | sampled | 1 | 0 | 1 | - | ref |

ref 面 52：重建 0 / 多边形 5 / 采样 14 / 未重建 33；包围盒丢弃 0

## 6. 处置结论

- **修不了（本轮）**：33 个未重建 ref 面。三条独立否证（无载荷 / 无完整边界 / 非别名）说明
  "从本 part 的数据补出这些面"没有可行路径；强行用弦线闭合线框再填面＝**编造几何**，不做。
- **已修（本轮）**：产品口径从"一句话警告"升级为**可数四元组**——
  `import_report` 新增 `ref_built` / `ref_unbuilt` / `ref_no_boundary`（`ref_faces` 保留为总数，旧调用不变），
  警告文本改为 `52 个面引用 ACIS ref 间接曲面（该类曲面的数据不在本 part）：其中 19 个仍由边界曲线重建，33 个未能重建（含 6 个无任何边界边）`。
  实测：SampleModel4 = 52/19/33/6，samplemodel2 = 20/19/1/0。
- **登记为后续**：
  P362 **按真实边界裁剪曲面片**（用 `exppc` 精确 pcurve 而不是包围盒裁剪）——直指结论 3 的 270/3542 条自由边，
  这是比 ref 族更大的一笔账；P363 **自由边/未闭合环进导入报告与状态栏**（把本轮仪器变成产品可见指标）。

## 7. 纪律（本轮新增）

86. **"修不了"必须附否证表**：每个想得到的候选修法都要给一次**可复算的实测否证**（命中 0 / 全部拒绝 / 数字不变），
    否则"不能修"只是没试过。R72：三条候选修法全部否证后才写下"修不了"，并把**已修的那一项**（产品口径）与
    未修项分开登记。
