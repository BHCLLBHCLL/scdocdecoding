# ACIS SAB 内部保存遍历算法（逆向结论）

## 结论一句话

`api_save_entity_list` 维护一个 **FIFO 工作清单（ENTITY_LIST）**：seed 实体（BODY）入队后，逐条出队写出记录，出队时把该记录引用的、尚未登记的全部实体追加到队尾（首次引用即分配记录编号）。**记录写入顺序 = 编号顺序 = 出队顺序**，这就是官方 SAB 中"深度交错"序列的来源——没有任何硬编码模板，交错是**指针字段顺序**的涌现结果。

## 证据链

### 1. PE 符号分析（`references/disasm/pe_exports.py`、`pdata.py`）
- 真正内核 DLL = `SpaACIS.dll`（SpaceClaim 安装目录 `C:\Program Files\ANSYS Inc\v195\scdm\`），导出全部类的 `save` 虚方法
- 导出表给出每个 `save` 的实现地址，`.pdata` 异常目录给出精确函数边界
- 反汇编（`references/disasm/*.asm`）确认每个 `save(ENTITY_LIST&)` = `save_begin` → `save_data` → `save_end`

### 2. 驱动函数（`api_save_entity_list` @ 0x18116b010）
```
save_entity_list(file, version, top_entity_list, options):
    worklist = top_entity_list          # 调用者 seed（通常 [BODY]）
    while worklist 未耗尽:
        e = worklist.pop_front()
        e->save_data(worklist)          # 写记录 + 引用登记
```
核心子函数 `save_entity_pointer(list, ent)`（@0x1811d4060）：
```
idx = ENTITY_LIST.add(ent, append_if_missing)  # 首次引用：登记新编号并入队
stream.write_ptr(idx)                          # 写入引用
```
**编号在"首次引用"时分配，记录在"出队"时写入**——二者在 FIFO 下恒等。

### 3. 决定性验证（`references/disasm/verify_sab_order.py`）
从官方 golden `ref_tet.scdoc` 的 141 条记录提取每条记录的 ptr 引用序列，模拟：
- **FIFO（从记录 0 body 出发，出队时把未登记引用追加队尾）：出队序列 == 0..140 精确一致 ✅**
- LIFO：失败（首个错位在 pop#2）❌

### 4. 各类 save_data 的引用字段顺序（反汇编 + 官方记录交叉验证）
| 类 | 引用顺序（按保存字段序） |
|---|---|
| BODY | attribs(链首) → [self 标记] → lumps → ... |
| LUMP | attribs → shells → body |
| SHELL | attribs → faces(链首) → lump |
| FACE | attribs → next_face → loop → shell → surface |
| LOOP | attribs → 首 coedge → face |
| COEDGE | attribs → next → prev → partner → edge → loop |
| EDGE | attribs → vertex1 → vertex2 → coedge → curve |
| VERTEX | incident_edge → point |
| 几何（plane/straight/point/ellipse/cone） | 无实体引用（叶节点） |

attrib 链走 `save_common`（遍历链头，vtable+0x140 判定可保存性），attrib 记录自身出队时递归登记 NEXT。

## 实现（`scdm/sab_emit.py`）

`Worklist` 类即上述算法的直接移植；`Makers` 按 key 实体（kind, body, ...) 提供每条记录的模板，指针字段经 `wl.ref(key)` 现场登记。官方 box（111 记录）与 converter 输出（111）的 kind 序列、指针角色完全一致。

## 官方打开链路的两个前置条件（本轮额外发现）

单独 FIFO 还不够，官方 SpaceClaim 打开还需要：

1. **XACIS 名字字符串驻留**：attrib 的 name_tag 必须用 ACIS 字符串池缩写——首个 `ATTRIB_XACIS_NAME%6` 全名 + 后续 `%6`；否则 SabSatConverter 报 `Sat file indexing mechanism failed`。
2. **document.xml 与 SAB attrib 值 Id 体系一致**：模板包的 `NominalBodyDef Id="0:23"` / `NominalFaceDef Id="0:27"...` 必须与 SAB 中 `string_attrib` 值 `0:23`/`0:27` 匹配；错位（如模板 0:22 体系配 0:23 SAB）→ 官方打开 bodies=0。

最终验证：原生 emitter 写出的 box（10mm）= **官方 SpaceClaim bodies=1** ✅（`references/verify_open.py` 哨兵 `done bodies=1`）。
