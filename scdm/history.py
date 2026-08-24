"""Undo stack of KernelDoc snapshots. Index 0 is the oldest kept state."""
from __future__ import annotations

from typing import Any, List, Optional


class History:
    def __init__(self, limit: int = 50):
        self.limit = limit
        self._stack: List[Any] = []
        self._index = -1

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return 0 <= self._index + 1 < len(self._stack)

    def push(self, snapshot: Any) -> None:
        self._stack = self._stack[: self._index + 1]
        self._stack.append(snapshot)
        if len(self._stack) > self.limit:
            drop = len(self._stack) - self.limit
            self._stack = self._stack[drop:]
        self._index = len(self._stack) - 1

    def undo(self) -> Optional[Any]:
        if not self.can_undo():
            return None
        self._index -= 1
        return self._stack[self._index]

    def redo(self) -> Optional[Any]:
        if not self.can_redo():
            return None
        self._index += 1
        return self._stack[self._index]

    def current(self) -> Optional[Any]:
        if self._index < 0:
            return None
        return self._stack[self._index]

    def clear(self) -> None:
        self._stack.clear()
        self._index = -1
