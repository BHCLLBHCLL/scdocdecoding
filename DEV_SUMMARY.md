# DEV_SUMMARY — 本轮攻坚记录

## 🏆 决定性成果：官方打开 0 bodies 问题彻底解决（原生链路，bodies=1）

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
