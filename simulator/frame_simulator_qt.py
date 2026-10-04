r"""Khung giả lập VXPEmu — **PySide6**, chỉ hiện đúng khung máy.

Bám sát ảnh tham chiếu ``8687567.PNG`` / mô tả giao diện:

* Nền xanh than đậm ``#12161f``; phím xanh navy đậm hơn nền, viền mảnh, phát
  sáng nhẹ khi rê chuột (cảm giác "cảm ứng").
* **Thanh công cụ** 7 nút vuông nằm góc trên bên phải — đúng thứ tự:
  khung ảnh · mũi tên xuống · máy ảnh · thư mục+cộng · máy quay+cộng ·
  đồng bộ · mũi tên chéo mở rộng.
* **Khung nội dung** — ô vuông đen viền mảnh ở giữa phía trên, bên trong là
  bản đồ lưới đô thị khái niệm (đường phố + điểm phát sáng). Đè lên góc trên
  trái là hai dòng xanh nhạt: ``Case ID: FB-1984-ZUL-10`` và
  ``Subject: G_M_A_S`` (có con trỏ nhấp nháy, ký tự đầu được tô sáng).
* **Thanh hướng dẫn** ngay dưới khung nội dung:
  ``Nhấn nhiều lần: 2=abc, 3=def, 7=pqrs, 0=space`` — và khi đang gõ sẽ đổi sang
  dạng ``2 → b   letter 2/3``.
* **Bàn phím** chiếm nửa dưới, bề mặt có vân nhám, chia ba phần rõ rệt:
  lưới 3×3 số (1–9, phím 1 trống dưới số) + hàng ``*`` / ``0`` rộng hơn;
  cụm điều hướng ``_ ↑ / ← OK → / 🗑 ↓``; cột dọc ngoài cùng ``_ ← #⏎``.

Chạy::

    .venv\Scripts\python.exe simulator\frame_simulator_qt.py

Đây là bản xem trước thiết kế thuần túy; runtime ứng dụng dùng VXPEmu.
"""
from __future__ import annotations

import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# --------------------------------------------------------------------------
# Bảng màu — xanh than đậm #12161f, nhấn xanh nhạt / xám nhạt.
# --------------------------------------------------------------------------
C_BG = "#12161f"          # nền chính
C_BG_DEEP = "#0d1119"     # nền cửa sổ (sâu hơn khung)
C_KEY = "#0f141d"         # mặt phím — navy ĐẬM HƠN nền chính theo mô tả
C_KEY_HOVER = "#141b28"
C_KEY_OK = "#1b2434"      # phím OK nổi hơn chút
C_BORDER = "#263247"      # viền mảnh
C_BORDER_SOFT = "#1c2433"
C_TEXT = "#e2e8f0"
C_TEXT_DIM = "#94a3b8"
C_TEXT_FAINT = "#64748b"
C_ACCENT = "#5eead4"      # teal — điểm nhấn
C_ACCENT_2 = "#8b5cf6"    # tím — chữ multi-tap
C_RECORD = "#fb7185"      # hồng — nút ghi
C_SCREEN = "#06080c"      # ô màn hình đen

# --------------------------------------------------------------------------
# Icon font "Segoe MDL2 Assets" — đúng font VXPEmu dùng. Mã glyph nằm vùng
# Private Use Area nên không bị biến thành color emoji.
# --------------------------------------------------------------------------
MDL2_FONT = "Segoe MDL2 Assets"
MDL2_PICTURE = "\uE8B7"     # 🖼 khung ảnh
MDL2_DOWNLOAD = "\uE896"    # ⬇ mũi tên xuống
MDL2_CAMERA = "\uE722"      # máy ảnh
MDL2_NEWFOLDER = "\uE8F4"   # thư mục + dấu cộng
MDL2_CAMCORDER = "\uE714"   # máy quay + dấu cộng (hồng)
MDL2_SYNC = "\uE895"        # mũi tên tròn đồng bộ
MDL2_EXPAND = "\uE740"      # mũi tên chéo mở rộng

MDL2_UP = "\uE74A"
MDL2_DOWN = "\uE74B"
MDL2_LEFT = "\uE72B"
MDL2_RIGHT = "\uE72A"
MDL2_DELETE = "\uE74D"      # thùng rác
MDL2_ENTER = "\uE751"       # return

