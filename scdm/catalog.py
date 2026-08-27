"""Ribbon / backstage command catalog aligned with DEV_PLAN.md."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Command:
    id: str
    name: str
    en: str
    wave: str
    icon: str
    large: bool = False
    checkable: bool = False
    note: str = ""


@dataclass(frozen=True)
class Group:
    name: str
    en: str
    commands: Tuple[Command, ...]


@dataclass(frozen=True)
class Tab:
    id: str
    name: str
    en: str
    groups: Tuple[Group, ...]
    kind: str = "ribbon"  # ribbon | backstage


def C(id, name, en, wave, icon, large=False, checkable=False, note="") -> Command:
    return Command(id, name, en, wave, icon, large, checkable, note)


TABS: Tuple[Tab, ...] = (
    Tab("file", "文件", "File", (), "backstage"),
    Tab("design", "设计", "Design", (
        Group("剪贴板", "Clipboard", (
            C("edit.paste", "粘贴", "Paste", "M2", "paste", large=True),
            C("edit.cut", "剪切", "Cut", "M2", "cut"),
            C("edit.copy", "复制", "Copy", "M2", "copy"),
        )),
        Group("定向", "Orient", (
            C("view.spin", "旋转", "Spin", "M1", "spin"),
            C("view.pan", "平移", "Pan", "M1", "pan"),
            C("view.zoom", "缩放", "Zoom", "M1", "zoom"),
            C("view.fit", "适合", "Fit", "M1", "fit"),
            C("view.prev", "上一视图", "Previous", "M1", "prev"),
            C("view.home", "主视图", "Home", "M1", "home"),
            C("view.iso", "等轴测", "Isometric", "M1", "iso"),
            C("view.pos_x", "右视", "+X", "M1", "viewx"),
            C("view.pos_y", "后视", "+Y", "M1", "viewy"),
            C("view.pos_z", "俯视", "+Z", "M1", "viewz"),
        )),
        Group("草图", "Sketch", (
            C("sketch.line", "直线", "Line", "M3", "line"),
            C("sketch.tangent", "切线", "Tangent", "M3", "tangent"),
            C("sketch.rect", "矩形", "Rectangle", "M3", "rect"),
            C("sketch.rect3", "三点矩形", "3-Pt Rect", "M3", "rect3"),
            C("sketch.circle", "圆", "Circle", "M3", "circle"),
            C("sketch.circle3", "三点圆", "3-Pt Circle", "M3", "circle3"),
            C("sketch.ellipse", "椭圆", "Ellipse", "M3", "ellipse"),
            C("sketch.spline", "样条", "Spline", "M3", "spline"),
            C("sketch.point", "点", "Point", "M3", "point"),
            C("sketch.construction", "构造线", "Construction", "M3", "const"),
            C("sketch.offset", "偏移", "Offset", "M3", "offset"),
            C("sketch.layout", "布局", "Layout", "M3", "layout"),
            C("sketch.grid", "网格", "Grid", "M3", "grid", checkable=True),
        )),
        Group("模式", "Mode", (
            C("mode.sketch", "草图", "Sketch", "M3", "mode_sketch", checkable=True),
            C("mode.section", "截面", "Section", "M2", "mode_section", checkable=True),
            C("mode.3d", "三维", "3D", "M1", "mode_3d", checkable=True),
        )),
        Group("编辑", "Edit", (
            C("tool.select", "选择", "Select", "M1", "select", large=True, checkable=True),
            C("tool.pull", "拉动", "Pull", "M2", "pull", large=True, checkable=True,
              note="挤出/偏移/旋转/扫掠"),
            C("tool.move", "移动", "Move", "M2", "move", large=True, checkable=True),
            C("tool.fill", "填充", "Fill", "M2", "fill", large=True, checkable=True),
            C("tool.replace", "替换", "Replace", "M2", "replace", large=True, checkable=True),
        )),
        Group("相交", "Intersect", (
            C("tool.combine", "合并", "Combine", "M2", "combine", large=True, checkable=True),
            C("tool.split_body", "分割实体", "Split Body", "M2", "split", large=True, checkable=True),
            C("tool.split_faces", "分割面", "Split Faces", "M2", "splitf", checkable=True),
        )),
        Group("约束", "Constraint", (
            C("con.dim", "尺寸", "Dimension", "M3", "dim"),
            C("con.hv", "水平竖直", "H/V", "M3", "hv"),
            C("con.coin", "重合", "Coincident", "M3", "coin"),
            C("con.tan", "相切", "Tangent", "M3", "tan"),
            C("con.eq", "相等", "Equal", "M3", "eq"),
            C("con.par", "平行垂直", "Par/Perp", "M3", "par"),
            C("con.fix", "中点固定", "Mid/Fix", "M3", "fix"),
        )),
        Group("生成", "Create", (
            C("create.pattern", "阵列", "Pattern", "M4", "pattern"),
            C("create.mirror", "镜像", "Mirror", "M4", "mirror"),
            C("create.project", "投影", "Project", "M3", "project"),
            C("create.shell", "抽壳", "Shell", "M4", "shell"),
            C("create.blend", "倒圆", "Blend", "M4", "blend"),
            C("create.chamfer", "倒角", "Chamfer", "M4", "chamfer"),
            C("create.draft", "拔模", "Draft", "M4", "draft"),
            C("create.offset", "偏移面", "Offset Faces", "M2", "offace"),
        )),
        Group("插入", "Insert", (
            C("insert.plane", "平面", "Plane", "M2", "plane"),
            C("insert.origin", "原点", "Origin", "M2", "origin"),
            C("insert.axis", "轴", "Axis", "M2", "axis"),
            C("insert.cyl", "圆柱", "Cylinder", "M2", "cyl", large=True),
            C("insert.sphere", "球", "Sphere", "M2", "sphere", large=True),
            C("insert.helix", "螺旋", "Helix", "M4", "helix"),
            C("insert.component", "组件", "Component", "M4", "comp"),
        )),
    )),
    Tab("display", "显示", "Display", (
        Group("显示", "Show", (
            C("show.faces", "面", "Faces", "M1", "face", checkable=True),
            C("show.edges", "边", "Edges", "M1", "edge", checkable=True),
            C("show.vertices", "顶点", "Vertices", "M1", "vert", checkable=True),
            C("show.planes", "平面", "Planes", "M1", "plane", checkable=True),
            C("show.axes", "轴/原点", "Axes", "M1", "origin", checkable=True),
        )),
        Group("样式", "Style", (
            C("style.shaded_edges", "着色+边", "Shaded+Edges", "M1", "shaded", checkable=True),
            C("style.shaded", "着色", "Shaded", "M1", "shaded2", checkable=True),
            C("style.wire", "线框", "Wireframe", "M1", "wire", checkable=True),
            C("style.transp", "透明", "Transparent", "M1", "transp", checkable=True),
        )),
        Group("图形", "Graphics", (
            C("gfx.silhouette", "轮廓边", "Silhouette", "M2", "sil", checkable=True),
            C("gfx.section", "剖面显示", "Section", "M2", "sect", checkable=True),
        )),
    )),
    Tab("assembly", "组件", "Assembly", (
        Group("组件", "Component", (
            C("asm.insert", "插入组件", "Insert", "M4", "comp"),
            C("asm.create", "创建组件", "Create", "M4", "comp"),
            C("asm.move", "移动组件", "Move", "M4", "move"),
            C("asm.anchor", "锚定", "Anchor", "M4", "fix"),
            C("asm.mate", "配合", "Mate", "M4", "coin"),
            C("asm.explode", "爆炸图", "Explode", "M4", "pattern"),
            C("asm.light", "轻量化", "Lightweight", "M4", "transp"),
        )),
    )),
    Tab("measure", "测量", "Measure", (
        Group("测量", "Measure", (
            C("measure.dist", "测量", "Measure", "M1", "measure", large=True, checkable=True),
            C("measure.mass", "质量属性", "Mass", "M2", "mass", large=True),
            C("measure.interfere", "干涉", "Interference", "M4", "combine"),
        )),
    )),
    Tab("facets", "分面", "Facets", (
        Group("网格", "Mesh", (
            C("facet.reverse", "反转法向", "Reverse", "M5", "rev"),
            C("facet.smooth", "光滑", "Smooth", "M5", "smooth"),
            C("facet.reduce", "简化", "Reduce", "M5", "reduce"),
            C("facet.fill", "填孔", "Fill Hole", "M5", "fill"),
            C("facet.convert", "转为实体", "Convert", "M5", "solid"),
        )),
    )),
    Tab("additive", "增材", "Additive", (
        Group("打印准备", "Print Prep", (
            C("add.build", "构建体", "Build Volume", "M5", "box"),
            C("add.orient", "取向", "Orientation", "M5", "iso"),
            C("add.support", "支撑", "Supports", "M5", "axis"),
            C("add.lattice", "点阵", "Lattice", "M5", "grid"),
        )),
    )),
    Tab("repair", "修复", "Repair", (
        Group("修复", "Repair", (
            C("repair.stitch", "缝合", "Stitch", "M4", "stitch"),
            C("repair.gaps", "间隙", "Gaps", "M4", "gaps"),
            C("repair.missing", "缺失面", "Missing", "M4", "fill"),
            C("repair.extra", "多余边", "Extra Edges", "M4", "edge"),
            C("repair.small", "小面", "Small Faces", "M4", "face"),
            C("repair.solidify", "实体化", "Solidify", "M4", "solid"),
        )),
    )),
    Tab("prepare", "准备", "Prepare", (
        Group("仿真准备", "Sim Prep", (
            C("prep.share", "共享拓扑", "Share", "M5", "stitch"),
            C("prep.enclose", "包围体", "Enclosure", "M5", "box"),
            C("prep.mid", "中面", "Midsurface", "M5", "face"),
            C("prep.small", "小特征", "Defeaturing", "M4", "reduce"),
            C("prep.named", "命名选择", "Named Sel", "M4", "sel"),
        )),
    )),
    Tab("workbench", "Workbench", "Workbench", (
        Group("参数", "Parameters", (
            C("wb.params", "参数", "Parameters", "M5", "dim"),
            C("wb.publish", "发布", "Publish", "M5", "save"),
        )),
    )),
    Tab("detail", "详细", "Detailing", (
        Group("工程图", "Drawing", (
            C("det.view", "视图", "Views", "M5", "iso"),
            C("det.dim", "尺寸", "Dimension", "M5", "dim"),
            C("det.note", "注释", "Note", "M5", "note"),
            C("det.bom", "BOM", "BOM", "M5", "list"),
        )),
    )),
    Tab("safety", "安全", "Safety", (
        Group("附加页", "Add-in", (
            C("safety.tab", "安全模块", "Safety", "M5", "fix",
              note="原安装附加页，保留空壳"),
        )),
    )),
    Tab("tools", "工具", "Tools", (
        Group("工具", "Tools", (
            C("tools.script", "脚本", "Script", "M4", "script"),
            C("tools.record", "录制", "Record", "M4", "rec"),
            C("tools.customize", "自定义", "Customize", "M4", "gear"),
        )),
    )),
    Tab("keyshot", "KeyShot", "KeyShot", (
        Group("渲染", "Render", (
            C("ks.render", "渲染", "Render", "M5", "render",
              note="自有入口，不复制 KeyShot 品牌"),
        )),
    )),
)

BACKSTAGE: Tuple[Command, ...] = (
    C("file.new", "新建", "New", "M1", "new"),
    C("file.open", "打开", "Open", "M1", "open"),
    C("file.recent", "最近文件", "Recent", "M1", "recent"),
    C("file.close", "关闭", "Close", "M1", "close"),
    C("file.save", "保存", "Save", "M2", "save"),
    C("file.save_as", "另存为", "Save As", "M2", "saveas"),
    C("file.recover", "恢复", "Recover", "M4", "recover"),
    C("file.print", "打印", "Print", "M4", "print"),
    C("file.image", "导出图像", "Image", "M1", "image"),
    C("file.export", "导出几何", "Export", "M2", "export"),
    C("file.options", "选项", "Options", "M1", "gear"),
    C("file.exit", "退出", "Exit", "M1", "exit"),
)

QAT: Tuple[Command, ...] = (
    C("file.new", "新建", "New", "M1", "new"),
    C("file.open", "打开", "Open", "M1", "open"),
    C("file.save", "保存", "Save", "M2", "save"),
    C("edit.undo", "撤销", "Undo", "M2", "undo"),
    C("edit.redo", "重做", "Redo", "M2", "redo"),
)

# M1 handlers that actually run (others announce their wave).
M1_LIVE = {
    "file.new", "file.open", "file.recent", "file.close", "file.image",
    "file.options", "file.exit",
    "view.spin", "view.pan", "view.zoom", "view.fit", "view.prev",
    "view.home", "view.iso", "view.pos_x", "view.pos_y", "view.pos_z",
    "mode.3d", "tool.select",
    "show.faces", "show.edges", "show.vertices", "show.planes", "show.axes",
    "style.shaded_edges", "style.shaded", "style.wire", "style.transp",
    "measure.dist",
}

M2_LIVE = {
    "file.save", "file.save_as", "file.export",
    "edit.undo", "edit.redo", "edit.copy", "edit.cut", "edit.paste",
    "tool.pull", "tool.move", "tool.fill", "tool.replace",
    "tool.combine", "tool.split_body", "tool.split_faces",
    "insert.cyl", "insert.sphere", "insert.plane", "insert.origin", "insert.axis",
    "create.offset", "mode.section",
    "measure.mass",
}

M3_LIVE = {
    "mode.sketch",
    "sketch.line", "sketch.rect", "sketch.circle", "sketch.point",
    "sketch.grid", "create.project",
    "con.dim", "con.hv", "con.coin", "con.perp",
    "con.eq", "con.par", "con.tan", "con.mid", "con.fix",
}

M4_LIVE = {
    "create.pattern", "create.mirror", "create.shell", "create.blend",
    "create.chamfer", "create.draft", "insert.helix",
    "repair.stitch", "repair.solidify", "repair.gaps", "repair.missing",
    "repair.extra", "repair.small",
    "measure.interfere", "prep.named",
    "asm.insert", "asm.create", "asm.move", "asm.anchor", "asm.mate",
    "asm.explode", "asm.light",
    "tools.script", "tools.record", "tools.customize",
}

M5_LIVE = {
    "file.print",
    "facet.reverse", "facet.smooth", "facet.reduce", "facet.fill", "facet.convert",
    "wb.params", "wb.publish",
    "add.build", "add.orient", "add.support", "add.lattice",
    "det.view", "det.dim", "det.note", "det.bom",
    "ks.render",
}


def live_commands():
    s = set(M1_LIVE)
    try:
        from scdm.kernel import available
        if available():
            s |= M2_LIVE | M3_LIVE | M4_LIVE | M5_LIVE
    except Exception:
        pass
    return s


def command_by_id(cmd_id: str) -> Optional[Command]:
    for c in BACKSTAGE + QAT:
        if c.id == cmd_id:
            return c
    for tab in TABS:
        for g in tab.groups:
            for c in g.commands:
                if c.id == cmd_id:
                    return c
    return None


def all_commands() -> List[Command]:
    out: List[Command] = []
    seen = set()
    for c in list(BACKSTAGE) + list(QAT):
        if c.id not in seen:
            out.append(c)
            seen.add(c.id)
    for tab in TABS:
        for g in tab.groups:
            for c in g.commands:
                if c.id not in seen:
                    out.append(c)
                    seen.add(c.id)
    return out
