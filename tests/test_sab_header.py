"""P0 regression: sab_emit._rec_header must survive the optional-cid contract.

The function was defined twice (the later shadowed the earlier), leaving the
cid-is-None branch dead. One definition is now removed; this locks both paths."""
from __future__ import annotations

from scdm.sab_emit import T_CHAIN, T_RECORD, _rec_header


def test_rec_header_with_class_id():
    seen = {}
    out = _rec_header("shell", 10, seen)
    assert out[0] == T_RECORD
    assert seen == {"shell": 10}
    # second time: interned short form = kind + hdrlen(5) + T_ID + 4-byte id
    again = _rec_header("shell", 10, seen)
    assert len(again) == 7 and again[0] == T_RECORD
    assert again[1] == 5
    # chain kind is preserved
    assert _rec_header("spline", 21, {}, kind=T_CHAIN)[0] == T_CHAIN


def test_rec_header_without_class_id():
    """cid=None means `no class id`: must not raise and must not intern."""
    seen = {}
    out = _rec_header("plain", None, seen)
    assert out[0] == T_RECORD
    assert b"plain" in out
    assert seen == {}            # nothing to intern without a class id
    assert len(out) == len(_rec_header("plain", None, None))
