"""P7: drawing increment - projected/section views, dimensions, SVG sheet."""
from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("OCC")

from scdm import drawing as D  # noqa: E402
from scdm import kernel as K  # noqa: E402


def _extent_mm(polys):
    e = D.extents(polys)
    return (e[2] - e[0]) * 1000.0, (e[3] - e[1]) * 1000.0


def test_det_proj_projects_along_a_chosen_direction():
    """det.proj -> a 20mm cube projected along -Z is 20 x 20 mm."""
    name, polys = D.projected_view(K.make_box(0.02, 0.02, 0.02),
                                   (0.0, 0.0, -1.0), label="投影")
    assert name == "投影" and polys
    w, h = _extent_mm(polys)
    assert w == pytest.approx(20.0, abs=1e-6)
    assert h == pytest.approx(20.0, abs=1e-6)
    with pytest.raises(ValueError):
        D.projected_view(K.make_box(0.02, 0.02, 0.02), (0.0, 0.0, 0.0))


def test_det_section_views_the_cut_face():
    """det.section -> mid-plane cut of a 20mm cube is a 20 x 20 mm outline."""
    shape = K.make_box(0.02, 0.02, 0.02)
    name, polys = D.section_view(shape, K.cog(shape), (0.0, 0.0, 1.0),
                                 label="剖视")
    assert name == "剖视" and polys
    w, h = _extent_mm(polys)
    assert w == pytest.approx(20.0, abs=1e-6)
    assert h == pytest.approx(20.0, abs=1e-6)


def test_dimension_notes_report_mm_extents():
    """P7 dimensions -> one width x height note per view, in mm."""
    views = [D.projected_view(K.make_box(0.02, 0.03, 0.02), (0, 0, -1))]
    notes = D.annotate(views)
    assert notes == ["投影: 20.0 x 30.0 mm"], notes
    assert D.annotate([("空", [])]) == ["空: -"]


def test_p48_dimension_drag_changes_only_the_offset():
    """P48: dragging a dimension handle is an offset edit, nothing else.

    The measured value, the measured interval and the body itself must be
    bit-identical afterwards - a dimension is a measurement, not a driver.
    """
    box = K.make_box(0.02, 0.02, 0.02)
    views = [D.projected_view(box, (0.0, 0.0, -1.0), label='前')]
    (d,) = [x for x in D.dimensions_for(views) if x.axis == 'h']
    value, a, b, vol = d.value_mm, d.a, d.b, K.volume(box)

    # the handle sits on the line, so projecting it back is a round trip
    assert d.offset_for_point(d.handle_point()) == pytest.approx(d.offset)
    old = d.offset
    d.drag_by(0.0, 0.005)
    assert d.offset == pytest.approx(old + 0.005)
    assert (d.value_mm, d.a, d.b) == (value, a, b)
    assert K.volume(box) == pytest.approx(vol, rel=0)

    # dragging onto an explicit point, and the minimum clamp
    (hx, hy) = d.handle_point()
    d.drag_to((hx, hy + 0.01))
    assert d.offset == pytest.approx(old + 0.015)
    d.drag_by(0.0, -10.0)
    assert d.offset == pytest.approx(old + 0.015 - 10.0)
    # the clamp is opt-in: a dimension may legitimately sit on either side
    assert d.drag_by(0.0, 10.0, minimum=0.0) >= 0.0


def test_p48_stale_dimension_is_marked_and_drawn_as_warning():
    """P48: a lost edge association marks the dimension stale and the sheet
    prints the value with a question mark instead of a confident number."""
    import re

    box = K.make_box(0.02, 0.02, 0.02)
    edge = K.explore(box, 'edge')[0]
    dim = D.dimension_for_edge(box, edge)
    assert dim is not None and dim.assoc
    _, stale = D.refresh_dimensions(box, [dim])
    assert stale == 0 and dim.stale is False

    # a box far away has no edge near the stored selector -> stale
    other = K.translate(K.make_box(0.02, 0.02, 0.02), (1.0, 0.0, 0.0))
    _, stale = D.refresh_dimensions(other, [dim])
    assert stale == 1 and dim.stale is True

    fd, path = tempfile.mkstemp(suffix='.svg')
    os.close(fd)
    try:
        views = [(dim.view, D.projected_view(box, (0.0, 0.0, -1.0))[1])]
        D.svg_sheet(views, path, dimensions=[dim])
        svg = open(path, encoding='utf-8').read()
        assert '#c60' in svg and '?' in svg
    finally:
        os.unlink(path)

def test_svg_sheet_writes_views_and_dimensions():
    """P7 SVG sheet -> real file with polylines and dimension text."""
    views = D.three_views(K.make_box(0.02, 0.02, 0.02))
    fd, path = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    try:
        D.svg_sheet(views, path, fmt="A4", title="测试图纸")
        text = open(path, encoding="utf-8").read()
    finally:
        os.unlink(path)
    assert text.startswith("<?xml") and "<svg" in text and text.rstrip().endswith("</svg>")
    assert text.count("<polyline") == sum(len(p) for _n, p in views)
    for note in D.annotate(views):
        assert note in text
    assert "测试图纸" in text
    # sheet size follows the format table (A4 = 210 x 297 mm)
    assert 'width="210.000"' in text and 'height="297.000"' in text


