"""P319/R60: 材料库与零件属性 —— 质量 = 体积 × 密度（闭式），属性随 .scdm 往返。

Densities are kg/m^3, matching the kernel's metre convention, so
`mass = K.volume(shape) * density` needs no unit juggling; reporting layers
convert to g/kg as they like.  E and nu are stored for the analysis side and are
never used to build geometry.

Custom materials can be registered, and registration validates the physical
numbers (a negative or zero density is refused) - the library is data, not a
place to smuggle in wrong numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MATERIALS: Dict[str, Dict[str, Any]] = {
    "steel": {"name": "碳钢", "density": 7850.0, "E": 210.0e9, "nu": 0.30},
    "stainless": {"name": "不锈钢", "density": 7930.0, "E": 193.0e9, "nu": 0.29},
    "aluminum": {"name": "铝合金", "density": 2700.0, "E": 70.0e9, "nu": 0.33},
    "copper": {"name": "紫铜", "density": 8960.0, "E": 117.0e9, "nu": 0.34},
    "brass": {"name": "黄铜", "density": 8500.0, "E": 100.0e9, "nu": 0.34},
    "titanium": {"name": "钛合金", "density": 4506.0, "E": 110.0e9, "nu": 0.34},
    "abs": {"name": "ABS", "density": 1040.0, "E": 2.3e9, "nu": 0.35},
}

DEFAULT = "steel"


def register_material(key: str, name: str, density: float, E: float = 0.0,
                      nu: float = 0.0) -> Dict[str, Any]:
    """Add/replace a material; the physical numbers are validated here."""
    k = str(key).strip().lower()
    if not k:
        raise ValueError("材料代号不能为空")
    d = float(density)
    if d <= 0:
        raise ValueError("材料密度必须为正（kg/m³）：%s" % density)
    e = float(E)
    if e < 0:
        raise ValueError("弹性模量不能为负")
    n = float(nu)
    if not (-1.0 < n < 0.5):
        raise ValueError("泊松比必须在 (-1, 0.5) 内")
    MATERIALS[k] = {"name": str(name or k), "density": d, "E": e, "nu": n}
    return MATERIALS[k]


def entry(material: str) -> Dict[str, Any]:
    """The material table row; unknown keys raise instead of guessing."""
    k = str(material).strip().lower()
    if k not in MATERIALS:
        raise ValueError("未知材料：%s（可选 %s）"
                         % (material, "/".join(sorted(MATERIALS))))
    return MATERIALS[k]


def density(material: str = DEFAULT) -> float:
    return float(entry(material)["density"])


def mass_from_volume(volume_m3: float, material: str = DEFAULT) -> float:
    """Closed form: mass = volume x density (kg)."""
    v = float(volume_m3)
    if v < 0:
        raise ValueError("体积不能为负")
    return v * density(material)


def mass(shape, material: str = DEFAULT) -> float:
    """Mass of a shape in kg (kernel volume x material density)."""
    from scdm import kernel as K
    return mass_from_volume(K.volume(shape), material)


@dataclass
class PartProperties:
    """P319: 零件属性 —— 材料 + 自定义字段（随 .scdm 往返）。"""

    material: str = DEFAULT
    custom: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self) -> "PartProperties":
        info = entry(self.material)                 # raises on unknown material
        self.material = str(self.material).strip().lower()
        self.custom = {str(k): str(v)
                       for k, v in (self.custom or {}).items()}
        self._info = info
        return self

    def info(self) -> Dict[str, Any]:
        return dict(entry(self.material))

    def name(self) -> str:
        return str(self.info().get("name", self.material))

    def density(self) -> float:
        return float(self.info()["density"])

    def mass(self, shape) -> float:
        from scdm import kernel as K
        return mass_from_volume(K.volume(shape), self.material)

    def to_dict(self) -> Dict[str, Any]:
        return {"material": self.material, "custom": dict(self.custom)}

    @classmethod
    def from_dict(cls, data) -> "PartProperties":
        data = data or {}
        return cls(material=data.get("material", DEFAULT),
                   custom=dict(data.get("custom") or {}))


def bom_rows(bodies, properties: Optional[Dict[str, Any]] = None,
             scale: float = 1000.0) -> List[Dict[str, Any]]:
    """P319: BOM rows (mm/g units) with material and mass - the material change
    follows through because mass is recomputed from the live volume each time."""
    from scdm import kernel as K
    props = properties or {}
    out: List[Dict[str, Any]] = []
    for b in bodies or ():
        p = props.get(getattr(b, "id", None))
        if p is None:
            p = PartProperties()
        vol = K.volume(b.shape)
        out.append({
            "id": getattr(b, "id", ""),
            "name": getattr(b, "name", ""),
            "material": p.material,
            "material_name": p.name(),
            "density": p.density(),
            "volume_mm3": vol * scale ** 3,
            "mass_g": mass_from_volume(vol, p.material) * 1000.0,
            "area_mm2": K.area(b.shape) * scale ** 2,
            "custom": dict(p.custom),
        })
    return out


def bom_totals(rows) -> Dict[str, float]:
    """Totals for a BOM (mass in g, volume in mm³) - the sum of the rows."""
    return {"mass_g": sum(float(r["mass_g"]) for r in rows or ()),
            "volume_mm3": sum(float(r["volume_mm3"]) for r in rows or ()),
            "count": float(len(list(rows or ())))}
