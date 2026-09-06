"""P0-1: assembly document id uniqueness (parametrized, N bodies).

The official 60-stride layout collides for >=4 bodies (e.g. body part
0:{22+60*3}=0:202 vs component instance 0:{200+2}=0:202; dense bodies also
collide with container parts 0:{240+ci}).  The allocator must guarantee
document-global uniqueness for any body count / body kind, while keeping
the official numbering for small N.
"""
from __future__ import annotations

import re

import pytest

from scdm.scdoc_write import _allocate_assembly_ids, _assembly_document_xml

# synthetic item tuples: (kind, verts, edges, faces) — only the count
# fields are read by the allocator / document generator
def _box_item():
    verts = [(0, 0, 0)] * 8
    edges = [(0, 1)] * 12
    faces = [{"loop": [0, 1, 2, 3], "normal": (0, 0, 1), "center": (0, 0, 0)}
             for _ in range(6)]
    return ("planar", verts, edges, faces)


def _cyl_item():
    return ("cyl", {"R": 0.003, "h": 0.01})


class _Body:
    def __init__(self, name):
        self.id = name
        self.name = name


class _KDoc:
    def __init__(self, names, n_components):
        self.bodies = [_Body(n) for n in names]
        self.components = [_C("Assembly%d" % (i + 1)) for i in range(n_components)]


class _C:
    def __init__(self, name):
        self.id = name
        self.name = name
        self.visible = True
        self.anchored = False


def _ids_in_xml(xml):
    """All Id="0:N" attribute values in a document.xml."""
    return [int(m) for m in re.findall(r'Id="0:(\d+)"', xml)]


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("kind", ["box", "cyl"])
def test_document_ids_globally_unique(n, kind):
    item = _box_item() if kind == "box" else _cyl_item()
    groups = [("B%d" % i, [item], [(0.7, 0.8, 0.9)]) for i in range(n)]
    kdoc = _KDoc(["B%d" % i for i in range(n)], 1)
    plan = _allocate_assembly_ids(groups, kdoc)
    xml = _assembly_document_xml(kdoc, groups, "asm", ids=plan).decode()

    ids = _ids_in_xml(xml)
    assert len(ids) == len(set(ids)), (
        "duplicate ids for n=%d %s: %s" % (n, kind, [
            i for i in set(ids) if ids.count(i) > 1]))

    # every COMPONENT instance refId must map to an existing body PartDef
    # (the root defaultEdgeTreatment also carries a refId -- to its own
    # DefaultEdgeTreatmentDef 0:13 -- and is not a component reference)
    part_ids = set(plan["part"])
    for cd in re.finditer(r'<ComponentDef[^>]*>.*?</ComponentDef>', xml, re.S):
        ref = re.search(r'refId="[^":]+:(\d+)"', cd.group(0))
        assert ref, "ComponentDef without source refId"
        assert int(ref.group(1)) in part_ids, (n, kind, ref.group(1))

    # NominalBodyDef ids must match the per-part SAB body attrib ids
    for gi, bid in enumerate(plan["body"]):
        assert ('Id="0:%d"' % bid) in xml
    assert xml.count("<NominalBodyDef") == n


def test_two_bodies_keep_official_numbering():
    """Small N preserves the golden-sample 60-stride layout exactly."""
    item = _box_item()
    groups = [("B0", [item], [(0.7, 0.8, 0.9)]),
              ("B1", [item], [(0.7, 0.8, 0.9)])]
    kdoc = _KDoc(["B0", "B1"], 1)
    plan = _allocate_assembly_ids(groups, kdoc)
    assert plan["part"] == [22, 82]
    assert plan["body"] == [23, 83]
    assert plan["faces"][0][:3] == [27, 30, 33]
    assert plan["edges"][0][:3] == [45, 48, 51]


def test_four_bodies_no_202_collision():
    """The exact collision from the priorities doc: body part 0:{22+60*3}
    == 0:202 used to equal component instance 0:{200+2}."""
    item = _box_item()
    groups = [("B%d" % i, [item], [(0.7, 0.8, 0.9)]) for i in range(4)]
    kdoc = _KDoc(["B%d" % i for i in range(4)], 1)
    plan = _allocate_assembly_ids(groups, kdoc)
    xml = _assembly_document_xml(kdoc, groups, "asm", ids=plan).decode()
    ids = _ids_in_xml(xml)
    assert len(ids) == len(set(ids))
    # and the plan must not hand the same number to a part and a component
    assert not (set(plan["part"]) & set(plan["comp"]))
    assert not (set(plan["body"]) & set(plan["comp"]))
    assert not (set(plan["part"]) & set(plan["cont_part"]))