def test_svg_sheet_rejects_empty_views():
    with pytest.raises(ValueError):
        D.svg_sheet([("空", [])], os.devnull)

def test_det_dim_objects_carry_mm_values_and_moveable_offsets():
    """det.dim / P17: a dimension object measures in mm and its line can move
    without changing the measured value."""
    views = D.three_views(K.make_box(0.02, 0.03, 0.02))
    dims = D.dimensions_for(views)
    assert len(dims) == 2 * len(views)          # horizontal + vertical per view
    h = [d for d in dims if d.axis == "h"][0]
    assert h.value_mm == pytest.approx(20.0, abs=1e-6)
    # 俯视 is the view that shows the 30mm depth, so its vertical dim is 30
    assert dims[3].axis == "v"
    assert dims[3].value_mm == pytest.approx(30.0, abs=1e-6)

    line0 = h.line()
    h.offset -= 0.01                            # drag the dimension line
    line1 = h.line()
    assert line1[0][1] == pytest.approx(line0[0][1] - 0.01, abs=1e-12)
    assert h.value_mm == pytest.approx(20.0, abs=1e-6)


def test_det_dxf_exports_lines_and_dimension_text():
    """det.dxf: ASCII DXF with one LINE per segment plus dimension TEXT."""
    views = D.three_views(K.make_box(0.02, 0.02, 0.02))
    fd, path = tempfile.mkstemp(suffix=".dxf")
    os.close(fd)
    try:
        D.write_dxf(views, path)
        text = open(path, encoding="utf-8").read()
    finally:
        os.unlink(path)
    assert text.startswith("0\nSECTION")
    assert text.rstrip().endswith("EOF")
    n_seg = sum(len(poly) - 1 for _n, polys in views for poly in polys)
    n_dim = 2 * len(views)
    assert text.count("\nLINE\n") == n_seg + n_dim
    assert text.count("\nTEXT\n") == n_dim
    assert "20.0" in text


def test_svg_sheet_draws_dimension_objects():
    """P17: the SVG sheet also renders the dimension lines and values."""
    views = [D.projected_view(K.make_box(0.02, 0.02, 0.02), (0, 0, -1))]
    fd, path = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    try:
        D.svg_sheet(views, path, dimensions=True)
        text = open(path, encoding="utf-8").read()
    finally:
        os.unlink(path)
    assert 'class="dim"' in text
    assert ">20.0<" in text

def _top_x_edge(shape):
    """The 20mm edge on the top face running along +X (test fixture)."""
    for e in K.explore(shape, "edge"):
        vs = K.explore(e, "vertex")
        if len(vs) != 2:
            continue
        a, b = K.vertex_point(vs[0]), K.vertex_point(vs[1])
        if (abs(a[2] - 0.02) < 1e-9 and abs(b[2] - 0.02) < 1e-9
                and abs(b[1] - a[1]) < 1e-9 and abs(b[0] - a[0]) > 0.019):
            return e
    return None


def test_det_dim_edge_association_tracks_geometry():
    """det.dim / P24: an edge-associated dimension re-measures after an edit."""
    box = K.make_box(0.02, 0.02, 0.02)
    d = D.dimension_for_edge(box, _top_x_edge(box))
    assert d is not None and d.axis == "edge"
    assert d.value_mm == pytest.approx(20.0, rel=1e-6)
    assert d.assoc and d.assoc["length"] == pytest.approx(0.02, rel=1e-6)

    # grow +X by 5mm and unify the fused seam: the same edge is now 25mm
    face = [f for f in K.explore(box, "face")
            if abs(K.face_normal_center(f)[1][0] - 0.02) < 1e-9][0]
    grown = K.unify_same_domain(K.pull_face(box, face, 0.005))
    dims, stale = D.refresh_dimensions(grown, [d])
    assert stale == 0
    assert d.value_mm == pytest.approx(25.0, rel=1e-6)


def test_det_dim_edge_association_reports_stale():
    """P24: when the edge is gone the dimension is flagged, not silently wrong."""
    box = K.make_box(0.02, 0.02, 0.02)
    d = D.dimension_for_edge(box, _top_x_edge(box))
    far = K.translate(box, (0.5, 0.5, 0.5))
    dims, stale = D.refresh_dimensions(far, [d])
    assert stale == 1
    assert d.value_mm == pytest.approx(20.0, rel=1e-6)   # unchanged, not bogus


def test_dimension_edge_line_moves_with_offset():
    """P24: dragging the dimension line (offset) never changes the value."""
    box = K.make_box(0.02, 0.02, 0.02)
    d = D.dimension_for_edge(box, _top_x_edge(box))
    line0 = d.line()
    d.offset += 0.005
    line1 = d.line()
    assert line1[0][0] != line0[0][0] or line1[0][1] != line0[0][1]
    assert d.value_mm == pytest.approx(20.0, rel=1e-6)