# Chuỗi dự phòng khi máy không có font MDL2 (tránh ô vuông rỗng/tofu).
_FALLBACK = {
    MDL2_PICTURE: "▭",
    MDL2_DOWNLOAD: "↓",
    MDL2_CAMERA: "◉",
    MDL2_NEWFOLDER: "▤",
    MDL2_CAMCORDER: "●",
    MDL2_SYNC: "↻",
    MDL2_EXPAND: "↗",
    MDL2_UP: "↑",
    MDL2_DOWN: "↓",
    MDL2_LEFT: "←",
    MDL2_RIGHT: "→",
    MDL2_DELETE: "⌫",
    MDL2_ENTER: "⎆",
}

_icon_family: str | None = None


def resolve_icon_font() -> str:
    """Family icon-font dùng được trên máy, hoặc ``""`` nếu không có."""
    global _icon_family
    if _icon_family is not None:
        return _icon_family
    db = QFontDatabase()
    for family in (MDL2_FONT, "Holo MDL2 Assets"):
        if family in set(db.families()):
            _icon_family = family
            return family
    ttf = Path(r"C:\Windows\Fonts\segmdl2.ttf")
    if ttf.is_file():
        font_id = db.addApplicationFont(str(ttf))
        if font_id >= 0 and MDL2_FONT in db.applicationFontFamilies(font_id):
            _icon_family = MDL2_FONT
            return MDL2_FONT
    _icon_family = ""
    return ""


def _icon_font(size: int = 15) -> QFont:
    return QFont(resolve_icon_font() or "Segoe UI Symbol", size)


def _glyph(code: str) -> str:
    """Glyph MDL2 nếu có font, ngược lại ký tự hình học tương đương."""
    return code if resolve_icon_font() else _FALLBACK.get(code, "?")


