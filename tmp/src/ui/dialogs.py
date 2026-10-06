"""Custom modal dialogs. Nothing here uses a native OS dialog or title bar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation,
                            QTimer, Qt)
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from . import icons
from .theme import colors as theme_colors

KIND_ICON = {"info": "info", "question": "question", "warning": "warn", "critical": "close",
             "success": "check"}
KIND_TONE = {"info": "accent", "question": "accent", "warning": "warn", "critical": "danger",
             "success": "success"}


def _shadow(widget: QWidget, blur: int = 30, alpha: int = 150) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 10)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class ModalDialog(QDialog):
    """Frameless, rounded, animated modal. Subclasses fill `header`/`body`/`footer`."""

    def __init__(self, title: str, parent: QWidget | None = None, width: int = 440,
                 kind: str = "info", glyph: str | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setModal(True)
        self.setObjectName("ModalDialog")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        self.card = QFrame(self)
        self.card.setObjectName("RootContainer")
        _shadow(self.card)
        outer.addWidget(self.card)

        root = QVBoxLayout(self.card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        head = QFrame(self.card)
        head.setObjectName("DialogHeader")
        head.setFixedHeight(52)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(18, 0, 12, 0)
        hl.setSpacing(12)

        pal = theme_colors(QApplication.instance())
        tone = pal[KIND_TONE.get(kind, "accent")]
        badge = QFrame()
        badge.setObjectName("AccentBar")
        badge.setFixedSize(3, 22)
        badge.setProperty("tone", KIND_TONE.get(kind, "accent"))
        badge.style().polish(badge)

        mark = QLabel()
        mark.setPixmap(icons.pixmap(glyph or KIND_ICON.get(kind, "info"), tone, 20, 1.7))
        mark.setFixedSize(24, 24)
        mark.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitle")
        close = QPushButton()
        close.setProperty("role", "caption")
        close.setFlat(True)
        close.setFixedSize(30, 26)
        close.setIcon(icons.icon("close", pal["text_muted"], 14))
        close.clicked.connect(self.reject)

        hl.addWidget(badge)
        hl.addWidget(mark)
        hl.addWidget(self.title_label)
        hl.addStretch(1)
        hl.addWidget(close)

        self.body = QWidget(self.card)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(20, 16, 20, 8)
        self.body_layout.setSpacing(10)

        self.footer = QFrame(self.card)
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(20, 6, 20, 18)
        fl.setSpacing(8)
        fl.addStretch(1)
        self._footer_layout = fl

        root.addWidget(head)
        root.addWidget(self.body)
        root.addWidget(self.footer)

        self.setMinimumWidth(width)
        self._animated = False

    # ------------------------------------------------------------ animation

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._animated or not self.parentWidget():
            return
        self._animated = True
        target = self.geometry()
        self.setWindowOpacity(0.0)
        self.move(target.left(), target.top() + 16)
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(180)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(220)
        slide.setStartValue(self.pos())
        slide.setEndValue(QPoint(target.left(), target.top()))
        slide.setEasingCurve(QEasingCurve.OutCubic)
        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)
        group.start()
        self._anim = group

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.parentWidget():
            self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if not parent or not parent.isVisible():
            return
        geo = parent.geometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = max(geo.y(), geo.y() + (geo.height() - self.height()) // 2 - 30)
        self.move(x, y)

    # ------------------------------------------------------------ footer api

    def add_button(self, text: str, role: str = "ghost", key: Qt.Key | None = None
                   ) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("role", role)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumWidth(96 if role != "chip" else 60)
        self._footer_layout.addWidget(button)
        if role == "primary":
            button.setDefault(True)
            button.setAutoDefault(True)
        return button


class MessageDialog(ModalDialog):
    def __init__(self, parent, title: str, text: str, informative: str = "",
                 kind: str = "info", buttons: tuple[str, ...] = ("OK",),
                 glyph: str | None = None):
        super().__init__(title, parent, 460 if informative else 420, kind, glyph)
        body = QVBoxLayout()
        body.setSpacing(6)
        main = QLabel(text)
        main.setWordWrap(True)
        main.setStyleSheet("font-size:14px;")
        body.addWidget(main)
        if informative:
            sub = QLabel(informative)
            sub.setWordWrap(True)
            sub.setProperty("role", "muted")
            body.addWidget(sub)
        self.body_layout.addLayout(body)

        self.result_value: str = ""
        for i, label in enumerate(buttons):
            role = "primary" if i == len(buttons) - 1 else "ghost"
            if label.lower() in ("huỷ", "cancel", "discard"):
                role = "ghost"
            button = self.add_button(label, role)
            button.clicked.connect(lambda _=False, name=label: self._finish(name))
        self._center_on_parent()

    def _finish(self, value: str) -> None:
        self.result_value = value
        self.accept()

    @classmethod
    def ask(cls, parent, title, text, informative="", kind="info",
            buttons=("OK",)) -> str:
        dialog = cls(parent, title, text, informative, kind, buttons)
        dialog.exec()
        return dialog.result_value


class InputDialog(ModalDialog):
    def __init__(self, parent, title: str, label: str, value: str = "",
                 placeholder: str = "", kind: str = "question",
                 multiline: bool = False):
        super().__init__(title, parent, 440, kind)
        self.field = QLineEdit(value)
        self.field.setPlaceholderText(placeholder)
        self.body_layout.addWidget(QLabel(label))
        self.body_layout.addWidget(self.field)
        ok = self.add_button("Xác nhận", "primary")
        self.add_button("Huỷ", "ghost")
        ok.clicked.connect(self.accept)
        self.field.returnPressed.connect(self.accept)
        self.field.selectAll()
        self.field.setFocus()
        self._center_on_parent()

    @classmethod
    def ask_text(cls, parent, title, label, value="", placeholder="") -> str | None:
        dialog = cls(parent, title, label, value, placeholder)
        return dialog.field.text().strip() if dialog.exec() else None


class NumberDialog(ModalDialog):
    """Numeric prompt used for map resizing and tile size overrides."""

    def __init__(self, parent, title: str, rows: list[tuple[str, int, int, int]]):
        super().__init__(title, parent, 400, "question")
        self.fields: dict[str, QSpinBox] = {}
        grid = QVBoxLayout()
        grid.setSpacing(10)
        for label, value, lo, hi in rows:
            line = QHBoxLayout()
            cap = QLabel(label)
            cap.setMinimumWidth(96)
            spin = QSpinBox()
            spin.setRange(lo, hi)
            spin.setValue(value)
            spin.setFixedWidth(110)
            line.addWidget(cap)
            line.addWidget(spin)
            line.addStretch(1)
            grid.addLayout(line)
            self.fields[label] = spin
        self.body_layout.addLayout(grid)
        ok = self.add_button("Xác nhận", "primary")
        self.add_button("Huỷ", "ghost")
        ok.clicked.connect(self.accept)
        self._center_on_parent()

    @property
    def values(self) -> dict[str, int]:
        return {k: s.value() for k, s in self.fields.items()}


class AboutDialog(ModalDialog):
    def __init__(self, parent, engine_name: str, version: str, rows: dict[str, str]):
        super().__init__("Giới thiệu", parent, 470, "info", "app")
        head = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icons.pixmap("app", theme_colors(QApplication.instance())["accent"], 40,
                                    1.5))
        mark.setFixedSize(48, 48)
        head.addWidget(mark)
        block = QVBoxLayout()
        title = QLabel(f"{engine_name} {version}")
        title.setProperty("role", "h1")
        sub = QLabel("Engine đồ hoạ 2D + trình soạn tilemap · PySide6 / Qt 6")
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        block.addWidget(title)
        block.addWidget(sub)
        head.addLayout(block)
        head.addStretch(1)
        self.body_layout.addLayout(head)

        table = QFrame()
        table.setProperty("role", "inset")
        tl = QVBoxLayout(table)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(4)
        for key, value in rows.items():
            line = QHBoxLayout()
            k = QLabel(key)
            k.setProperty("role", "muted")
            v = QLabel(value)
            v.setProperty("role", "mono")
            line.addWidget(k)
            line.addStretch(1)
            line.addWidget(v)
            tl.addLayout(line)
        self.body_layout.addWidget(table)
        self.add_button("Đóng", "primary").clicked.connect(self.accept)
        self._center_on_parent()


class FileDialog(ModalDialog):
    """Non-native file chooser: quick locations, filtered list, typed name."""

    def __init__(self, parent, title: str, directory: str | Path, exts: list[str],
                 save: bool, filename: str = ""):
        super().__init__(title, parent, 700, "question", "folder")
        self.exts = [e.lower().lstrip("*").lstrip(".") for e in exts]
        self.save = save
        self.cwd = Path(directory)

        head = QHBoxLayout()
        self.path_label = QLabel(str(self.cwd))
        self.path_label.setProperty("role", "mono")
        head.addWidget(self.path_label)
        head.addStretch(1)
        self.body_layout.addLayout(head)

        middle = QHBoxLayout()
        middle.setSpacing(12)

        quick = QListWidget()
        quick.setFixedWidth(150)
        quick.setProperty("role", "sidebar")
        for label, path in self._quick_locations():
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(path))
            quick.addItem(item)
        quick.currentItemChanged.connect(self._on_quick)
        middle.addWidget(quick)

        self.listing = QListWidget()
        self.listing.setAlternatingRowColors(False)
        self.listing.setSelectionMode(QAbstractItemView.SingleSelection)
        self.listing.itemDoubleClicked.connect(lambda _i: self._accept_current())
        self.listing.currentItemChanged.connect(self._on_select)
        middle.addWidget(self.listing, 1)
        self.body_layout.addLayout(middle)

        name_row = QHBoxLayout()
        cap = QLabel("Tên file" if save else "File")
        cap.setProperty("role", "muted")
        self.name = QLineEdit(filename)
        self.name.setPlaceholderText(".".join(["untitled", self.exts[0]]) if save else "")
        self.name.textEdited.connect(self._on_typed)
        self.name.returnPressed.connect(self._accept_current)
        name_row.addWidget(cap)
        name_row.addWidget(self.name)
        self.body_layout.addLayout(name_row)

        self.error = QLabel("")
        self.error.setProperty("role", "error")
        self.body_layout.addWidget(self.error)

        self.add_button("Huỷ", "ghost").clicked.connect(self.reject)
        ok = self.add_button("Lưu" if save else "Mở", "primary")
        ok.clicked.connect(self._accept_current)
        self._reload()
        quick.setCurrentRow(0)
        self._center_on_parent()

    @staticmethod
    def _quick_locations() -> list[tuple[str, Path]]:
        home = Path.home()
        spots = [("Dự án", Path.cwd()), ("Tài nguyên", home / "Pictures"),
                 ("Tải về", home / "Downloads"), ("Màn hình", home / "Desktop"),
                 ("Home", home)]
        return [(label, p) for label, p in spots if p.exists()]

    def _on_quick(self, current: QListWidgetItem, _previous) -> None:
        if not current:
            return
        self._goto(Path(current.data(Qt.UserRole)))

    def _goto(self, path: Path) -> None:
        self.cwd = path.resolve()
        self.path_label.setText(str(self.cwd))
        self._reload()

    def _reload(self) -> None:
        self.listing.clear()
        if not self.cwd.exists():
            return
        for child in sorted(self.cwd.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if child.is_dir():
                if not child.name.startswith("."):
                    self._add(child, child.name + "/", "folder")
            elif not self.exts or child.suffix.lstrip(".").lower() in self.exts:
                self._add(child, child.name, "image")

    def _add(self, path: Path, text: str, glyph: str) -> None:
        pal = theme_colors(QApplication.instance())
        item = QListWidgetItem(QIcon(icons.pixmap(glyph, pal["text_muted"], 15)), "  " + text)
        item.setData(Qt.UserRole, str(path))
        item.setToolTip(str(path))
        self.listing.addItem(item)

    def _on_select(self, current: QListWidgetItem, _previous) -> None:
        if current and self.save:
            self.name.setText(Path(current.data(Qt.UserRole)).name)

    def _on_typed(self, text: str) -> None:
        target = self.cwd / text
        if not self.save and target.is_dir():
            self._goto(target)
            self.name.clear()

    def _accept_current(self) -> None:
        items = self.listing.selectedItems() or (
            [self.listing.currentItem()] if self.listing.currentItem() else [])
        if not self.save and items:
            target = Path(items[0].data(Qt.UserRole))
            if target.is_dir():
                self._goto(target)
                return
        raw = self.name.text().strip()
        if not raw:
            self.error.setText("Nhập tên file trước khi tiếp tục.")
            return
        target = (self.cwd / raw)
        if self.save:
            if self.exts and target.suffix.lstrip(".").lower() not in self.exts:
                target = target.with_suffix("." + self.exts[0])
            if target.exists():
                answer = MessageDialog.ask(self, "Ghi đè file?", target.name,
                                           "File đã tồn tại và sẽ bị ghi đè.", "warning",
                                           ("Huỷ", "Ghi đè"))
                if answer != "Ghi đè":
                    return
        elif not target.exists():
            self.error.setText("Không tìm thấy file.")
            return
        self.selected = target
        self.accept()

    @classmethod
    def get_open_name(cls, parent, title: str, directory, exts: list[str]) -> str | None:
        dialog = cls(parent, title, directory or Path.cwd(), exts, False)
        return str(dialog.selected) if dialog.exec() else None

    @classmethod
    def get_save_name(cls, parent, title: str, directory, exts: list[str],
                      filename: str = "") -> str | None:
        dialog = cls(parent, title, directory or Path.cwd(), exts, True, filename)
        return str(dialog.selected) if dialog.exec() else None


class Toast(QFrame):
    """Transient, non-modal feedback that never steals focus."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setLayout(QHBoxLayout(self))
        self.layout().setContentsMargins(12, 9, 14, 9)
        self.layout().setSpacing(9)
        self.mark = QLabel()
        self.text = QLabel()
        self.text.setObjectName("ToastText")
        self.layout().addWidget(self.mark)
        self.layout().addWidget(self.text)
        _shadow(self, 22, 120)
        self.hide()

    def popup(self, message: str, kind: str = "info", msec: int = 2600) -> None:
        pal = theme_colors(QApplication.instance())
        tone = pal[KIND_TONE.get(kind, "accent")]
        self.mark.setPixmap(icons.pixmap(KIND_ICON.get(kind, "dot"), tone, 16, 1.8))
        self.text.setText(message)
        self.adjustSize()
        host = self.parentWidget()
        if host:
            self.move(host.width() - self.width() - 24, host.height() - self.height() - 24)
        self.show()
        self.raise_()
        QTimer.singleShot(msec, self.hide)
