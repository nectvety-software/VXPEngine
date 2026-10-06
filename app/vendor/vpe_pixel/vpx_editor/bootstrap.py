"""Qt environment report + one-click repair, shown at startup.

The stdlib half of the gate lives in `envcheck` — `ensure_runtime()` there runs
before Qt is imported, because a missing PySide6 cannot be reported with a Qt
dialog. This module is only reached once QApplication exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QSize, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from . import envcheck, icons
from .envcheck import Check
from .theme import get_theme
from .widgets import AccentButton


class RepairWorker(QThread):
    """Runs the pending repairs one after another, streaming their log."""

    line = Signal(str)
    step = Signal(str, bool)
    finished_all = Signal(int, int)

    def __init__(self, targets: List[Check], parent=None) -> None:
        super().__init__(parent)
        self.targets = targets

    def run(self) -> None:
        ok = bad = 0
        for c in self.targets:
            self.line.emit(f"> {c.label} — {c.fix_label}")
            try:
                result = bool(c.fix(self.line.emit))
            except Exception as exc:  # a repair must never take the app down
                result = False
                self.line.emit(f"  error: {exc}")
            if result:
                ok += 1
                self.line.emit("  done")
            else:
                bad += 1
                self.line.emit("  not resolved")
            self.step.emit(c.key, result)
        self.finished_all.emit(ok, bad)


class _CheckRow(QWidget):
    """Status glyph + label + detail, with a per-item Fix button."""

    def __init__(self, check: Check, on_fix: Callable[[Check], None]) -> None:
        super().__init__(None)
        self.check = check
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(11)

        self.status = QLabel()
        self.status.setFixedSize(20, 20)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.status)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = QLabel(check.label)
        self.title.setObjectName("Value")
        text.addWidget(self.title)
        self.sub = QLabel()
        self.sub.setObjectName("Muted")
        self.sub.setWordWrap(True)
        text.addWidget(self.sub)
        lay.addLayout(text, 1)

        self.fix_btn = QPushButton("Fix")
        self.fix_btn.setObjectName("Ghost")
        self.fix_btn.setMinimumHeight(30)
        icons.set_icon(self.fix_btn, "settings", 15)
        self.fix_btn.clicked.connect(lambda _=False, c=check: on_fix(c))
        lay.addWidget(self.fix_btn)

        self.refresh()

    def refresh(self) -> None:
        c = self.check
        if c.ok:
            glyph, token = "check", "ok"
        elif c.required:
            glyph, token = "close", "danger"
        else:
            glyph, token = "none", "warn"
        self.status.setPixmap(icons.icon(glyph, token).pixmap(QSize(18, 18)))
        self.status.setToolTip(f"{c.label}: {c.value}")
        detail = f"{c.value} — {c.detail}" if c.detail else c.value
        self.sub.setText(detail)
        show = c.fixable and not c.ok
        self.fix_btn.setVisible(show)
        self.fix_btn.setToolTip(f"{c.fix_label} — {c.label}")


class CheckList(QScrollArea):
    """Scrollable status list reused by the startup dialog and the installer."""

    def __init__(self, checks: List[Check], on_fix: Optional[Callable[[Check], None]] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.checks = checks
        self.rows: List[_CheckRow] = []
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        holder = QWidget()
        holder.setObjectName("Panel")
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        for i, c in enumerate(checks):
            if i:
                col.addWidget(_divider())
            row = _CheckRow(c, on_fix if on_fix else (lambda _c: None))
            self.rows.append(row)
            col.addWidget(row)
        col.addStretch(1)
        self.setWidget(holder)

    def refresh(self) -> None:
        for row in self.rows:
            row.refresh()


class EnvCheckDialog(QDialog):
    def __init__(self, checks: Optional[List[Check]] = None, parent=None,
                 title: str = "Environment check",
                 target_dir: Optional[Path] = None, payload_bytes: int = 0) -> None:
        super().__init__(parent)
        self.checks = checks if checks is not None else envcheck.collect(
            target_dir, payload_bytes)
        self.target_dir = target_dir
        self.payload_bytes = payload_bytes
        self.worker: Optional[RepairWorker] = None
        self.restart_needed = False
        self.setWindowTitle(f"{title} — VXP Pixel Editor")
        self.setMinimumSize(580, 520)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("Title")
        root.addWidget(heading)
        intro = QLabel(
            "Every component below is verified before the editor opens. "
            "Anything that can be repaired has a Fix button.")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.list = CheckList(self.checks, self._run_one, self)
        root.addWidget(self.list, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.hide()
        t = get_theme().tokens
        self.log.setStyleSheet(
            f"background:{t['input']};color:{t['muted']};"
            f"border:1px solid {t['border']};font-size:12px;")
        root.addWidget(self.log)

        buttons = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setObjectName("Muted")
        buttons.addWidget(self.summary, 1)
        self.fix_all = AccentButton("Fix automatically")
        icons.set_icon(self.fix_all, "refresh", 16, token="on_accent",
                       tooltip="Run every available repair in order")
        self.fix_all.clicked.connect(self._run_all)
        buttons.addWidget(self.fix_all)
        self.accept_btn = QPushButton("Continue")
        self.accept_btn.setObjectName("Primary")
        icons.set_icon(self.accept_btn, "check", 15, token="on_accent",
                       tooltip="Open the editor with the current setup")
        self.accept_btn.clicked.connect(self.accept)
        buttons.addWidget(self.accept_btn)
        self.close_btn = QPushButton("Exit")
        self.close_btn.setObjectName("Ghost")
        icons.set_icon(self.close_btn, "close", 15,
                       tooltip="Close without starting the editor")
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        root.addLayout(buttons)

        self._sync()

    # ---- state ----------------------------------------------------------
    def _sync(self) -> None:
        self.list.refresh()
        bad = envcheck.blocking(self.checks)
        can = envcheck.fixable(self.checks)
        ready = sum(1 for c in self.checks if c.ok)
        self.summary.setText(
            f"{ready}/{len(self.checks)} ready · "
            + (f"{len(bad)} blocking" if bad else "nothing blocking"))
        busy = self.worker is not None
        self.fix_all.setEnabled(bool(can) and not busy)
        self.fix_all.setText(f"Fix automatically ({len(can)})" if can
                             else "Fix automatically")
        self.accept_btn.setEnabled(not bad and not busy)
        self.close_btn.setEnabled(not busy)

    def _append(self, line: str) -> None:
        self.log.show()
        self.log.appendPlainText(line)

    # ---- repair ---------------------------------------------------------
    def _run(self, targets: List[Check]) -> None:
        if self.worker is not None or not targets:
            return
        self.worker = RepairWorker(targets, self)
        self.worker.line.connect(self._append)
        self.worker.step.connect(self._on_step)
        self.worker.finished_all.connect(self._on_done)
        self._sync()
        self.worker.start()

    def _run_one(self, check: Check) -> None:
        self._run([check])

    def _run_all(self) -> None:
        self._run(list(envcheck.fixable(self.checks)))

    def _on_step(self, key: str, ok: bool) -> None:
        if ok and key in ("pyside6", "vc"):
            self.restart_needed = True

    def _on_done(self, fixed: int, unresolved: int) -> None:
        self.worker = None
        self._append(f"— {fixed} repaired, {unresolved} unresolved")
        for c in self.checks:
            if not c.ok and c.key in ("appdata", "projects", "target"):
                fresh = {x.key: x for x in envcheck.collect(
                    self.target_dir, self.payload_bytes)}[c.key]
                c.ok, c.value, c.detail = fresh.ok, fresh.value, fresh.detail
        self._sync()
        if self.restart_needed and not envcheck.blocking(self.checks):
            self._append("restart required — close and launch the editor again")

    def closeEvent(self, event) -> None:
        if self.worker is not None:
            self.worker.quit()
            self.worker.wait(3000)
        super().closeEvent(event)


def _divider() -> QWidget:
    line = QWidget()
    line.setFixedHeight(1)
    line.setStyleSheet(
        f"background:{get_theme().token('border_soft', '#1E2738')};")
    return line


def show_environment_dialog(parent=None,
                            checks: Optional[List[Check]] = None,
                            title: str = "Environment check") -> bool:
    """Open the report modally. True when the user accepted."""
    return bool(EnvCheckDialog(checks, parent, title).exec())


def preflight(parent=None, force: bool = False) -> bool:
    """Gate the launch. False means the editor should not continue."""
    checks = envcheck.collect()
    if not envcheck.blocking(checks) and not force:
        return True
    dlg = EnvCheckDialog(checks, parent, "Environment check")
    dlg.exec()
    return not envcheck.blocking(dlg.checks)