# --------------------------------------------------------------------------
# Ô màn hình — bản đồ lưới đô thị khái niệm + overlay
# --------------------------------------------------------------------------
class ScreenPane(QFrame):
    """Ô vuông đen 240×320 vẽ bản đồ đô thị + hai dòng overlay phía trên."""

    SCREEN_W = 240
    SCREEN_H = 320

    #: (x, y, bán_kính, màu) — các điểm phát sáng trên bản đồ.
    _MARKERS = (
        (60, 40, 13, "#5eead4"),
        (90, 80, 13, "#5eead4"),
        (120, 120, 15, "#fb7185"),
        (180, 200, 15, "#fb7185"),
        (210, 240, 13, "#5eead4"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenPane")
        self._zoom = 1.0
        self.setFixedSize(int(self.SCREEN_W * self._zoom), int(self.SCREEN_H * self._zoom))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # --- Overlay: Case ID / Subject, đè lên góc trên trái ---
        overlay = QWidget(self)
        # QSS toàn cục của IDE có luật `QWidget { background }` — nếu không có
        # objectName + luật transparent riêng, overlay sẽ đục và che kín màn hình.
        overlay.setObjectName("ScreenOverlay")
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._overlay = overlay
        self._overlay_layout = QVBoxLayout(overlay)
        self._overlay_layout.setContentsMargins(7, 6, 7, 6)
        self._overlay_layout.setSpacing(1)
        lay = self._overlay_layout

        self._case_label = QLabel('Mã vụ án: <span style="color:#e2e8f0">FB-1984-ZUL-10</span>')
        self._case_label.setObjectName("OverlayLine")
        lay.addWidget(self._case_label)

        # 'G' được tô sáng (accent) — phần còn lại màu thường. Nội dung nạp
        # qua ``set_subject`` để luôn nhất quán với logic gõ phím.
        self._subject_label = QLabel()
        self._subject_label.setObjectName("OverlayLine")
        lay.addWidget(self._subject_label)

        self._caret = QLabel("|")
        self._caret.setObjectName("OverlayCaret")
        # Con trỏ nằm ngay sau chuỗi Subject — đặt tuyệt đối, căn theo chiều
        # rộng thực tế của nhãn để không bị lệch khi font khác nhau.
        self._caret.setParent(self)
        self._caret.adjustSize()

        lay.addStretch(1)

        self._caret_timer = QTimer(self)
        self._caret_timer.setInterval(530)
        self._caret_timer.timeout.connect(self._toggle_caret)
        self._caret_timer.start()

        # Chuỗi Subject lưu dưới dạng **chỉ chữ** (không kể dấu '_'); khi
        # hiển thị mới nối bằng '_' → "GMAS" hiện thành "G_M_A_S". Cách này
        # giúp gõ phím chỉ cần nối thêm ký tự mà không phải vá chuỗi có sẵn.
        self._subject = ""
        self._max_letters = 4        # "G_M_A_S" = 4 chữ
        self.set_subject("GMAS")     # trạng thái "đang sử dụng" mặc định

        # Ảnh scene đồng bộ từ IDE (240x320). Khi có ảnh này, màn hình hiển
        # thị đúng màn chơi đang mở trong IDE thay vì bản đồ tĩnh.
        self._scene_image = None
        self.set_zoom(1.0)

    # ------------------------------------------------------------------

    def set_scene_image(self, image) -> None:
        """Nhận ảnh scene từ IDE; None = quay lại bản đồ tĩnh + overlay."""
        self._scene_image = image
        has_scene = image is not None and not image.isNull()
        self._case_label.setVisible(not has_scene)
        self._subject_label.setVisible(not has_scene)
        self._caret.setVisible(not has_scene)
        self.update()

    def _toggle_caret(self) -> None:
        if self._scene_image is not None and not self._scene_image.isNull():
            self._caret.setVisible(False)
            return
        self._caret.setVisible(not self._caret.isVisible())

    def _paint_overlay_position(self) -> None:
        """Đặt con trỏ ngay sau nhãn Subject."""
        m_left, m_top = self._overlay_margins()
        width = self._subject_label.sizeHint().width()
        self._caret.move(m_left + width - 1, m_top + self._case_label.sizeHint().height() + 1)

    def _overlay_margins(self) -> tuple[int, int]:
        return int(7 * self._zoom), int(6 * self._zoom)

    def set_zoom(self, zoom: float) -> None:
        """Phóng to/thu nhỏ ô màn hình (1x = 240x320 thật của thiết bị)."""
        self._zoom = max(1.0, float(zoom))
        self.setFixedSize(int(self.SCREEN_W * self._zoom), int(self.SCREEN_H * self._zoom))
        for label, base in ((self._case_label, 9), (self._subject_label, 9), (self._caret, 10)):
            font = label.font()
            font.setPixelSize(int(base * self._zoom))
            label.setFont(font)
        left, top = self._overlay_margins()
        self._overlay_layout.setContentsMargins(left, top, left, top)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._subject_label.adjustSize()
        self._paint_overlay_position()
        self.update()

    def set_subject(self, text: str) -> None:
        """Cập nhật chuỗi Subject; ký tự đầu luôn được tô sáng."""
        self._subject = text[: self._max_letters]
        if not self._subject:
            self._subject_label.setText(
                'Chủ đề: <span style="color:#e2e8f0">_</span>'
            )
        else:
            head = self._subject[0]
            tail = "_" + "_".join(self._subject[1:]) if len(self._subject) > 1 else ""
            self._subject_label.setText(
                f'Chủ đề: <span style="color:#5eead4;font-weight:700">{head}</span>'
                f'<span style="color:#e2e8f0">{tail}</span>'
            )
        self._subject_label.adjustSize()
        self._paint_overlay_position()

    @property
    def subject(self) -> str:
        return self._subject

    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._paint_overlay_position()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(6, 6, self.width() - 12, self.height() - 12)
        p.fillRect(rect, QColor(C_SCREEN))

        p.save()
        p.setClipRect(rect)

        if self._scene_image is not None and not self._scene_image.isNull():
            # Màn chơi đồng bộ từ IDE: vẽ đúng khung 240x320 (giữ tỉ lệ).
            img = self._scene_image
            scale = min(rect.width() / img.width(), rect.height() / img.height())
            w = img.width() * scale
            h = img.height() * scale
            target = QRectF(
                rect.center().x() - w / 2,
                rect.center().y() - h / 2,
                w,
                h,
            )
            p.drawImage(target, img)
            p.restore()
            p.end()
            return

        # --- Bản đồ vẽ trong tọa độ logic (0..228, 0..308) rồi scale theo zoom ---
        log_w = float(self.SCREEN_W - 12)
        log_h = float(self.SCREEN_H - 12)
        p.translate(rect.topLeft())
        p.scale(rect.width() / log_w, rect.height() / log_h)
        p.setClipRect(QRectF(0, 0, log_w, log_h))

        # --- Lưới đô thị: đại lộ dày, đường phố mảnh ---
        p.setPen(QPen(QColor("#0f172a"), 22, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.FlatCap))
        for y in (80, 160, 240):
            p.drawLine(QPointF(0, y), QPointF(log_w, y))
        for x in (60, 120, 180):
            p.drawLine(QPointF(x, 0), QPointF(x, log_h))

        p.setPen(QPen(QColor("#0b1120"), 10, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.FlatCap))
        for y in (40, 120, 200, 280):
            p.drawLine(QPointF(0, y), QPointF(log_w, y))
        for x in (30, 90, 150, 210):
            p.drawLine(QPointF(x, 0), QPointF(x, log_h))

        # Mắt lưới rất mảnh để tạo chi tiết "bản đồ kỹ thuật số".
        p.setPen(QPen(QColor("#0a0f18"), 1))
        step = 15
        x = 0.0
        while x <= log_w:
            p.drawLine(QPointF(x, 0), QPointF(x, log_h))
            x += step
        y = 0.0
        while y <= log_h:
            p.drawLine(QPointF(0, y), QPointF(log_w, y))
            y += step

        # --- Điểm đánh dấu phát sáng ---
        for mx, my, radius, color in self._MARKERS:
            lx, ly = mx - 6, my - 6
            grad = QRadialGradient(QPointF(lx, ly), radius)
            glow = QColor(color)
            glow.setAlpha(150)
            grad.setColorAt(0.0, glow)
            fade = QColor(color)
            fade.setAlpha(0)
            grad.setColorAt(1.0, fade)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawEllipse(QPointF(lx, ly), radius, radius)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(lx, ly), 2.6, 2.6)

        p.restore()
        p.end()


# --------------------------------------------------------------------------
# Bàn phím — bề mặt vân nhám
# --------------------------------------------------------------------------
class KeypadPanel(QFrame):
    """Khung phím lớn, bề mặt có vân nhám nhẹ, chia thành các phần riêng."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("KeypadPanel")
        self._texture: QPixmap | None = None

    def _build_texture(self, size) -> QPixmap:
        """Vân nhám li ti — sinh một lần rồi cache (deterministic)."""
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        rng = random.Random(20240829)  # cố định hạt để vân không nhấp nháy
        for _ in range(int(size.width() * size.height() / 90)):
            x = rng.randint(0, max(size.width() - 1, 0))
            y = rng.randint(0, max(size.height() - 1, 0))
            alpha = rng.randint(4, 16)
            p.setPen(QColor(255, 255, 255, alpha))
            p.drawPoint(x, y)
        p.end()
        return pm

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._texture is None or self._texture.size() != self.size():
            self._texture = self._build_texture(self.size())
        p = QPainter(self)
        p.drawPixmap(0, 0, self._texture)
        p.end()


class KeyButton(QPushButton):
    """Một phím — navy đậm hơn nền, viền mảnh, phát sáng nhẹ khi rê chuột."""

    def __init__(self, label: str, *, kind: str = "phone", icon: bool = False) -> None:
        super().__init__(label)
        self.kind = kind
        self.setProperty("kind", kind)
        self.setObjectName("KeyButton")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(56, 44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if icon:
            self.setFont(_icon_font(15))
        if kind == "ok":
            font = self.font()
            font.setBold(True)
            font.setPointSize(11)
            self.setFont(font)


# --------------------------------------------------------------------------
# Toolbar
# --------------------------------------------------------------------------
_TOOLBAR = (
    (MDL2_PICTURE, "Mở thư mục ảnh chụp", False, "gallery"),
    (MDL2_DOWNLOAD, "Nạp tệp .vxp", False, "load_vxp"),
    (MDL2_CAMERA, "Chụp màn hình", False, "capture"),
    (MDL2_NEWFOLDER, "Tạo thư mục mới", False, "new_folder"),
    (MDL2_CAMCORDER, "Ghi lại phiên chạy", True, "record"),   # hồng, đúng VXPEmu
    (MDL2_SYNC, "Đồng bộ / khởi động lại", False, "resync"),
    (MDL2_EXPAND, "Phóng to / thu nhỏ màn hình", False, "zoom"),
)


# --------------------------------------------------------------------------
# Khung thiết bị tái sử dụng (IDE nhúng; cửa sổ standalone bọc lại)
# --------------------------------------------------------------------------
class DeviceFrameWidget(QWidget):
    """Khung thiết bị dùng để xem trước scene khi thiết kế.

    Gồm thanh công cụ 7 nút, màn hình 240x320 với bản đồ + overlay vụ án,
    thanh hướng dẫn multi-tap và bàn phím MRE. IDE nhúng widget này vào tab
    giả lập; ``FrameSimulator`` bọc nó thành cửa sổ standalone.
    """

    #: Bảng chữ multi-tap kiểu Nokia.
    _TAP = {
        "1": ".,?!1", "2": "abc", "3": "def", "4": "ghi", "5": "jkl",
        "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz", "0": " ",
        "*": "+", "#": "#",
    }
    _TAP_RESET_MS = 1200

    #: Tên phím thiết bị phát ra khi bấm cụm điều hướng / cột biên.
    _NAV_KEYS = {
        "Gạch dưới": "SOFT", "Lên": "UP", "Trái": "LEFT", "OK": "OK",
        "Phải": "RIGHT", "Xoá": "DELETE", "Xuống": "DOWN",
        "Quay lại": "BACK", "Nhập": "ENTER",
    }

    resync_requested = Signal()
    key_pressed = Signal(str)
    artifact_loaded = Signal(str)
    capture_saved = Signal(str)
    expand_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("FrameSimulator")

        self._tap_key = ""
        self._tap_count = 0
        self._tap_timer = QTimer(self)
        self._tap_timer.setSingleShot(True)
        self._tap_timer.setInterval(self._TAP_RESET_MS)
        self._tap_timer.timeout.connect(self._reset_tap)

        self._zoom = 1.0
        self._recording = False
        self._rec_dir: Path | None = None
        self._rec_frame = 0
        self._rec_timer = QTimer(self)
        self._rec_timer.setInterval(200)
        self._rec_timer.timeout.connect(self._record_frame)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())
        root.addWidget(self._build_screen_column(), 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._build_keypad(), 1)
        self.setStyleSheet(_STYLESHEET)

    @property
    def zoom(self) -> float:
        return self._zoom

    def set_status(self, text: str) -> None:
        """Dòng trạng thái dưới bàn phím (vd: artifact .vxp đã nạp)."""
        self._status.setText(text)

    # ---------------------------------------------------------------- UI

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        lay.addStretch(1)  # đẩy 7 nút sang góc trên bên phải

        self._tool_buttons: list[QPushButton] = []
        self._tool_action_buttons: dict[str, QPushButton] = {}
        for glyph, tip, accent, action in _TOOLBAR:
            btn = QPushButton(_glyph(glyph))
            btn.setObjectName("ToolButton")
            if accent:
                btn.setProperty("accent", "true")
            if action == "record":
                btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedSize(32, 30)
            if resolve_icon_font():
                btn.setFont(_icon_font(14))
            btn.clicked.connect(lambda _=False, a=action: self._on_tool(a))
            lay.addWidget(btn)
            self._tool_buttons.append(btn)
            self._tool_action_buttons[action] = btn
        return bar

    def _build_screen_column(self) -> QWidget:
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(9)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._screen = ScreenPane(col)
        lay.addWidget(self._screen, 0, Qt.AlignmentFlag.AlignCenter)

        # Thanh hướng dẫn multi-tap — ngay dưới khung nội dung.
        self._hint = QLabel("Nhấn nhiều lần: 2=abc, 3=def, 7=pqrs, 0=space")
        self._hint.setObjectName("MultiTapHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setFixedHeight(24)
        lay.addWidget(self._hint)

        self._status = QLabel("Bản xem trước thiết kế sẵn sàng.")
        self._status.setObjectName("MultiTapHint")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)
        return col

    def _build_keypad(self) -> QWidget:
        panel = KeypadPanel()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)

        # --- Trái: lưới 3×3 số + hàng * / 0 ---
        row.addLayout(self._build_digits(), 3)

        # --- Giữa: cụm điều hướng _ ↑ / ← OK → / 🗑 ↓ ---
        row.addLayout(self._build_nav_cluster(), 3)

        # --- Phải ngoài cùng: cột dọc _ ← #⏎ ---
        row.addLayout(self._build_side_column(), 1)

        outer.addLayout(row)
        outer.addStretch(1)
        return panel

    def _build_digits(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)
        labels = ["1", "2 abc", "3 def", "4 ghi", "5 jkl", "6 mno",
                  "7 pqrs", "8 tuv", "9 wxyz"]
        for index, text in enumerate(labels):
            r, c = divmod(index, 3)
            btn = KeyButton(text, kind="phone")
            btn.clicked.connect(lambda _=False, t=text: self._on_digit(t))
            grid.addWidget(btn, r, c)

        box.addLayout(grid)

        # Hai phím rộng hơn ngay dưới lưới.
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        for text in ("*", "0"):
            btn = KeyButton(text, kind="phone")
            btn.setProperty("wide", "true")
            btn.clicked.connect(lambda _=False, t=text: self._on_digit(t))
            bottom.addWidget(btn)
        box.addLayout(bottom)
        return box

    def _build_nav_cluster(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(6)
        # (hàng, cột, nhãn, kind, có_icon, tooltip)
        spec = (
            (0, 0, "_", "nav", False, "Gạch dưới"),
            (0, 1, MDL2_UP, "nav", True, "Lên"),
            (1, 0, MDL2_LEFT, "nav", True, "Trái"),
            (1, 1, "OK", "ok", False, "Xác nhận"),
            (1, 2, MDL2_RIGHT, "nav", True, "Phải"),
            (2, 0, MDL2_DELETE, "nav", True, "Xoá"),
            (2, 1, MDL2_DOWN, "nav", True, "Xuống"),
        )
        for r, c, label, kind, is_icon, tip in spec:
            shown = _glyph(label) if is_icon else label
            btn = KeyButton(shown, kind=kind, icon=is_icon)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, t=tip: self._on_nav(t))
            grid.addWidget(btn, r, c)
        return grid

    def _build_side_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(6)
        spec = (
            ("_", False, "Gạch dưới"),
            (MDL2_LEFT, True, "Quay lại"),
        )
        for label, is_icon, tip in spec:
            btn = KeyButton(_glyph(label) if is_icon else label, kind="side",
                            icon=is_icon)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, t=tip: self._on_nav(t))
            col.addWidget(btn)

        # Phím # với mũi tên xuống dòng — hai dòng trong một phím.
        enter = QPushButton("#\n" + _glyph(MDL2_ENTER))
        enter.setObjectName("KeyButton")
        enter.setProperty("kind", "side")
        enter.setCursor(Qt.CursorShape.PointingHandCursor)
        enter.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        enter.setMinimumSize(56, 44)
        enter.setToolTip("Xuống dòng")
        enter.clicked.connect(lambda _=False: self._on_nav("Nhập"))
        col.addWidget(enter)
        return col

    # ------------------------------------------------------------- tương tác

    def _on_tool(self, action: str) -> None:
        handlers = {
            "gallery": self._tool_gallery,
            "load_vxp": self._tool_load_vxp,
            "capture": self._tool_capture,
            "new_folder": self._tool_new_folder,
            "record": self._tool_record,
            "resync": self._tool_resync,
            "zoom": self._tool_zoom,
        }
        handler = handlers.get(action)
        if handler is not None:
            handler()

    def _on_nav(self, tip: str) -> None:
        self._reset_tap()
        key = self._NAV_KEYS.get(tip, tip.upper())
        if key == "DELETE":
            if self._screen.subject:
                self._screen.set_subject(self._screen.subject[:-1])
                self._flash_hint(f"Xoá — Subject: {self._screen.subject or '(trống)'}")
            else:
                self._flash_hint("Xoá — Subject đang trống")
        elif key == "OK":
            self._flash_hint(f"OK — Subject: {self._screen.subject or '(trống)'}")
        else:
            self._flash_hint(f"Phím: {tip}")
        self.key_pressed.emit(key)

    # ------------------------------------------------------------- toolbar

    def _captures_dir(self) -> Path:
        root = Path.home() / "Pictures" / "VXPEngine"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _open_in_explorer(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _tool_gallery(self) -> None:
        folder = self._captures_dir()
        self._open_in_explorer(folder)
        self._flash_hint(f"Thư mục ảnh chụp: {folder}")

    def _tool_load_vxp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Nạp tệp .vxp", str(Path.home()),
            "Gói ARM VXP (*.vxp);;Tất cả (*.*)",
        )
        if not path:
            return
        name = Path(path).name
        self.set_status(f"Đã nạp {name} vào bản xem trước thiết kế.")
        self.artifact_loaded.emit(path)

    def _tool_capture(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self._captures_dir() / f"screen_{stamp}.png"
        if self._screen.grab().save(str(target), "PNG"):
            self._flash_hint(f"Đã chụp màn hình: {target.name}")
            self.capture_saved.emit(str(target))
        else:
            self._flash_hint("Không chụp được màn hình.")

    def _tool_new_folder(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self._captures_dir() / f"capture_{stamp}"
        folder.mkdir(parents=True, exist_ok=True)
        self._open_in_explorer(folder)
        self._flash_hint(f"Thư mục mới: {folder.name}")

    def _tool_resync(self) -> None:
        self._flash_hint("Đang đồng bộ với IDE…")
        self.resync_requested.emit()

    def _tool_zoom(self) -> None:
        self._zoom = 1.0 if self._zoom > 1.0 else 2.0
        self._screen.set_zoom(self._zoom)
        self._flash_hint(f"Thu phóng màn hình: {int(self._zoom * 100)}%")
        self.expand_requested.emit()

    def _tool_record(self) -> None:
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._rec_dir = self._captures_dir() / f"record_{stamp}"
        self._rec_dir.mkdir(parents=True, exist_ok=True)
        self._rec_frame = 0
        self._recording = True
        self._rec_timer.start()
        self._set_record_button(True)
        self._flash_hint("Đang ghi phiên chạy… (bấm lại để dừng)")

    def _record_frame(self) -> None:
        if self._rec_dir is None:
            return
        self._screen.grab().save(str(self._rec_dir / f"frame_{self._rec_frame:04d}.png"), "PNG")
        self._rec_frame += 1

    def _stop_recording(self) -> None:
        self._rec_timer.stop()
        self._recording = False
        self._set_record_button(False)
        folder, frames = self._rec_dir, self._rec_frame
        self._rec_dir = None
        if folder is None or frames == 0:
            self._flash_hint("Không có khung hình nào được ghi.")
            return
        video = self._encode_video(folder)
        if video is not None:
            self._flash_hint(f"Đã ghi video: {video.name}")
            self.capture_saved.emit(str(video))
        else:
            self._flash_hint(f"Đã ghi {frames} khung hình vào {folder.name} (thiếu ffmpeg để ghép video).")

    def _encode_video(self, folder: Path) -> Path | None:
        ffmpeg = Path(__file__).resolve().parent.parent / "libs" / "ffmpeg.exe"
        if not ffmpeg.is_file():
            return None
        out = folder.parent / f"{folder.name}.mp4"
        args = [
            str(ffmpeg), "-y", "-framerate", "5",
            "-i", str(folder / "frame_%04d.png"),
            "-pix_fmt", "yuv420p", str(out),
        ]
        try:
            subprocess.run(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120, check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return out if out.is_file() else None

    def _set_record_button(self, on: bool) -> None:
        btn = self._tool_action_buttons.get("record")
        if btn is not None:
            btn.setChecked(on)

    def _on_digit(self, text: str) -> None:
        """Gõ multi-tap: bấm lặp cùng phím chạy tiếp chuỗi chữ."""
        ch = text.split(" ", 1)[0]          # "2 abc" -> "2"
        letters = self._TAP.get(ch, "")
        if not letters:
            return
        if ch == self._tap_key:
            self._tap_count += 1
        else:
            self._tap_key = ch
            self._tap_count = 1
        index = (self._tap_count - 1) % len(letters)
        chosen = letters[index]
        shown = "space" if chosen == " " else chosen

        self._flash_hint(f"{ch} → {shown}   letter {self._tap_count}/{len(letters)}")

        # Phím 0 = space, các phím khác nối chữ vào Subject.
        if chosen != " ":
            self._screen.set_subject(self._screen.subject + chosen.upper())
        self._tap_timer.start()

    def _flash_hint(self, text: str) -> None:
        self._hint.setObjectName("MultiTapHintActive")
        self._hint.style().unpolish(self._hint)
        self._hint.style().polish(self._hint)
        self._hint.setText(text)

    def _reset_tap(self) -> None:
        self._tap_key = ""
        self._tap_count = 0
        self._hint.setObjectName("MultiTapHint")
        self._hint.style().unpolish(self._hint)
        self._hint.style().polish(self._hint)
        self._hint.setText("Nhấn nhiều lần: 2=abc, 3=def, 7=pqrs, 0=space")


# --------------------------------------------------------------------------
# QSS
# --------------------------------------------------------------------------
_STYLESHEET = f"""
QMainWindow, QWidget#FrameSimulator {{
    background: {C_BG_DEEP};
}}
QWidget#Toolbar {{
    background: {C_BG};
    border-bottom: 1px solid {C_BORDER_SOFT};
}}
QPushButton#ToolButton {{
    background: transparent;
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT_DIM};
    padding: 0px;
}}
QPushButton#ToolButton:hover {{
    background: {C_KEY_HOVER};
    border-color: {C_ACCENT};
    color: {C_ACCENT};
}}
QPushButton#ToolButton[accent="true"] {{
    color: {C_RECORD};
}}
QPushButton#ToolButton[accent="true"]:hover {{
    background: {C_RECORD};
    border-color: {C_RECORD};
    color: #0b0f16;
}}
QPushButton#ToolButton[accent="true"]:checked {{
    background: {C_RECORD};
    border-color: {C_RECORD};
    color: #0b0f16;
}}

