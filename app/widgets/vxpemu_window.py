"""Separate Nokia 225 shell hosting VXPEmu's real framebuffer window."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QDateTime, QProcess, QRectF, QSize, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QGuiApplication, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout,
    QWidget,
)

import native_window
import ffmpeg_tool
from .custom_dialog import FilePickerDialog
from .icons import icon

PORTRAIT = "portrait"
LANDSCAPE = "landscape"
SCREEN_SIZE = {PORTRAIT: (240, 320), LANDSCAPE: (320, 240)}


class ScreenHost(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.setFixedSize(240, 320)
        self.message = "Đang chờ VXPEmu…"
        self.live = False

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#07090d"))
        if self.live:
            return
        painter.setPen(QColor("#4676b2"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(8, 80, -8, -155), Qt.AlignmentFlag.AlignCenter, "NOKIA")
        painter.setPen(QColor("#76869e"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(self.rect().adjusted(10, 110, -10, -105),
                         Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
                         "225 DUAL SIM\n\n" + self.message)


class PhoneKeypad(QWidget):
    key_pressed = Signal(int)
    KEYS = (
        ("", native_window.MRE_KEY_LEFT_SOFT), ("▲", native_window.MRE_KEY_UP),
        ("", native_window.MRE_KEY_RIGHT_SOFT), ("◀", native_window.MRE_KEY_LEFT),
        ("OK", native_window.MRE_KEY_OK), ("▶", native_window.MRE_KEY_RIGHT),
        ("", -1), ("▼", native_window.MRE_KEY_DOWN), ("", -1),
        *((str(n), 0x30 + n) for n in range(1, 10)),
        ("*", 0x2A), ("0", 0x30), ("#", 0x23),
    )
    SOFT_KEY_ICONS = {
        native_window.MRE_KEY_LEFT_SOFT: ("fa5s.align-left", "Phím mềm trái"),
        native_window.MRE_KEY_RIGHT_SOFT: ("fa5s.align-right", "Phím mềm phải"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.buttons: list[QPushButton] = []
        for index, (label, code) in enumerate(self.KEYS):
            row, column = divmod(index, 3)
            if code < 0:
                layout.addWidget(QWidget(), row, column)
                continue
            button = QPushButton(label)
            button.setFixedSize(76, 24)
            button.setProperty("mreKeyCode", code)
            soft_key = self.SOFT_KEY_ICONS.get(code)
            if soft_key is not None:
                icon_name, description = soft_key
                button.setIcon(icon(icon_name, "#DCE7F7"))
                button.setIconSize(QSize(15, 15))
                button.setToolTip(description)
                button.setAccessibleName(description)
            button.clicked.connect(lambda _checked=False, value=code: self.key_pressed.emit(value))
            layout.addWidget(button, row, column)
            self.buttons.append(button)
        self.setFixedSize(234, 186)


class PhoneBody(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.orientation = PORTRAIT
        self.screen = ScreenHost(self)
        self.keypad = PhoneKeypad(self)
        self.set_orientation(PORTRAIT)

    def set_orientation(self, orientation: str) -> None:
        self.orientation = orientation if orientation in SCREEN_SIZE else PORTRAIT
        sw, sh = SCREEN_SIZE[self.orientation]
        self.screen.setFixedSize(sw, sh)
        if self.orientation == PORTRAIT:
            width, height = 268, 42 + sh + 12 + self.keypad.height() + 14
            self.screen.setGeometry((width - sw) // 2, 42, sw, sh)
            self.keypad.setGeometry((width - self.keypad.width()) // 2, 42 + sh + 12,
                                     self.keypad.width(), self.keypad.height())
        else:
            width, height = 14 + sw + 12 + self.keypad.width() + 14, 42 + max(sh, self.keypad.height()) + 14
            self.screen.setGeometry(14, 42, sw, sh)
            self.keypad.setGeometry(14 + sw + 12, 42 + (sh - self.keypad.height()) // 2,
                                     self.keypad.width(), self.keypad.height())
        self.setFixedSize(width, height)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor("#2b3444"))
        gradient.setColorAt(1, QColor("#151c27"))
        painter.setPen(QPen(QColor("#435069"), 1.5))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, 20, 20)
        screen = self.screen.geometry()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#090d14"))
        painter.drawRoundedRect(QRectF(screen).adjusted(-5, -5, 5, 5), 5, 5)
        painter.setBrush(QColor("#080b11"))
        screen_center = screen.center().x()
        painter.drawRoundedRect(QRectF(screen_center - 25, 13, 50, 5), 2.5, 2.5)
        painter.setPen(QColor("#8492aa"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(screen.left(), 21, screen.width(), 15),
                         Qt.AlignmentFlag.AlignCenter, "NOKIA")


class VxpEmuWindow(QWidget):
    restart_requested = Signal()
    stop_requested = Signal()
    load_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Nokia 225 Dual SIM — VXPEmu")
        self.setObjectName("VxpEmuPhoneWindow")
        self._pid = 0
        self._hwnd: int | None = None
        self._attempts = 0
        self._artifact = ""
        self._closing_for_shutdown = False
        self._record_dir: Path | None = None
        self._record_frame = 0
        self._record_output: Path | None = None
        self._encoder: QProcess | None = None
        self._attach_timer = QTimer(self)
        self._attach_timer.setInterval(300)
        self._attach_timer.timeout.connect(self._try_attach)
        self._fit_timer = QTimer(self)
        self._fit_timer.setInterval(400)
        self._fit_timer.timeout.connect(self._fit)
        self._record_timer = QTimer(self)
        self._record_timer.setInterval(100)
        self._record_timer.timeout.connect(self._capture_record_frame)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("PhoneWindowBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        title = QLabel("NOKIA 225")
        title.setStyleSheet("font-weight:700;color:#f0f4fb")
        bar_layout.addWidget(title)
        bar_layout.addStretch()
        root.addWidget(bar)

        tools = QWidget()
        tools.setObjectName("PhoneToolBar")
        tools_layout = QHBoxLayout(tools)
        tools_layout.setContentsMargins(10, 4, 10, 6)
        tools_layout.setSpacing(5)

        def tool_button(icon_name: str, tooltip: str, callback, color: str = "#aab4c6") -> QToolButton:
            button = QToolButton()
            button.setIcon(icon(icon_name, color))
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(39, 36)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            tools_layout.addWidget(button)
            return button

        self.run_button = tool_button("fa5s.play", "Chạy / dừng VXP hiện tại", self._toggle_run, "#65dc96")
        self.import_button = tool_button("fa5s.download", "Nạp một tệp .vxp khác", self._choose_vxp)
        self.screenshot_button = tool_button("fa5s.camera", "Chụp màn hình VXP", self.capture_screenshot)
        self.open_shots_button = tool_button("fa5s.folder-open", "Mở thư mục ảnh/video đã chụp", self.open_capture_folder)
        self.record_button = tool_button("fa5s.video", "Bắt đầu/dừng quay video", self.toggle_recording, "#fb7185")
        self.record_button.setCheckable(True)
        self.rotate_button = tool_button("fa5s.sync-alt", "Xoay 240×320 / 320×240", self.toggle_orientation)
        self.fullscreen_button = tool_button("fa5s.expand-alt", "Toàn màn hình", self.toggle_fullscreen)
        tools_layout.addStretch()
        root.addWidget(tools)

        stage = QWidget()
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(14, 14, 14, 8)
        self.body = PhoneBody()
        stage_layout.addWidget(self.body, 0, Qt.AlignmentFlag.AlignCenter)
        root.addWidget(stage)
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(10, 5, 10, 8)
        hint = QLabel("Bấm phím trên vỏ máy để gửi phím MRE")
        hint.setStyleSheet("color:#7788a2")
        self.status = QLabel("Chưa chạy")
        self.status.setStyleSheet("color:#91a6c5")
        footer_layout.addWidget(hint, 1)
        footer_layout.addWidget(self.status)
        root.addWidget(footer)

        self.body.keypad.key_pressed.connect(self.send_key)
        self.setStyleSheet("""
            #VxpEmuPhoneWindow, #PhoneWindowBar, #PhoneToolBar { background:#0d121b; color:#dce7f7; }
            QToolButton { background:#171f2c; color:#cbd7e8; border:1px solid #2c394e;
                          border-radius:5px; padding:5px 9px; }
            QToolButton:hover { background:#202b3c; }
            QPushButton { background:#34445d; color:white; border:1px solid #506685;
                          border-radius:4px; font-size:11px; }
            QPushButton:pressed { background:#4e6c96; }
        """)
        self._fit_shell()

    def attach_process(self, artifact: str, pid: int) -> None:
        self._pid, self._hwnd, self._attempts = int(pid), None, 0
        self._artifact = str(artifact)
        self.run_button.setIcon(icon("fa5s.stop", "#fb7185"))
        self.body.screen.live = False
        self.body.screen.message = "Đang khởi động VXPEmu…"
        self.status.setText(f"{Path(artifact).name} · PID {pid}")
        self.show()
        self.raise_()
        self.activateWindow()
        self._attach_timer.start()

    def _try_attach(self) -> None:
        self._attempts += 1
        hwnd = native_window.find_main_window(self._pid)
        if hwnd and native_window.embed(hwnd, int(self.body.screen.winId()),
                                        self.body.screen.width(), self.body.screen.height()):
            self._hwnd = hwnd
            self._attach_timer.stop()
            self._fit_timer.start()
            self.body.screen.live = True
            self.body.screen.update()
            self.status.setText(f"Đang chạy · {self.body.screen.width()}×{self.body.screen.height()}")
        elif self._attempts >= 50:
            self._attach_timer.stop()
            self.status.setText("Không tìm thấy cửa sổ VXPEmu")

    def toggle_orientation(self) -> None:
        target = LANDSCAPE if self.body.orientation == PORTRAIT else PORTRAIT
        self.set_orientation(target)

    def set_orientation(self, orientation: str) -> None:
        self.body.set_orientation(orientation)
        if not self.isFullScreen():
            self._fit_shell()
        self._fit()
        if self._pid:
            self.status.setText(
                f"Đang chạy · {self.body.screen.width()}×{self.body.screen.height()}"
            )

    def _fit_shell(self) -> None:
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.body.updateGeometry()
        stage = self.body.parentWidget()
        if stage is not None:
            if stage.layout() is not None:
                stage.layout().invalidate()
            stage.updateGeometry()
        self.layout().invalidate()
        self.layout().activate()
        size = self.sizeHint()
        self.setFixedSize(size)

    def _fit(self) -> None:
        if self._hwnd:
            native_window.fit(
                self._hwnd,
                self.body.screen.width(),
                self.body.screen.height(),
                int(self.body.screen.winId()),
            )

    def _toggle_run(self) -> None:
        if self._pid:
            self.stop_requested.emit()
        else:
            self.restart_requested.emit()

    def _choose_vxp(self) -> None:
        start = Path(self._artifact).parent if self._artifact else Path.home()
        selected = FilePickerDialog.get_open_file_name(
            self, "Nạp ứng dụng VXP", start, "Ứng dụng MRE VXP (*.vxp)"
        )
        if selected:
            self.load_requested.emit(selected)

    @staticmethod
    def capture_directory() -> Path:
        pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
        target = Path(pictures or str(Path.home() / "Pictures")) / "VXPEmu"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _grab_screen(self):
        screen = self.body.screen.screen() or QGuiApplication.primaryScreen()
        return screen.grabWindow(int(self.body.screen.winId())) if screen is not None else None

    def capture_screenshot(self) -> None:
        pixmap = self._grab_screen()
        if pixmap is None or pixmap.isNull():
            self.status.setText("Không chụp được màn hình VXPEmu")
            return
        stamp = QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        output = self.capture_directory() / f"VXPEmu-{stamp}.png"
        if pixmap.save(str(output), "PNG"):
            self.status.setText(f"Đã chụp · {output.name}")
        else:
            self.status.setText("Lưu ảnh chụp thất bại")

    def open_capture_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.capture_directory())))

    def toggle_recording(self) -> None:
        if self._record_timer.isActive():
            self._stop_recording()
            return
        if not self._hwnd:
            self.record_button.setChecked(False)
            self.status.setText("Hãy chạy VXP trước khi quay")
            return
        if ffmpeg_tool.ffmpeg_path() is None:
            self.record_button.setChecked(False)
            self.status.setText("Không tìm thấy ffmpeg để quay video")
            return
        self._record_dir = Path(tempfile.mkdtemp(prefix="vxpemu-record-"))
        self._record_frame = 0
        stamp = QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        self._record_output = self.capture_directory() / f"VXPEmu-{stamp}.mp4"
        self.record_button.setChecked(True)
        self._record_timer.start()
        self.status.setText("Đang quay · 10 FPS")

    def _capture_record_frame(self) -> None:
        if self._record_dir is None:
            return
        pixmap = self._grab_screen()
        if pixmap is None or pixmap.isNull():
            return
        self._record_frame += 1
        pixmap.save(str(self._record_dir / f"frame-{self._record_frame:06d}.png"), "PNG")

    def _stop_recording(self) -> None:
        self._record_timer.stop()
        self.record_button.setChecked(False)
        if self._record_dir is None or self._record_output is None or self._record_frame == 0:
            self._discard_recording()
            return
        ffmpeg = ffmpeg_tool.ffmpeg_path()
        if ffmpeg is None:
            self._discard_recording()
            return
        self.status.setText("Đang lưu video…")
        encoder = QProcess(self)
        encoder.setProgram(str(ffmpeg))
        encoder.setArguments([
            "-y", "-framerate", "10", "-i", str(self._record_dir / "frame-%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(self._record_output),
        ])
        encoder.finished.connect(self._recording_encoded)
        self._encoder = encoder
        encoder.start()

    def _recording_encoded(self, code: int, _status) -> None:
        output = self._record_output
        ok = code == 0 and output is not None and output.is_file()
        self._discard_recording()
        self.status.setText(f"Đã lưu · {output.name}" if ok and output else "Lưu video thất bại")

    def _discard_recording(self) -> None:
        if self._record_dir is not None:
            shutil.rmtree(self._record_dir, ignore_errors=True)
        self._record_dir = None
        self._record_output = None
        self._record_frame = 0
        self._encoder = None

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self._fit_shell()
            self.fullscreen_button.setIcon(icon("fa5s.expand-alt", "#aab4c6"))
            self.fullscreen_button.setToolTip("Toàn màn hình")
        else:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.showFullScreen()
            self.fullscreen_button.setIcon(icon("fa5s.compress-alt", "#aab4c6"))
            self.fullscreen_button.setToolTip("Thoát toàn màn hình")

    def send_key(self, code: int) -> None:
        if self._hwnd:
            native_window.send_key(self._hwnd, code)

    def process_stopped(self, code: int) -> None:
        self._attach_timer.stop()
        self._fit_timer.stop()
        self._pid, self._hwnd = 0, None
        self.body.screen.live = False
        self.body.screen.message = "VXPEmu đã dừng"
        self.body.screen.update()
        self.run_button.setIcon(icon("fa5s.play", "#65dc96"))
        if self._record_timer.isActive():
            self._stop_recording()
        self.status.setText(f"Đã dừng · code {code}")

    def closeEvent(self, event) -> None:
        if not self._closing_for_shutdown and self._pid:
            self.stop_requested.emit()
        event.accept()

    def shutdown(self) -> None:
        self._closing_for_shutdown = True
        self._attach_timer.stop()
        self._fit_timer.stop()
        self._record_timer.stop()
        self._discard_recording()
        self.close()
