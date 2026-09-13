"""P283/R51: beam family - 6 sections, closed-form area/inertia, extremes.

The closed forms live in scdm/beams.py; here they are checked against the
kernel's own mass properties (surface props of the section face and volume
props of the solid), which is what makes "the section is exactly what the
formula says" a decision instead of a claim.
"""
from __future__ import annotations

import math

import pytest

pytest.importorskip("OCC")

from scdm import beams as B  # noqa: E402
from scdm import kernel as K  # noqa: E402

L = 0.2


def _mm(key, scale=1000.0):
    return {k: v / scale for k, v in B.DEFAULTS[key].items()}


def _eigvals_sym3(m):
    """Eigenvalues of a symmetric 3x3 matrix, closed form (trigonometric).

    numpy's LAPACK path (eigvalsh) crashes in this environment, and the closed
    form keeps the frame-invariance assertion self-contained anyway.
    """
    a00, a01, a02 = m[0]
    a10, a11, a12 = m[1]
    a20, a21, a22 = m[2]
    q = (a00 + a11 + a22) / 3.0
    p1 = a01 * a01 + a02 * a02 + a12 * a12
    p2 = ((a00 - q) ** 2 + (a11 - q) ** 2 + (a22 - q) ** 2 + 2.0 * p1)
    p = math.sqrt(p2 / 6.0)
    if p < 1e-30:
        return [q, q, q]
    b = [[(m[i][j] - (q if i == j else 0.0)) / p for j in range(3)]
         for i in range(3)]
    det = (b[0][0] * (b[1][1] * b[2][2] - b[1][2] * b[2][1])
           - b[0][1] * (b[1][0] * b[2][2] - b[1][2] * b[2][0])
           + b[0][2] * (b[1][0] * b[2][1] - b[1][1] * b[2][0]))
    r = max(-1.0, min(1.0, det / 2.0))
    phi = math.acos(r) / 3.0
    e1 = q + 2.0 * p * math.cos(phi)
    e3 = q + 2.0 * p * math.cos(phi + 2.0 * math.pi / 3.0)
    e2 = 3.0 * q - e1 - e3
    return sorted([e1, e2, e3])


def test_p283_six_profiles_match_the_closed_form():
    for key in B.PROFILES:
        d = _mm(key)
        cf = B.closed_form(key, **d)
        face = B.section_face(key, **d)
        sp = K.section_props(face)
        assert sp["area"] == pytest.approx(cf["area"], rel=1e-9), key
        assert sp["ix"] == pytest.approx(cf["ix"], rel=1e-9), key
        assert sp["iy"] == pytest.approx(cf["iy"], rel=1e-9), key
        assert sp["j"] == pytest.approx(cf["j"], rel=1e-9), key
        # raw placement reports the closed-form centroid
        raw = K.section_props(B.section_face(key, center=False, **d))
        assert raw["cx"] == pytest.approx(cf["cx"], abs=1e-12), key
        assert raw["cy"] == pytest.approx(cf["cy"], abs=1e-12), key
        # the solid is the section swept: prismatic mass properties are exact
        shape = B.beam(key, L, **d)
        area = cf["area"]
        assert K.volume(shape) == pytest.approx(area * L, rel=1e-9), key
        inert = K.inertia(shape)
        assert inert["ixx"] == pytest.approx(L * cf["ix"] + area * L ** 3 / 12,
                                             rel=1e-9), key
        assert inert["iyy"] == pytest.approx(L * cf["iy"] + area * L ** 3 / 12,
                                             rel=1e-9), key
        assert inert["izz"] == pytest.approx(L * cf["j"], rel=1e-9), key
        assert abs(inert["cog"][0]) < 1e-12 and abs(inert["cog"][1]) < 1e-12, key
        assert inert["cog"][2] == pytest.approx(L / 2.0, rel=1e-9), key


