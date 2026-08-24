"""Direct-modeling tool state machine (UI now; kernel in M2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Tool:
    id: str
    name: str
    wave: str
    hud: str = ""
    live: bool = False  # True when the tool can commit geometry


class ToolManager:
    def __init__(self, status: Callable[[str], None]):
        self._status = status
        self.active = "tool.select"
        self.mode = "mode.3d"
        self.previous: Optional[str] = None
        self.options: Dict[str, object] = {}

    def set_mode(self, mode_id: str, wave: str, live: bool) -> None:
        if not live:
            self._status(f"{wave} 未实现：{mode_id}（界面已切换，内核稍后接入）")
        self.mode = mode_id

    def activate(self, cmd_id: str, name: str, wave: str, live: bool, hud: str) -> None:
        if cmd_id != self.active:
            self.previous = self.active
        self.active = cmd_id
        if live:
            self._status(hud or name)
        else:
            self._status(f"{wave} 未实现：{name} — 选项已显示，提交将在内核接入后生效")

    def repeat_previous(self) -> Optional[str]:
        return self.previous
