"""ACIS SAB (Standard ACIS Binary) tokenizer for SpaceClaim .scdoc geometry.

Reverse-engineered byte-level format (ACIS 29.0, SpaceClaim v195):

Layout
------
* 16-byte magic            b"ACIS BinaryFileT"
* int32 LE  n              (11 in box.scdoc) + n opaque header bytes
* string  product          e.g. "SpaceClaim"
* string  version          e.g. "ACIS 29.0 NT"
* string  date             e.g. "Mon Aug 24 00:13:12 2026"
* double  x3               tolerances / unit scale (1000.0, 1e-7, ~1e-10)
* flag token 0x0a
* string  product id       long alphanumeric string
* entity records ...       terminated by record "End-of-ACIS-data"

Token stream (inside / between records)
---------------------------------------
0x04 <int32 LE>    integer
0x0c <int32 LE>    integer / pointer value
0x06 <double LE>   double
0x07 <len> <bytes> string (len is one byte)
0x13 <24 bytes>    3 doubles (position / vector)
0x14 <24 bytes>    3 doubles (second flavour, seen on surfaces)
0x0a               flag (also begins a bounding box: two 0x13 vectors)
0x0b               flag
0x15 <int32 LE>    integer (loop flavour)
0x11               record terminator ("*" in SAT)

Entity record header
--------------------
0x0d <hdrlen> <name> [0x25 <int32 LE>]   full record (carries the fields)
0x0e <hdrlen> <name> [0x25 <int32 LE>]   chain header (derived class level,
                                         no fields; the following 0x0d record
                                         completes the entity)
hdrlen == len(name) + (5 if id present else 0); the id-bearing form is
<name> 0x25 <int32>.  "End-of-ACIS-data" carries no id.

Class-name registry (0x25 ids)
------------------------------
The int32 after 0x25 is a *class tag id*, not an entity id: the first
occurrence of a class writes its name, later occurrences write an empty
name and the same id (string interning).  Observed registry for box.scdoc:
1=body 2=string_attrib 3=name_attrib 4=gen 5=attrib 7=lump 9=shell
10=face 11=loop 12=plane 13=surface 14=rgb_color 15=st 16=coedge
17=edge 18=vertex 19=straight 20=curve 21=point (6, 8 unused).

Entity references
-----------------
0x0c "ptr" token values are 0-BASED indices into the 0x0d record
sequence (entity N = records[N]).  -1 = null.  E.g. body#1's lump
pointer value 2 -> records[2] = the lump record.

Derived ACIS classes are stored as consecutive records, most derived first:
    string_attrib / name_attrib / gen / attrib      (generic attribute)
    plane / surface                                  (planar face geometry)
    straight / curve                                 (linear edge geometry)
    rgb_color / st / attrib                          (render style)

String abbreviation
-------------------
Repeated strings are written abbreviated: the first occurrence of
'ATTRIB_XACIS_NAME%6' is stored in full, later ones as just '%6'
(the unique suffix).  Resolved by the semantic layer (topology.py).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MAGIC = b"ACIS BinaryFileT"
END_MARKER = 'End-of-ACIS-data'

T_INT = 0x04
T_DOUBLE = 0x06
T_STRING = 0x07
T_PTR = 0x0C
T_CHAIN = 0x0E
T_RECORD = 0x0D
T_TERM = 0x11
T_VEC3 = 0x13
T_VEC3B = 0x14
T_FLAG_A = 0x0A
T_FLAG_B = 0x0B
T_INT15 = 0x15
T_ID = 0x25


class SabError(Exception):
    """Raised when the SAB stream cannot be tokenized."""


@dataclass
class Token:
    kind: str
    value: Any
    offset: int

    def __str__(self) -> str:
        v = self.value
        if self.kind in ('vec3', 'vec3b'):
            v = '(%.6g, %.6g, %.6g)' % tuple(v)
        elif isinstance(v, float):
            v = '%.6g' % v
        elif isinstance(v, str):
            v = repr(v)
        return f'{self.kind}={v}'


@dataclass
class EntityRecord:
    """One 0x0d record together with its 0x0e chain headers (names resolved)."""
    index: int                     # 1-based sequence number
    chain: List[Tuple[str, int]] = field(default_factory=list)
    name: str = ''                 # most-base class of this entity
    rec_id: Optional[int] = None   # class tag id of `name`
    tokens: List[Token] = field(default_factory=list)
    offset: int = 0

    @property
    def kind(self) -> str:
        """Most-derived ACIS class (first chain entry, else own name)."""
        if self.chain:
            return self.chain[0][0] or self.name
        return self.name

    @property
    def class_path(self) -> str:
        parts = [n for n, _ in self.chain] + ([self.name] if self.name else [])
        return '/'.join(parts) if parts else '<anonymous>'

    def dump(self) -> str:
        toks = ' '.join(str(t) for t in self.tokens)
        cid = '' if self.rec_id is None else f'#{self.rec_id}'
        chain = (' '.join(f'{n}#{i}' for n, i in self.chain) + ' ') if self.chain else ''
        return f'[{self.index:3d}] @{self.offset:5d} {chain}{self.name or "<anon>"}{cid}: {toks}'


@dataclass
class SabFile:
    product: str = ''
    version: str = ''
    date: str = ''
    doubles: List[float] = field(default_factory=list)
    product_id: str = ''
    header_blob: bytes = b''
    records: List[EntityRecord] = field(default_factory=list)
    classes: Dict[int, str] = field(default_factory=dict)

    @property
    def unit_scale(self) -> float:
        """First header double: internal-units -> document-units factor (1000)."""
        return self.doubles[0] if self.doubles else 1.0


class SabTokenizer:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.class_names: Dict[int, str] = {}

    # -- primitive readers -------------------------------------------------
    def _need(self, n: int, what: str) -> None:
        if self.pos + n > len(self.data):
            raise SabError(f'truncated {what} at offset {self.pos} (need {n} bytes)')

    def _u8(self) -> int:
        self._need(1, 'byte')
        b = self.data[self.pos]
        self.pos += 1
        return b

    def _i32(self) -> int:
        self._need(4, 'int32')
        v = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return v

    def _f64(self) -> float:
        self._need(8, 'double')
        v = struct.unpack_from('<d', self.data, self.pos)[0]
        self.pos += 8
        return v

    def _string(self) -> str:
        self._need(1, 'string length')
        ln = self._u8()
        self._need(ln, 'string body')
        s = self.data[self.pos:self.pos + ln].decode('latin-1')
        self.pos += ln
        return s

    def _vec3(self) -> Tuple[float, float, float]:
        self._need(24, 'vec3')
        v = struct.unpack_from('<3d', self.data, self.pos)
        self.pos += 24
        return v

    def _expect(self, marker: int) -> None:
        b = self._u8()
        if b != marker:
            raise SabError(f'expected 0x{marker:02x} got 0x{b:02x} at {self.pos - 1}')

    def _record_header(self) -> Tuple[str, Optional[int]]:
        """Read a 0x0d/0x0e header; resolve interned class names via registry."""
        hdrlen = self._u8()
        self._need(hdrlen, 'record header body')
        body = self.data[self.pos:self.pos + hdrlen]
        self.pos += hdrlen
        if T_ID in body:
            cut = body.index(T_ID)
            name = body[:cut].decode('latin-1')
            rec_id = struct.unpack_from('<i', body, cut + 1)[0]
            if name:
                self.class_names[rec_id] = name
            else:
                name = self.class_names.get(rec_id, name)
        else:
            name = body.decode('latin-1')
            rec_id = None
        return name, rec_id

    # -- main loop ----------------------------------------------------------
    def parse(self) -> SabFile:
        d = self.data
        if d[:16] != MAGIC:
            raise SabError('not an ACIS binary file (bad magic)')
        self.pos = 16
        out = SabFile()

        blob_len = self._i32()
        self._need(blob_len, 'header blob')
        out.header_blob = d[self.pos:self.pos + blob_len]
        self.pos += blob_len

        self._expect(T_STRING); out.product = self._string()
        self._expect(T_STRING); out.version = self._string()
        self._expect(T_STRING); out.date = self._string()
        out.doubles = []
        for _ in range(3):
            self._expect(T_DOUBLE)
            out.doubles.append(self._f64())

        flag = self._u8()
        if flag != T_FLAG_A:
            raise SabError(f'unexpected header byte 0x{flag:02x} at {self.pos - 1}')
        self._expect(T_STRING); out.product_id = self._string()

        records: List[EntityRecord] = []
        chain: List[Tuple[str, int]] = []
        rec_index = 0
        current: Optional[EntityRecord] = None
        while self.pos < len(d):
            off = self.pos
            b = self._u8()
            if b in (T_CHAIN, T_RECORD):
                name, rec_id = self._record_header()
                if name == END_MARKER:
                    break
                if b == T_CHAIN:
                    chain.append((name, rec_id if rec_id is not None else -1))
                    continue
                rec_index += 1
                current = EntityRecord(index=rec_index, chain=chain, name=name,
                                       rec_id=rec_id, offset=off)
                chain = []
                records.append(current)
                continue
            if current is None:
                raise SabError(f'token 0x{b:02x} outside any record at {off}')
            if b == T_INT:
                current.tokens.append(Token('int', self._i32(), off))
            elif b == T_PTR:
                current.tokens.append(Token('ptr', self._i32(), off))
            elif b == T_DOUBLE:
                current.tokens.append(Token('double', self._f64(), off))
            elif b == T_STRING:
                current.tokens.append(Token('string', self._string(), off))
            elif b == T_VEC3:
                current.tokens.append(Token('vec3', self._vec3(), off))
            elif b == T_VEC3B:
                current.tokens.append(Token('vec3b', self._vec3(), off))
            elif b == T_FLAG_A:
                current.tokens.append(Token('flag_a', None, off))
            elif b == T_FLAG_B:
                current.tokens.append(Token('flag_b', None, off))
            elif b == T_INT15:
                current.tokens.append(Token('int15', self._i32(), off))
            elif b == T_TERM:
                current = None
            else:
                raise SabError(
                    f'unknown token 0x{b:02x} at offset {off} '
                    f'(record {rec_index} {current.class_path})')
        out.records = records
        out.classes = dict(self.class_names)
        return out


def tokenize(data: bytes) -> SabFile:
    return SabTokenizer(data).parse()