def test_p283_beam_along_a_slanted_segment_is_frame_invariant():
    d = _mm("i")
    cf = B.closed_form("i", **d)
    p0, p1 = (0.01, 0.02, 0.03), (0.05, 0.06, 0.09)
    seg = math.dist(p0, p1)
    shape = B.beam_along("i", p0, p1, **d)
    area = cf["area"]
    assert K.volume(shape) == pytest.approx(area * seg, rel=1e-9)
    inert = K.inertia(shape)
    for i in range(3):
        assert inert["cog"][i] == pytest.approx((p0[i] + p1[i]) / 2.0, rel=1e-9)
    # the inertia eigenvalues are frame invariant: a rotated beam must show the
    # same three values as the axis-aligned prism formula
    m = [[inert["ixx"], inert["ixy"], inert["ixz"]],
         [inert["ixy"], inert["iyy"], inert["iyz"]],
         [inert["ixz"], inert["iyz"], inert["izz"]]]
    got = _eigvals_sym3(m)
    want = sorted([seg * cf["ix"] + area * seg ** 3 / 12,
                   seg * cf["iy"] + area * seg ** 3 / 12, seg * cf["j"]])
    for g, w in zip(got, want):
        assert g == pytest.approx(w, rel=1e-9)


def test_p283_illegal_sections_and_lengths():
    with pytest.raises(K.KernelError):
        B.beam("i", L, h=-1.0, b=0.05, tw=0.005, tf=0.007)
    with pytest.raises(K.KernelError):        # missing tf
        B.beam("i", L, h=0.1, b=0.05, tw=0.005)
    with pytest.raises(K.KernelError):        # unknown profile
        B.beam("zz", L, b=0.05, h=0.01)
    with pytest.raises(K.KernelError):        # wall = radius: no bore left
        B.beam("pipe", L, d=0.06, t=0.03)
    with pytest.raises(K.KernelError):        # flanges would touch
        B.beam("i", L, h=0.1, b=0.05, tw=0.005, tf=0.05)
    with pytest.raises(K.KernelError):        # web as wide as the flange
        B.beam("i", L, h=0.1, b=0.05, tw=0.05, tf=0.007)
    with pytest.raises(K.KernelError):        # angle leg consumed by thickness
        B.beam("l", L, a=0.05, b=0.05, t=0.05)
    with pytest.raises(K.KernelError):
        B.beam("flat", 0.0, b=0.04, h=0.01)
    with pytest.raises(K.KernelError):
        B.beam_along("flat", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), b=0.04, h=0.01)
    with pytest.raises(K.KernelError):
        B.beam("flat", L, b=0.04, h=0.01, axis=(0.0, 0.0, 0.0))


def test_p283_extreme_sections_are_exact():
    cases = {
        "pipe-thin": ("pipe", {"d": 0.100, "t": 0.002}),      # 2 mm wall
        "i-small": ("i", {"h": 0.020, "b": 0.010, "tw": 0.0015, "tf": 0.002}),
        "flat-strip": ("flat", {"b": 0.100, "h": 0.0005}),    # 0.5 mm strip
        "l-unequal": ("l", {"a": 0.080, "b": 0.040, "t": 0.004}),
    }
    for name, (key, d) in cases.items():
        cf = B.closed_form(key, **d)
        shape = B.beam(key, L, **d)
        assert K.volume(shape) == pytest.approx(cf["area"] * L, rel=1e-9), name
        sp = K.section_props(B.section_face(key, **d))
        assert sp["ix"] == pytest.approx(cf["ix"], rel=1e-9), name
        assert sp["iy"] == pytest.approx(cf["iy"], rel=1e-9), name


def test_p283_beam_solids_are_valid_geometry():
    for key in B.PROFILES:
        findings = K.check_geometry(B.beam(key, L, **_mm(key)))
        assert not findings["open_shell"], key
        assert not findings["self_intersecting"], key
        if key in ("rod", "pipe"):
            # check_geometry measures an edge by the chord between the first and
            # last polyline points, which is 0 for a CLOSED circular edge - a
            # curved-edge artefact of that check, not a beam defect
            continue
        assert not findings["short_edges"], key
