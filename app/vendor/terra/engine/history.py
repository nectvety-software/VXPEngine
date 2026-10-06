"""Undo history. Commands carry cell edits so painting stays O(changes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

Edits = list[tuple[int, int, int, int]]  # (layer_index, cell_index, old, new)


@dataclass
class PaintCommand:
    label: str
    tilemap: object
    edits: Edits

    def redo(self) -> None:
        self._write(3)

    def undo(self) -> None:
        self._write(2)

    def _write(self, slot: int) -> None:
        for li, ci, old, new in self.edits:
            self.tilemap.layers[li].cells[ci] = old if slot == 2 else new


@dataclass
class FnCommand:
    """Ad-hoc command for layer/property changes: pass a do/undo pair."""

    label: str
    do: Callable[[], None]
    undo_fn: Callable[[], None]
    run_on_push: bool = True

    def redo(self) -> None:
        self.do()

    def undo(self) -> None:
        self.undo_fn()


@dataclass
class History:
    limit: int = 250
    entries: list = field(default_factory=list)
    cursor: int = 0

    @property
    def can_undo(self) -> bool:
        return self.cursor > 0

    @property
    def can_redo(self) -> bool:
        return self.cursor < len(self.entries)

    @property
    def undo_label(self) -> str:
        return self.entries[self.cursor - 1].label if self.can_undo else ""

    @property
    def redo_label(self) -> str:
        return self.entries[self.cursor].label if self.can_redo else ""

    def push(self, command) -> None:
        if isinstance(command, PaintCommand) and not command.edits:
            return
        if isinstance(command, FnCommand) and command.run_on_push:
            command.redo()
        del self.entries[self.cursor:]
        self.entries.append(command)
        if len(self.entries) > self.limit:
            self.entries.pop(0)
        self.cursor = len(self.entries)

    def undo(self) -> bool:
        if not self.can_undo:
            return False
        self.cursor -= 1
        self.entries[self.cursor].undo()
        return True

    def redo(self) -> bool:
        if not self.can_redo:
            return False
        self.entries[self.cursor].redo()
        self.cursor += 1
        return True

    def clear(self) -> None:
        self.entries.clear()
        self.cursor = 0