QFrame#ScreenPane {{
    background: {C_SCREEN};
    border: 1px solid {C_BORDER};
    border-radius: 3px;
}}
QWidget#ScreenOverlay {{
    background: transparent;
}}
QLabel#OverlayLine {{
    color: #9dc9ff;
    font-family: "Consolas", "Cascadia Mono", monospace;
    background: transparent;
}}
QLabel#OverlayCaret {{
    color: {C_ACCENT};
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-weight: 700;
    background: transparent;
}}

QLabel#MultiTapHint, QLabel#MultiTapHintActive {{
    background: {C_KEY};
    border: 1px solid {C_BORDER_SOFT};
    border-radius: 4px;
    color: {C_TEXT_DIM};
    font-size: 11px;
    letter-spacing: 0.3px;
}}
QLabel#MultiTapHintActive {{
    color: {C_TEXT};
    border-color: {C_ACCENT_2};
}}

QFrame#KeypadPanel {{
    background: {C_BG};
    border-top: 1px solid {C_BORDER_SOFT};
}}
QPushButton#KeyButton {{
    background: {C_KEY};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    color: {C_TEXT};
    font-size: 13px;
    padding: 4px 2px;
}}
QPushButton#KeyButton:hover {{
    background: {C_KEY_HOVER};
    border-color: #3b4a68;
}}
QPushButton#KeyButton:pressed {{
    background: #0a0e15;
    border-color: {C_ACCENT};
}}
QPushButton#KeyButton[kind="ok"] {{
    background: {C_KEY_OK};
    color: {C_TEXT};
    font-weight: 700;
    border-color: #2f3b55;
}}
QPushButton#KeyButton[kind="ok"]:hover {{
    background: #222c3f;
    border-color: {C_ACCENT};
}}
QPushButton#KeyButton[kind="nav"], QPushButton#KeyButton[kind="side"] {{
    color: {C_TEXT_DIM};
}}
"""


class FrameSimulator(QMainWindow):
    """Cửa sổ standalone bọc DeviceFrameWidget (chạy trực tiếp hoặc từ IDE)."""

    _BASE_W = 520
    _BASE_H = 782

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VXPEmu — Frame Simulator")
        self.frame = DeviceFrameWidget(self)
        self.setCentralWidget(self.frame)
        self.frame.expand_requested.connect(self._fit_window)
        self._fit_window()

    def _fit_window(self) -> None:
        extra_w = int(ScreenPane.SCREEN_W * (self.frame.zoom - 1))
        extra_h = int(ScreenPane.SCREEN_H * (self.frame.zoom - 1))
        self.setFixedSize(self._BASE_W + extra_w, self._BASE_H + extra_h)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = FrameSimulator()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
