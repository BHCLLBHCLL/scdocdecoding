# 界面参考图（R123/C-8）

这两张图由 `tools/gui_screenshot.py` 生成，用来对照「界面到底长什么样」——
文本报告能说明行为，但说明不了布局。**GUI 改动后请重新生成并提交**，否则图会过期。

| 文件 | 场景 | 看什么 |
| --- | --- | --- |
| `sketch_diagnostics.png` | `--demo conflict` | 草图模式页签；结构树里的「引用体检：N 条（双击定位）」；模式条「自由度 0 · 冗余 2 · 冲突 #5、#7 · 悬空 1」；视口里的红色冲突标记 |
| `reference_health.png` | `--demo mate` | 设计页签；两个实体与组件 C1；配合指向已删除组件后的体检结果；命名选择「底面」 |

重新生成（在仓库根目录，Windows / conda `occ` 环境）：

```
python tools/gui_screenshot.py --out docs/screenshots/sketch_diagnostics.png \
    --demo conflict --size 1500x950
python tools/gui_screenshot.py --out docs/screenshots/reference_health.png \
    --demo mate --size 1500x950
```

注意：**3D 视口是 GL 表面，Qt 的 `grab()` 抓不到**。工具会从 VTK 渲染窗口取像素再合成进
窗口截图；如果没有原生平台（离屏），视口会是空的，工具会如实报 `3d=False`。

可用场景：`solid`（只开文档）、`sketch`（冗余+悬空）、`picks`（选中一个实体）、
`conflict`（冲突+冗余+悬空齐备）、`mate`（配合悬空）。
