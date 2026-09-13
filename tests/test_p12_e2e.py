"""P1-2: end-to-end task-chain gate — DEV_PLAN §20.8 演练路径自动化。

Chain: 新建 → 草图画矩形 → 拉伸 → 抽壳 → 阵列 → 截面检查 → 命名选择
→ 存 .scdm → 重开 → 体积校验。  All steps are real kernel calls, not
mocks; the assertion is quantitative (volume survives the round-trip)."""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import kernel as K  # noqa: E402
from scdm import sketch as S  # noqa: E402
from scdm.io_project import load_scdm, save_scdm  # noqa: E402
from scdm.kdoc import KernelDoc  # noqa: E402


def test_full_task_chain_roundtrip():
    # 新建
    doc = KernelDoc()
    # 草图画矩形 (10 x 8 mm) → 拉伸 12 mm
    curves = [("rect", (0.0, 0.0), (0.01, 0.008))]
    solid = S.extrude_sketch(curves, 0.012, "xy")
    v_full = K.volume(solid)
    assert v_full == pytest.approx(0.01 * 0.008 * 0.012, rel=1e-9)
    # 抽壳 (1 mm wall, open top face)
    shell = K.shell_solid(solid, 0.001, opening_faces=[])
    assert K.volume(shell) < v_full
    # 阵列 (linear, 2 copies spaced 15 mm along X)
    parts = K.pattern_linear(shell, (0.015, 0.0, 0.0), 2)
    assert len(parts) == 2
    # 截面检查 (mid-plane outline is non-empty)
    outline = K.section_outline(shell, (0.005, 0.004, 0.006),
                                (0.0, 0.0, 1.0))
    assert len(outline) >= 1
    # 命名选择 (persisted in the manifest)
    doc.named = [{"name": "外壳", "items": [("body", "b1")]}]
    # 存 .scdm → 重开
    body = doc.add_body(shell, name="外壳")
    body.id = "b1"
    fd, path = tempfile.mkstemp(suffix=".scdm")
    os.close(fd)
    try:
        save_scdm(path, doc)
        doc2 = load_scdm(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    # 体积校验：round-trip 后体积恒等
    assert len(doc2.bodies) == 1
    v2 = K.volume(doc2.bodies[0].shape)
    assert v2 == pytest.approx(K.volume(shell), rel=1e-9)
    # 命名选择随 manifest 往返
    assert doc2.named and doc2.named[0]["name"] == "外壳"


def test_task_chain_script_record_replay():
    """录放链：Recorder 记录 pull -> replay 重放 -> 体积按拉动量增长（§20.8）。

    P0 修复：旧实现用 {"op": ...} 键（replay 只认 "cmd"）会落到「跳过未知命令」
    分支、且以 or True 收尾，实际从未重放也永不失败；现改为真实 API + 量化体积断言。
    """
    from scdm import scripting as SCR

    doc = KernelDoc()
    box = K.make_box(0.01, 0.01, 0.01)
    body = doc.add_body(box, name="S")
    v0 = K.volume(body.shape)

    rec = SCR.Recorder()
    rec.start()
    rec.note("tool.pull", target="last", index=0, face_i=0, distance=5.0)
    steps = rec.stop()
    assert steps == [{"cmd": "tool.pull",
                      "opts": {"target": "last", "index": 0,
                               "face_i": 0, "distance": 5.0}}]

    report = SCR.replay(steps, doc)
    assert report == ["OK tool.pull"], report
    v1 = K.volume(doc.bodies[0].shape)
    # 10mm 立方体的 face 0：面积 1e-4 m^2，拉动 5mm => +5e-7 m^3
    assert v1 == pytest.approx(v0 + 0.01 * 0.01 * 0.005, rel=1e-9)
    assert v1 > v0
