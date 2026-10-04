"""2Dutiful Engine desktop shell with Home dashboard and 2D workspace."""
from __future__ import annotations

import ctypes
import faulthandler
import json
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCursor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSplitter,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from adb_manager import AdbDeviceManager
from feature_audit import audit_engine_source, format_audit_summary, summarize_findings
from libgdx_runner import LibGDXRunner
from project_store import ENGINE_VERSION, ProjectInfo, ProjectStore
from widgets import panels
from widgets.asset_editor import AssetEditorDialog
from widgets.code_editor import CodeEditor
from widgets.custom_dialog import ConfirmDialog, CustomDialog, FilePickerDialog, NoticeDialog, RunSessionDialog, TextInputDialog
from widgets.documentation_page import DocumentationPage
from widgets.home_page import HomePage
from widgets.icons import app_icon, icon
from widgets.log_format import append_colored_log
from widgets.new_project_dialog import NewProjectDialog
from widgets.keyframe_editor import KeyframeEditorWindow
from widgets.panel_frame import PanelFrame
from widgets.task_progress import BottomTaskProgress
from widgets.title_bar import CustomTitleBar
from widgets.viewport import Viewport2D
from scene_screen_store import ScreenInfo, ScreenStore
from update_checker import UpdateChecker
from window_state import WindowStateController
from widgets.toast import AppToast


RESIZE_MARGIN = 6
_CRASH_LOG_HANDLE = None

BUILD_TARGETS = (
    ("Compile Java (core + lwjgl3)", "fa5s.code", "compile"),
    ("Desktop JAR (LWJGL3)", "fa5s.desktop", "lwjgl3:dist"),
    ("Desktop JAR + JAD", "fa5s.file-alt", "desktop_jad"),
    ("Android APK Debug", "fa5s.mobile-alt", "android:assembleDebug"),
    ("Android APK Release", "fa5b.android", "android:assembleRelease"),
    ("Android AAB Release", "fa5s.archive", "android:bundleRelease"),
    ("C/C++ Native DLL", "fa5s.microchip", "native"),
    ("Clean Project", "fa5s.broom", "clean"),
)

JAVA_SAMPLE_CODE = """package com.dutiful2d.ten_project;

import com.badlogic.gdx.ApplicationAdapter;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.graphics.GL20;

public final class DutifulGame extends ApplicationAdapter {
    @Override
    public void create() {
        // Empty starter project: add game systems here.
    }

    @Override
    public void render() {
        Gdx.gl.glClearColor(0.055f, 0.075f, 0.11f, 1f);
        Gdx.gl.glClear(GL20.GL_COLOR_BUFFER_BIT);
    }
}
"""


class EventMappingDialog(CustomDialog):
    """Frameless editor for basic scene-node events."""

    def __init__(self, screens: list[ScreenInfo], payload: dict, parent=None) -> None:
        super().__init__("Ánh xạ sự kiện cơ bản", parent, width=540, height=430, resizable=False, modal=True)
        self.result_mapping: dict | None = None
        title = QLabel(f"Thành phần: {payload.get('name', 'Node')}")
        title.setObjectName("DialogSectionTitle")
        self.body_layout.addWidget(title)
        form = QFormLayout()
        self.trigger = QComboBox()
        self.trigger.addItem("Nhấn / click", "on_click")
        self.trigger.addItem("Chạm / touch", "on_touch")
        self.trigger.addItem("Va chạm / overlap", "on_overlap")
        self.trigger.addItem("Đi vào vùng", "on_enter")
        self.trigger.addItem("Rời vùng", "on_exit")
        self.trigger.addItem("Hoàn tất animation", "on_animation_complete")
        preset = str(payload.get("preset_trigger", ""))
        for index in range(self.trigger.count()):
            if self.trigger.itemData(index) == preset:
                self.trigger.setCurrentIndex(index)
                break
        self.action = QComboBox()
        self.action.addItem("Chuyển sang màn khác", "change_screen")
        self.action.addItem("Bật/tắt hiển thị", "toggle_visible")
        self.action.addItem("Phát animation", "play_animation")
        self.action.addItem("Đặt thuộc tính", "set_property")
        self.action.addItem("Phát tín hiệu gameplay", "emit_signal")
        self.target = QComboBox()
        self.target.addItem("— Không chọn —", "")
        for screen in screens:
            self.target.addItem(screen.name, screen.id)
        self.parameter = QLineEdit()
        self.parameter.setPlaceholderText("Ví dụ: run, opacity=0.5, open_shop")
        self.enabled = QCheckBox("Bật sự kiện")
        self.enabled.setChecked(True)
        form.addRow("Kích hoạt", self.trigger)
        form.addRow("Hành động", self.action)
        form.addRow("Màn đích", self.target)
        form.addRow("Tham số", self.parameter)
        form.addRow("Trạng thái", self.enabled)
        self.body_layout.addLayout(form)
        note = QLabel("Dữ liệu được lưu trực tiếp trong node .dtfe và tự sinh vào DutifulSceneBindings.java.")
        note.setWordWrap(True)
        note.setObjectName("DialogHint")
        self.body_layout.addWidget(note)
        cancel = QPushButton("Hủy")
        cancel.clicked.connect(self.reject)
        apply_button = QPushButton("Áp dụng")
        apply_button.setObjectName("PrimaryAction")
        apply_button.clicked.connect(self._accept_mapping)
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(apply_button)

    def _accept_mapping(self) -> None:
        self.result_mapping = {
            "trigger": str(self.trigger.currentData() or "on_click"),
            "action": str(self.action.currentData() or "change_screen"),
            "target_screen": str(self.target.currentData() or ""),
            "parameter": self.parameter.text().strip(),
            "enabled": self.enabled.isChecked(),
        }
        self.accept()

    @classmethod
    def get_mapping(cls, screens: list[ScreenInfo], payload: dict, parent=None) -> dict | None:
        dialog = cls(screens, payload, parent)
        return dialog.result_mapping if dialog.exec() == QDialog.DialogCode.Accepted else None


class AutomationMappingDialog(CustomDialog):
    """Map any visual component to an optional runtime automation role.

    Mapping is metadata-driven: users can still write custom Java gameplay, while
    the generated runtime exposes standard input, collider and semantic queries.
    """

    ROLE_PRESETS = (
        ("Không tự động hóa / dùng code", "custom"),
        ("Nhân vật người chơi", "player"),
        ("Joystick ảo", "virtual_joystick"),
        ("Nút hướng", "direction_button"),
        ("Nút hành động", "action_button"),
        ("Nút kỹ năng", "skill_button"),
        ("Ground / nền va chạm", "ground"),
        ("Platform một chiều", "one_way_platform"),
        ("Vật cản tĩnh", "static_obstacle"),
        ("Vùng nguy hiểm", "hazard"),
        ("Vùng Trigger / Sensor", "trigger_zone"),
        ("Cổng chuyển map", "portal"),
        ("Vật phẩm thu thập", "collectible"),
        ("Kẻ địch", "enemy"),
        ("Điểm sinh nhân vật", "spawn_point"),
        ("Camera Follow Target", "camera_target"),
        ("Trang trí / không gameplay", "decoration"),
    )

    def __init__(self, screens: list[ScreenInfo], payload: dict, parent=None) -> None:
        super().__init__("Ánh xạ vai trò & tự động hóa", parent, width=610, height=650, resizable=True, modal=True)
        self.result_mapping: dict | None = None
        current = payload.get("automation") if isinstance(payload.get("automation"), dict) else {}
        title = QLabel(f"Thành phần: {payload.get('name', 'Node')}")
        title.setObjectName("DialogSectionTitle")
        self.body_layout.addWidget(title)

        form = QFormLayout()
        self.role = QComboBox()
        for label, value in self.ROLE_PRESETS:
            self.role.addItem(label, value)
        current_role = str(current.get("role") or payload.get("ui_role") or "custom")
        aliases = {
            "VirtualJoystick": "virtual_joystick", "VirtualJoystickLeft": "virtual_joystick",
            "VirtualJoystickRight": "virtual_joystick", "DirectionButton": "direction_button",
            "JumpButton": "action_button", "RunButton": "action_button", "ActionButton": "action_button",
            "SkillButton": "skill_button", "Ground": "ground", "OneWayPlatform": "one_way_platform",
            "StaticObstacle": "static_obstacle", "HazardZone": "hazard", "TriggerZone": "trigger_zone",
            "Portal": "portal", "Collectible": "collectible", "Player": "player", "Enemy": "enemy",
            "SpawnPoint": "spawn_point", "CameraTarget": "camera_target", "Decoration": "decoration",
        }
        current_role = aliases.get(current_role, current_role)
        for index in range(self.role.count()):
            if self.role.itemData(index) == current_role:
                self.role.setCurrentIndex(index); break

        self.input_action = QComboBox()
        for label, value in (
            ("— Không gán —", ""), ("Di chuyển 2 trục", "MOVE_AXIS"),
            ("Trái", "MOVE_LEFT"), ("Phải", "MOVE_RIGHT"), ("Lên", "MOVE_UP"), ("Xuống", "MOVE_DOWN"),
            ("Nhảy", "JUMP"), ("Chạy nhanh", "RUN"), ("Tấn công", "ATTACK"),
            ("Kỹ năng 1", "SKILL_1"), ("Kỹ năng 2", "SKILL_2"), ("Kỹ năng 3", "SKILL_3"),
            ("Tương tác", "INTERACT"), ("Tạm dừng", "PAUSE"), ("Tùy chỉnh…", "__custom__"),
        ):
            self.input_action.addItem(label, value)
        existing_input = str(current.get("input_action") or payload.get("input_binding") or "")
        found_input = False
        for index in range(self.input_action.count()):
            if self.input_action.itemData(index) == existing_input:
                self.input_action.setCurrentIndex(index); found_input = True; break
        if existing_input and not found_input:
            for index in range(self.input_action.count()):
                if self.input_action.itemData(index) == "__custom__":
                    self.input_action.setCurrentIndex(index); break
        self.custom_input = QLineEdit(existing_input if existing_input and not found_input else "")
        self.custom_input.setPlaceholderText("Ví dụ: DASH, OPEN_INVENTORY")

        self.axis = QComboBox()
        self.axis.addItem("Cả hai trục X/Y", "both")
        self.axis.addItem("Chỉ trục ngang X", "x")
        self.axis.addItem("Chỉ trục dọc Y", "y")
        axis_value = str(current.get("axis", "both"))
        for index in range(self.axis.count()):
            if self.axis.itemData(index) == axis_value:
                self.axis.setCurrentIndex(index); break

        self.physics = QComboBox()
        for label, value in (
            ("Không tạo collider tự động", "none"), ("Static collider", "static"),
            ("Dynamic body", "dynamic"), ("Kinematic body", "kinematic"),
            ("Sensor / Trigger", "sensor"), ("One-way platform", "one_way"),
        ):
            self.physics.addItem(label, value)
        physics_value = str(current.get("physics", "none"))
        for index in range(self.physics.count()):
            if self.physics.itemData(index) == physics_value:
                self.physics.setCurrentIndex(index); break

        self.collision_shape = QComboBox()
        self.collision_shape.addItem("Theo khung ảnh / bounds", "bounds")
        self.collision_shape.addItem("Hình tròn", "circle")
        self.collision_shape.addItem("Polygon từ Collision Editor", "polygon")
        shape_value = str(current.get("collision_shape", "bounds"))
        for index in range(self.collision_shape.count()):
            if self.collision_shape.itemData(index) == shape_value:
                self.collision_shape.setCurrentIndex(index); break

        self.dead_zone = QDoubleSpinBox()
        self.dead_zone.setRange(0.0, 0.95); self.dead_zone.setSingleStep(0.01); self.dead_zone.setDecimals(2)
        self.dead_zone.setValue(float(current.get("dead_zone", 0.18)))
        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(0.1, 5.0); self.sensitivity.setSingleStep(0.1); self.sensitivity.setDecimals(2)
        self.sensitivity.setValue(float(current.get("sensitivity", 1.0)))
        self.auto_execute = QCheckBox("Runtime tự thực thi mapping cơ bản")
        self.auto_execute.setChecked(bool(current.get("auto_execute", True)))
        self.movement_mode = QComboBox()
        self.movement_mode.addItem("Platformer — trái/phải + nhảy + trọng lực", "platformer")
        self.movement_mode.addItem("Top-down — di chuyển 4 hướng", "top_down")
        mode_value = str(current.get("movement_mode", "platformer"))
        for index in range(self.movement_mode.count()):
            if self.movement_mode.itemData(index) == mode_value:
                self.movement_mode.setCurrentIndex(index); break
        self.move_speed = QDoubleSpinBox()
        self.move_speed.setRange(1.0, 3000.0); self.move_speed.setDecimals(0); self.move_speed.setSuffix(" px/s")
        self.move_speed.setValue(float(current.get("move_speed", 260.0)))
        self.jump_speed = QDoubleSpinBox()
        self.jump_speed.setRange(1.0, 3000.0); self.jump_speed.setDecimals(0); self.jump_speed.setSuffix(" px/s")
        self.jump_speed.setValue(float(current.get("jump_speed", 560.0)))
        self.gravity = QDoubleSpinBox()
        self.gravity.setRange(0.0, 10000.0); self.gravity.setDecimals(0); self.gravity.setSuffix(" px/s²")
        self.gravity.setValue(float(current.get("gravity", 1450.0)))
        self.tags = QLineEdit(", ".join(str(item) for item in current.get("tags", []) if str(item).strip()))
        self.tags.setPlaceholderText("ground, walkable, stone")
        self.event_channel = QLineEdit(str(current.get("event_channel", "")))
        self.event_channel.setPlaceholderText("Ví dụ: PLAYER_JUMP, OPEN_DOOR")
        self.target_screen = QComboBox()
        self.target_screen.addItem("— Không chuyển màn —", "")
        for screen in screens:
            self.target_screen.addItem(screen.name, screen.id)
        target_value = str(current.get("target_screen", ""))
        for index in range(self.target_screen.count()):
            if self.target_screen.itemData(index) == target_value:
                self.target_screen.setCurrentIndex(index); break
        self.enabled = QCheckBox("Bật tự động hóa cho thành phần này")
        self.enabled.setChecked(bool(current.get("enabled", True)))

        form.addRow("Vai trò", self.role)
        form.addRow("Input action", self.input_action)
        form.addRow("Input tùy chỉnh", self.custom_input)
        form.addRow("Trục điều khiển", self.axis)
        form.addRow("Physics", self.physics)
        form.addRow("Collision shape", self.collision_shape)
        form.addRow("Dead zone", self.dead_zone)
        form.addRow("Độ nhạy", self.sensitivity)
        form.addRow("Tự chạy mapping", self.auto_execute)
        form.addRow("Kiểu di chuyển Player", self.movement_mode)
        form.addRow("Tốc độ di chuyển", self.move_speed)
        form.addRow("Lực nhảy", self.jump_speed)
        form.addRow("Trọng lực", self.gravity)
        form.addRow("Tags", self.tags)
        form.addRow("Kênh sự kiện", self.event_channel)
        form.addRow("Map đích", self.target_screen)
        form.addRow("Trạng thái", self.enabled)
        self.body_layout.addLayout(form)

        note = QLabel(
            "Khi bật Tự chạy mapping, runtime sẽ xử lý joystick, nút hướng, nhảy và collider cơ bản. "
            "Code Java riêng vẫn có thể đọc input helper hoặc tắt auto_execute để tự xây gameplay hoàn toàn tùy chỉnh."
        )
        note.setWordWrap(True); note.setObjectName("DialogHint")
        self.body_layout.addWidget(note)
        self.role.currentIndexChanged.connect(self._apply_role_defaults)
        self.input_action.currentIndexChanged.connect(self._update_input_state)
        if not current:
            self._apply_role_defaults()
        self._update_input_state()

        clear_button = QPushButton("Xóa ánh xạ")
        clear_button.clicked.connect(self._clear_mapping)
        cancel = QPushButton("Hủy"); cancel.clicked.connect(self.reject)
        apply_button = QPushButton("Áp dụng"); apply_button.setObjectName("PrimaryAction")
        apply_button.clicked.connect(self._accept_mapping)
        self.footer_layout.addWidget(clear_button)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(apply_button)

    def _update_input_state(self) -> None:
        self.custom_input.setEnabled(str(self.input_action.currentData()) == "__custom__")

    def _apply_role_defaults(self) -> None:
        role = str(self.role.currentData() or "custom")
        role_defaults = {
            "virtual_joystick": ("MOVE_AXIS", "none", "both"),
            "direction_button": ("MOVE_LEFT", "none", "x"),
            "action_button": ("JUMP", "none", "both"),
            "skill_button": ("SKILL_1", "none", "both"),
            "ground": ("", "static", "both"),
            "one_way_platform": ("", "one_way", "both"),
            "static_obstacle": ("", "static", "both"),
            "hazard": ("", "sensor", "both"),
            "trigger_zone": ("", "sensor", "both"),
            "portal": ("INTERACT", "sensor", "both"),
            "collectible": ("", "sensor", "both"),
            "player": ("", "dynamic", "both"),
            "enemy": ("", "dynamic", "both"),
        }
        input_value, physics_value, axis_value = role_defaults.get(role, ("", "none", "both"))
        for combo, value in ((self.input_action, input_value), (self.physics, physics_value), (self.axis, axis_value)):
            for index in range(combo.count()):
                if combo.itemData(index) == value:
                    combo.setCurrentIndex(index); break
        if role in {"ground", "one_way_platform"} and not self.tags.text().strip():
            self.tags.setText("ground, walkable")
        elif role == "hazard" and not self.tags.text().strip():
            self.tags.setText("hazard, damage")
        elif role == "portal" and not self.tags.text().strip():
            self.tags.setText("portal, transition")
        elif role == "player":
            self.auto_execute.setChecked(True)
            if not self.tags.text().strip():
                self.tags.setText("player, character")

    def _clear_mapping(self) -> None:
        self.result_mapping = {"enabled": False, "role": "custom", "input_action": "", "physics": "none", "tags": [], "auto_execute": False}
        self.accept()

    def _accept_mapping(self) -> None:
        selected_input = str(self.input_action.currentData() or "")
        if selected_input == "__custom__":
            selected_input = self.custom_input.text().strip().upper().replace(" ", "_")
        tags = [part.strip() for part in self.tags.text().split(",") if part.strip()]
        self.result_mapping = {
            "enabled": self.enabled.isChecked(),
            "role": str(self.role.currentData() or "custom"),
            "input_action": selected_input,
            "axis": str(self.axis.currentData() or "both"),
            "physics": str(self.physics.currentData() or "none"),
            "collision_shape": str(self.collision_shape.currentData() or "bounds"),
            "dead_zone": float(self.dead_zone.value()),
            "sensitivity": float(self.sensitivity.value()),
            "auto_execute": self.auto_execute.isChecked(),
            "movement_mode": str(self.movement_mode.currentData() or "platformer"),
            "move_speed": float(self.move_speed.value()),
            "jump_speed": float(self.jump_speed.value()),
            "gravity": float(self.gravity.value()),
            "tags": tags,
            "event_channel": self.event_channel.text().strip(),
            "target_screen": str(self.target_screen.currentData() or ""),
        }
        self.accept()

    @classmethod
    def get_mapping(cls, screens: list[ScreenInfo], payload: dict, parent=None) -> dict | None:
        dialog = cls(screens, payload, parent)
        return dialog.result_mapping if dialog.exec() == QDialog.DialogCode.Accepted else None


class MapTransitionDialog(CustomDialog):
    """Create a screen-to-screen transition in screens.dtfe."""

    def __init__(self, screens: list[ScreenInfo], source_id: str = "", target_id: str = "", parent=None) -> None:
        super().__init__("Ánh xạ sự kiện nối hai map", parent, width=520, height=390, resizable=False, modal=True)
        self.result_mapping: dict | None = None
        form = QFormLayout()
        self.source = QComboBox()
        self.target = QComboBox()
        for screen in screens:
            self.source.addItem(screen.name, screen.id)
            self.target.addItem(screen.name, screen.id)
        for combo, selected in ((self.source, source_id), (self.target, target_id)):
            for index in range(combo.count()):
                if combo.itemData(index) == selected:
                    combo.setCurrentIndex(index)
                    break
        self.trigger = QComboBox()
        self.trigger.addItem("Va chạm cổng / vùng", "on_overlap")
        self.trigger.addItem("Nhấn nút tương tác", "on_click")
        self.trigger.addItem("Đi vào vùng", "on_enter")
        self.trigger.addItem("Hoàn tất màn chơi", "on_complete")
        self.bidirectional = QCheckBox("Tạo liên kết hai chiều")
        form.addRow("Map nguồn", self.source)
        form.addRow("Map đích", self.target)
        form.addRow("Kích hoạt", self.trigger)
        form.addRow("Tùy chọn", self.bidirectional)
        self.body_layout.addLayout(form)
        note = QLabel("Liên kết được lưu trong assets/scenes/screens.dtfe và sinh hằng Java trong DutifulSceneBindings.Transitions.")
        note.setWordWrap(True)
        self.body_layout.addWidget(note)
        cancel = QPushButton("Hủy")
        cancel.clicked.connect(self.reject)
        apply_button = QPushButton("Tạo liên kết")
        apply_button.setObjectName("PrimaryAction")
        apply_button.clicked.connect(self._accept_mapping)
        self.footer_layout.addWidget(cancel)
        self.footer_layout.addWidget(apply_button)

    def _accept_mapping(self) -> None:
        source = str(self.source.currentData() or "")
        target = str(self.target.currentData() or "")
        if not source or not target or source == target:
            NoticeDialog("Liên kết chưa hợp lệ", "Hãy chọn hai màn chơi khác nhau.", self, error=True).exec()
            return
        self.result_mapping = {
            "source": source,
            "target": target,
            "trigger": str(self.trigger.currentData() or "on_overlap"),
            "bidirectional": self.bidirectional.isChecked(),
        }
        self.accept()

    @classmethod
    def get_mapping(cls, screens: list[ScreenInfo], source_id: str = "", target_id: str = "", parent=None) -> dict | None:
        dialog = cls(screens, source_id, target_id, parent)
        return dialog.result_mapping if dialog.exec() == QDialog.DialogCode.Accepted else None


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1536, 960)
        self.setMinimumSize(760, 520)
        self.setMouseTracking(True)
        self._closing = False

        self.project_store = ProjectStore()
        self.current_project: ProjectInfo | None = None
        self.editor_page: QWidget | None = None
        self.code_editors: dict[Path, CodeEditor] = {}
        self.image_previews: dict[Path, QWidget] = {}
        self.console_log: QPlainTextEdit | None = None
        self.output_log: QPlainTextEdit | None = None
        self.debugger_panel = None
        self.problems_panel = None
        self.console_tabs: QTabWidget | None = None
        self.console_panel: QWidget | None = None
        self.console_toggle_action: QAction | None = None
        self._console_last_height = 190
        self._console_visible = True
        self._selected_build_target_index = 0
        self._build_menu_actions: list[QAction] = []
        self.center_tabs: QTabWidget | None = None
        self.assets_panel = None
        self.scene_panel = None
        self.inspector_panel = None
        self.tileset_panel = None
        self.viewport_2d: Viewport2D | None = None
        self.scene_viewports: dict[Path, Viewport2D] = {}
        self.active_scene_path: Path | None = None
        self.workspace_split = None
        self.left_workspace_column = None
        self.center_workspace_column = None
        self.right_workspace_column = None
        self._toolbar_tool_buttons: list[QToolButton] = []
        self._status_optional_widgets: list[QWidget] = []
        self._console_backlog: list[str] = []
        self._build_diagnostics: list[dict] = []
        self._last_artifact: Path | None = None
        self._toolbar_tool_buttons_by_name: dict[str, QToolButton] = {}
        self.run_session_dialog: RunSessionDialog | None = None
        self.task_progress: BottomTaskProgress | None = None
        self.asset_editor_windows: list[AssetEditorDialog] = []
        self.keyframe_editor_windows: list[KeyframeEditorWindow] = []
        self.adb_devices: list[dict] = []
        self.selected_adb_serial = ""
        self.adb_menu: QMenu | None = None
        self.adb_run_action: QAction | None = None
        self.adb_manager = AdbDeviceManager(self)
        self.adb_manager.devices_changed.connect(self._on_adb_devices_changed)
        self.adb_manager.output.connect(self._append_console)
        self.adb_manager.error.connect(self._on_adb_error)
        self.runner = LibGDXRunner(self)
        self.runner.output.connect(self._append_console)
        self.runner.started.connect(self._on_runner_started)
        self.runner.running_changed.connect(self._runner_state_changed)
        self.runner.project_structure_changed.connect(self._project_structure_changed)
        self.runner.diagnostic.connect(self._on_diagnostic)
        self.runner.artifact_found.connect(self._on_artifact_found)
        self.runner.phase_changed.connect(self._on_phase_changed)
        self.runner.debugger_output.connect(self._append_debugger)
        self.runner.debugger_state.connect(self._on_debugger_state)
        self.runner.finished.connect(self._on_runner_finished)
        self.runner.environment_checked.connect(self._on_environment_checked)
        self.runner.environment_install_completed.connect(self._on_environment_install_completed)
        self._resizing = False
        self._resize_edge: str | None = None
        self._drag_start_geo = None
        self._drag_start_pos = None

        outer = QVBoxLayout(self)
        self.outer_layout = outer
        outer.setContentsMargins(RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN)
        self.root_frame = QFrame()
        self.root_frame.setObjectName("RootFrame")
        self.root_frame.setMouseTracking(True)
        outer.addWidget(self.root_frame)

        self.app_toast = AppToast(self.root_frame)
        self._pending_update_url = ""
        self.app_toast.action_requested.connect(self._open_pending_update)
        self.update_checker = UpdateChecker(ENGINE_VERSION, self)
        self.update_checker.update_available.connect(self._on_update_available)
        self.update_checker.up_to_date.connect(self._on_update_current)
        self.update_checker.failed.connect(self._on_update_failed)

        root_layout = QVBoxLayout(self.root_frame)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        self.window_state_controller = WindowStateController(
            window=self,
            title_bar=self.title_bar,
            outer_layout=self.outer_layout,
            root_frame=self.root_frame,
            normal_margin=RESIZE_MARGIN,
            parent=self,
        )
        self.title_bar.minimizeRequested.connect(self.window_state_controller.minimize)
        self.title_bar.maximizeRestoreRequested.connect(
            self.window_state_controller.toggle_maximize_restore
        )
        self.title_bar.closeRequested.connect(self.close)
        self.title_bar.homeRequested.connect(self._show_home)
        self.title_bar.btn_info.clicked.connect(lambda: self._show_documentation("about"))
        root_layout.addWidget(self.title_bar)

        self.menu_bar = self._build_menu_bar()
        self.title_bar.set_menu_bar(self.menu_bar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        root_layout.addWidget(self.stack, 1)

        self.home_page = HomePage()
        self.home_page.new_project_requested.connect(self._open_new_project_dialog)
        self.home_page.project_template_requested.connect(self._open_new_project_dialog)
        self.home_page.open_project_folder_requested.connect(self._open_project_folder)
        self.home_page.project_open_requested.connect(self._open_project)
        self.home_page.project_remove_requested.connect(self._remove_project_from_list)
        self.home_page.documentation_requested.connect(self._show_documentation)
        self.stack.addWidget(self.home_page)

        docs_directory = Path(__file__).resolve().parent.parent / "docs"
        self.documentation_page = DocumentationPage(docs_directory)
        self.documentation_page.home_requested.connect(self._show_home)
        self.stack.addWidget(self.documentation_page)
        self._show_home()
        QTimer.singleShot(2500, lambda: self.update_checker.check(manual=False))

    def _build_menu_bar(self) -> QMenuBar:
        menu_bar = QMenuBar()

        file_menu = menu_bar.addMenu("File")
        home_action = QAction(icon("fa5s.home"), "Home", self)
        home_action.setShortcut("Ctrl+Shift+H")
        home_action.triggered.connect(self._show_home)
        file_menu.addAction(home_action)

        new_action = QAction(icon("fa5s.plus"), "New libGDX Project…", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(lambda _checked=False: self._open_new_project_dialog())
        file_menu.addAction(new_action)

        open_action = QAction(icon("fa5s.folder-open"), "Open Project…", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_project_folder)
        file_menu.addAction(open_action)
        file_menu.addSeparator()

        save_action = QAction(icon("fa5s.save"), "Save All", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_open_files)
        file_menu.addAction(save_action)
        file_menu.addSeparator()

        exit_action = QAction(icon("fa5s.sign-out-alt"), "Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("Edit")
        undo_action = QAction(icon("fa5s.undo"), "Undo", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self._undo_action)
        edit_menu.addAction(undo_action)
        redo_action = QAction(icon("fa5s.redo"), "Redo", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self._redo_action)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        for label, shortcut, method_name in (
            ("Cut", "Ctrl+X", "cut"),
            ("Copy", "Ctrl+C", "copy"),
            ("Paste", "Ctrl+V", "paste"),
            ("Select All", "Ctrl+A", "selectAll"),
        ):
            action = QAction(label, self)
            action.setShortcut(shortcut)
            action.triggered.connect(
                lambda _checked=False, method=method_name: self._dispatch_focused_editor_method(method)
            )
            edit_menu.addAction(action)
        edit_menu.addSeparator()
        duplicate_action = QAction(icon("fa5s.clone"), "Duplicate Scene Object", self)
        duplicate_action.setShortcut("Ctrl+D")
        duplicate_action.triggered.connect(self._duplicate_selected)
        edit_menu.addAction(duplicate_action)
        delete_action = QAction(icon("fa5s.trash-alt"), "Delete Scene Object", self)
        delete_action.triggered.connect(
            lambda: self.viewport_2d.delete_selected() if self.viewport_2d is not None else None
        )
        edit_menu.addAction(delete_action)
        edit_menu.addSeparator()
        asset_editor_action = QAction(icon("fa5s.magic"), "Editor Assets…", self)
        asset_editor_action.setShortcut("Ctrl+Shift+A")
        asset_editor_action.triggered.connect(lambda: self._open_asset_editor(""))
        edit_menu.addAction(asset_editor_action)

        view_menu = menu_bar.addMenu("View")
        for label, attribute in (
            ("Scene Panel", "scene_panel"),
            ("Assets Panel", "assets_panel"),
            ("Inspector Panel", "inspector_panel"),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(True)
            action.triggered.connect(
                lambda checked, attr=attribute: self._set_panel_visible(attr, checked)
            )
            view_menu.addAction(action)
        self.console_toggle_action = QAction(icon("fa5s.terminal"), "Bottom Panel / Console", self)
        self.console_toggle_action.setShortcut("Ctrl+J")
        self.console_toggle_action.setCheckable(True)
        self.console_toggle_action.setChecked(True)
        self.console_toggle_action.triggered.connect(self._set_console_visible)
        view_menu.addAction(self.console_toggle_action)
        view_menu.addSeparator()
        zoom_in = QAction(icon("fa5s.search-plus"), "Zoom In", self)
        zoom_in.setShortcut("Ctrl++")
        zoom_in.triggered.connect(lambda: self._zoom_viewport(1.15))
        view_menu.addAction(zoom_in)
        zoom_out = QAction(icon("fa5s.search-minus"), "Zoom Out", self)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self._zoom_viewport(1 / 1.15))
        view_menu.addAction(zoom_out)
        reset_zoom = QAction(icon("fa5s.expand"), "Reset View", self)
        reset_zoom.setShortcut("Ctrl+0")
        reset_zoom.triggered.connect(self._reset_viewport)
        view_menu.addAction(reset_zoom)
        frame_selection = QAction(icon("fa5s.crosshairs"), "Frame Selection", self)
        frame_selection.setShortcut("F")
        frame_selection.triggered.connect(self._frame_selection)
        view_menu.addAction(frame_selection)

        project_menu = menu_bar.addMenu("Project")
        environment_action = QAction(icon("fa5s.check-circle"), "Kiểm tra môi trường / thư viện…", self)
        environment_action.triggered.connect(self._check_environment)
        project_menu.addAction(environment_action)
        compile_action = QAction(icon("fa5s.code"), "Compile Java (core + lwjgl3)", self)
        compile_action.setShortcut("Ctrl+F9")
        compile_action.triggered.connect(self._compile_java)
        project_menu.addAction(compile_action)
        project_menu.addSeparator()
        open_folder = QAction(icon("fa5s.folder-open"), "Open Project Folder", self)
        open_folder.triggered.connect(self._open_current_project_folder)
        project_menu.addAction(open_folder)

        scene_menu = menu_bar.addMenu("Scene")
        for label, tool, icon_name in (
            ("Rectangle2D", "Rectangle", "fa5s.vector-square"),
            ("Circle2D", "Circle", "fa5s.circle-notch"),
            ("Line2D", "Line", "fa5s.slash"),
            ("Text2D", "Text", "fa5s.font"),
            ("Tile2D", "Tile", "fa5s.th"),
            ("Brush2D", "Brush", "fa5s.paint-brush"),
        ):
            action = QAction(icon(icon_name), f"Create {label}", self)
            action.triggered.connect(lambda _checked=False, value=tool: self._select_toolbar_tool(value))
            scene_menu.addAction(action)
        scene_menu.addSeparator()
        scene_menu.addAction(duplicate_action)
        scene_menu.addAction(frame_selection)

        run_menu = menu_bar.addMenu("Run")
        debug_desktop = QAction(icon("fa5s.bug"), "Debug Desktop", self)
        debug_desktop.setShortcut("F5")
        debug_desktop.triggered.connect(self._debug_desktop)
        run_menu.addAction(debug_desktop)
        run_desktop = QAction(icon("fa5s.play"), "Run Desktop (LWJGL3)", self)
        run_desktop.setShortcut("F6")
        run_desktop.triggered.connect(self._run_desktop)
        run_menu.addAction(run_desktop)
        run_android_device = QAction(icon("fa5s.mobile-alt"), "Run on Android Device (ADB)", self)
        run_android_device.setShortcut("Ctrl+F6")
        run_android_device.triggered.connect(self._run_android_on_device)
        run_menu.addAction(run_android_device)
        run_menu.addSeparator()
        build_desktop = QAction(icon("fa5s.box"), "Build Desktop JAR", self)
        build_desktop.triggered.connect(lambda _checked=False: self._run_gradle_task("lwjgl3:dist"))
        run_menu.addAction(build_desktop)
        build_jad = QAction(icon("fa5s.file-alt"), "Build Desktop JAR + JAD", self)
        build_jad.triggered.connect(self._build_desktop_jad)
        run_menu.addAction(build_jad)
        build_android = QAction(icon("fa5s.mobile-alt"), "Build Android APK Debug", self)
        build_android.triggered.connect(lambda _checked=False: self._run_gradle_task("android:assembleDebug"))
        run_menu.addAction(build_android)
        build_android_release = QAction(icon("fa5b.android"), "Build Android APK Release", self)
        build_android_release.triggered.connect(lambda _checked=False: self._run_gradle_task("android:assembleRelease"))
        run_menu.addAction(build_android_release)
        build_aab = QAction(icon("fa5s.archive"), "Build Android AAB Release", self)
        build_aab.triggered.connect(lambda _checked=False: self._run_gradle_task("android:bundleRelease"))
        run_menu.addAction(build_aab)
        native_action = QAction(icon("fa5s.microchip"), "Build C/C++ Native DLL", self)
        native_action.triggered.connect(self._build_native_windows)
        run_menu.addAction(native_action)
        clean_action = QAction(icon("fa5s.broom"), "Clean Project", self)
        clean_action.triggered.connect(lambda _checked=False: self._run_gradle_task("clean"))
        run_menu.addAction(clean_action)
        run_menu.addSeparator()
        stop_action = QAction(icon("fa5s.stop"), "Stop Run / Build / Debug", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self.runner.stop)
        run_menu.addAction(stop_action)

        tools_menu = menu_bar.addMenu("Tools")
        tileset_action = QAction(icon("fa5s.th"), "TileSet Editor", self)
        tileset_action.triggered.connect(lambda: self._open_asset_editor("", "assets/map/tileset"))
        tools_menu.addAction(tileset_action)
        animation_action = QAction(icon("fa5s.film"), "Animation / Scene Editor", self)
        animation_action.triggered.connect(lambda: self._open_asset_editor("", "assets/scenes"))
        tools_menu.addAction(animation_action)
        tools_menu.addSeparator()
        adb_devices_action = QAction(icon("fa5s.usb"), "ADB Devices / USB Type-C", self)
        adb_devices_action.triggered.connect(self._refresh_adb_devices)
        tools_menu.addAction(adb_devices_action)
        audit_action = QAction(icon("fa5s.stethoscope"), "Kiểm tra logic công cụ Engine", self)
        audit_action.triggered.connect(self._run_feature_audit)
        tools_menu.addAction(audit_action)
        clear_problems = QAction(icon("fa5s.eraser"), "Clear Problems", self)
        clear_problems.triggered.connect(self._clear_build_diagnostics)
        tools_menu.addAction(clear_problems)

        help_menu = menu_bar.addMenu("Help")
        docs_action = QAction(icon("fa5s.book-open"), "2Dutiful Documentation", self)
        docs_action.setShortcut("F1")
        docs_action.triggered.connect(lambda: self._show_documentation())
        help_menu.addAction(docs_action)
        libgdx_docs_action = QAction(icon("fa5s.external-link-alt"), "libGDX Documentation", self)
        libgdx_docs_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://libgdx.com/wiki/"))
        )
        help_menu.addAction(libgdx_docs_action)
        help_menu.addSeparator()
        update_action = QAction(icon("fa5s.sync-alt"), "Kiểm tra cập nhật…", self)
        update_action.triggered.connect(lambda: self.update_checker.check(manual=True))
        help_menu.addAction(update_action)
        about_action = QAction(icon("fa5s.info-circle"), "About 2Dutiful Engine", self)
        about_action.triggered.connect(lambda: self._show_documentation("about"))
        help_menu.addAction(about_action)
        return menu_bar

    def _run_feature_audit(self) -> None:
        app_root = Path(__file__).resolve().parent
        findings = audit_engine_source(app_root)
        summary = summarize_findings(findings)
        report_path = app_root.parent / "reports" / "audits" / "feature-audit-latest.json"
        payload = {
            "engine_version": ENGINE_VERSION,
            "summary": summary,
            "findings": [finding.to_dict() for finding in findings],
        }
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as error:
            self._append_console(f"[Warning] Không thể ghi Feature Audit report: {error}")
        formatted = format_audit_summary(findings)
        self._append_console(formatted)
        NoticeDialog(
            "Kiểm tra logic công cụ",
            formatted + f"\n\nBáo cáo: {report_path}",
            self,
            error=bool(summary.get("error")),
        ).exec()

    def _show_home(self) -> None:
        self.home_page.set_projects(self.project_store.load())
        self.stack.setCurrentWidget(self.home_page)
        self.title_bar.set_home_mode(True)

    def _show_documentation(self, topic_key: str = "overview") -> None:
        self.documentation_page.open_topic(topic_key)
        self.stack.setCurrentWidget(self.documentation_page)
        self.title_bar.set_home_mode(False)
        self.title_bar.set_project_name("Tài liệu")

    def _open_new_project_dialog(self, template_key: str = "blank") -> None:
        default_path = str(self.project_store.default_projects_directory())
        previous_name = ""
        previous_path = default_path

        while True:
            dialog = NewProjectDialog(previous_path, self, template_key=template_key)
            dialog.edit_name.setText(previous_name)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            previous_name = dialog.project_name
            previous_path = dialog.base_directory
            try:
                project = self.project_store.create_project(
                    previous_name,
                    previous_path,
                    package_name=dialog.package_name,
                    native_enabled=dialog.native_enabled,
                    viewport_width=dialog.viewport_width,
                    viewport_height=dialog.viewport_height,
                    aspect_ratio=dialog.aspect_ratio,
                    template_key=dialog.template_key,
                )
            except (OSError, ValueError) as error:
                NoticeDialog("Không thể tạo dự án", str(error), self, error=True).exec()
                continue

            self.home_page.set_projects(self.project_store.load())
            self._open_project(project)
            return

    def _open_project_folder(self) -> None:
        start = str(self.project_store.default_projects_directory())
        selected = FilePickerDialog.get_existing_directory(
            self,
            "Mở thư mục dự án 2Dutiful",
            start,
        )
        if not selected:
            return
        try:
            project = self.project_store.register_existing(selected)
        except (OSError, ValueError) as error:
            NoticeDialog("Không thể mở dự án", str(error), self, error=True).exec()
            return
        self._open_project(project)

    def _remove_project_from_list(self, project: ProjectInfo) -> None:
        self.project_store.remove(project.path)
        self.home_page.set_projects(self.project_store.load())

    def _open_project(self, project: ProjectInfo) -> None:
        if not Path(project.path).exists():
            NoticeDialog(
                "Không tìm thấy dự án",
                "Thư mục dự án đã bị di chuyển hoặc xóa khỏi ổ đĩa.",
                self,
                error=True,
            ).exec()
            self.project_store.remove(project.path)
            self.home_page.set_projects(self.project_store.load())
            return

        runtime_message = ""
        try:
            _changed, runtime_message = ProjectStore.ensure_dtfe_runtime(project.path)
        except (OSError, ValueError) as error:
            runtime_message = f"Không thể đồng bộ DTFE runtime: {error}"

        self.current_project = self.project_store.touch(project)
        self.viewport_2d = None
        self.scene_viewports.clear()
        self.active_scene_path = None
        self.code_editors.clear()
        self.image_previews.clear()
        self.console_log = None
        self.output_log = None
        self.debugger_panel = None
        self.problems_panel = None
        self.console_tabs = None
        self.console_panel = None
        self.task_progress = None
        self._build_diagnostics.clear()
        self._console_backlog.clear()
        if runtime_message:
            self._console_backlog.append(f"[Runtime] {runtime_message}")
        if self.editor_page is not None:
            self.stack.removeWidget(self.editor_page)
            self.editor_page.deleteLater()
        self.editor_page = self._build_editor_page(self.current_project)
        self.stack.addWidget(self.editor_page)
        self.stack.setCurrentWidget(self.editor_page)
        self.title_bar.set_home_mode(False)
        self.title_bar.set_project_name(f"{self.current_project.name} • libGDX")
        self._apply_responsive_layout(self.width())

    def _build_editor_page(self, project: ProjectInfo) -> QWidget:
        page = QWidget()
        page.setObjectName("EditorPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_tool_bar())
        layout.addWidget(self._build_content_area(project), 1)
        layout.addWidget(self._build_status_bar(project))
        return page

    def _build_tool_bar(self) -> QWidget:
        self._toolbar_tool_buttons = []
        self._toolbar_tool_buttons_by_name = {}
        bar = QWidget()
        bar.setObjectName("MainToolBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 3, 10, 3)
        layout.setSpacing(2)

        home = QToolButton()
        home.setObjectName("ToolbarHome")
        home.setIcon(icon("fa5s.home"))
        home.setIconSize(QSize(14, 14))
        home.setFixedSize(29, 29)
        home.setToolTip("Về màn hình Home")
        home.clicked.connect(self._show_home)
        layout.addWidget(home)
        layout.addWidget(self._toolbar_separator())

        button_group: list[QToolButton] = []

        def add_tool(name: str, icon_name: str, checked: bool = False) -> QToolButton:
            button = QToolButton()
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(14, 14))
            button.setFixedSize(29, 29)
            button.setToolTip(name)
            button.setProperty("toolName", name)
            button.setCheckable(True)
            button.setChecked(checked)
            button.clicked.connect(
                lambda _checked=False, selected=button: self._activate_tool(button_group, selected)
            )
            layout.addWidget(button)
            button_group.append(button)
            self._toolbar_tool_buttons.append(button)
            self._toolbar_tool_buttons_by_name[name] = button
            return button

        for index, item in enumerate((
            ("Select", "fa5s.mouse-pointer"),
            ("Move", "fa5s.hand-paper"),
            ("Rotate", "fa5s.sync-alt"),
            ("Scale", "fa5s.expand-alt"),
        )):
            add_tool(item[0], item[1], checked=index == 0)

        layout.addWidget(self._toolbar_separator())

        def add_scene_action(icon_name: str, tooltip: str, callback, *, enabled: bool = True) -> QToolButton:
            button = QToolButton()
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(14, 14))
            button.setFixedSize(29, 29)
            button.setToolTip(tooltip)
            button.setEnabled(enabled)
            button.clicked.connect(lambda _checked=False: callback())
            layout.addWidget(button)
            return button

        self.undo_button = add_scene_action(
            "fa5s.undo", "Hoàn tác thay đổi Scene (Ctrl+Z)", self._undo_action, enabled=False
        )
        self.redo_button = add_scene_action(
            "fa5s.redo", "Làm lại thay đổi Scene (Ctrl+Y)", self._redo_action, enabled=False
        )
        self.reset_view_button = add_scene_action(
            "fa5s.crosshairs", "Đặt lại vị trí và mức thu phóng của frame (Ctrl+0)", self._reset_viewport
        )
        self.add_screen_toolbar_button = add_scene_action(
            "fa5s.plus-square", "Thêm màn chơi mới", lambda: self._handle_screen_action("create", {})
        )

        layout.addWidget(self._toolbar_separator())
        for name, icon_name in (
            ("Rectangle", "fa5s.vector-square"),
            ("Circle", "fa5s.circle-notch"),
            ("Line", "fa5s.slash"),
            ("Text", "fa5s.font"),
            ("Tile", "fa5s.th"),
            ("Brush", "fa5s.paint-brush"),
        ):
            add_tool(name, icon_name)

        self.toolbar_overflow = QToolButton()
        self.toolbar_overflow.setObjectName("ToolbarOverflow")
        self.toolbar_overflow.setIcon(icon("fa5s.ellipsis-h"))
        self.toolbar_overflow.setIconSize(QSize(14, 14))
        self.toolbar_overflow.setFixedSize(29, 29)
        self.toolbar_overflow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        overflow_menu = QMenu(self.toolbar_overflow)
        for tool_button in self._toolbar_tool_buttons:
            action = QAction(
                tool_button.icon(),
                str(tool_button.property("toolName") or tool_button.toolTip()),
                overflow_menu,
            )
            action.triggered.connect(lambda _checked=False, button=tool_button: button.click())
            overflow_menu.addAction(action)
        self.toolbar_overflow.setMenu(overflow_menu)
        self.toolbar_overflow.hide()
        layout.addWidget(self.toolbar_overflow)
        layout.addStretch()

        self.debug_button = self._command_button(
            "DebugBtn", "Debug", "fa5s.bug", "Debug Desktop bằng JDWP/JDB (F5)", self._debug_desktop
        )
        layout.addWidget(self.debug_button)
        self.run_button = self._command_button(
            "RunBtn", "Run", "fa5s.play", "Lưu mã và chạy desktop bằng LWJGL3 (F6)", self._run_desktop
        )
        layout.addWidget(self.run_button)
        self.stop_button = self._command_button(
            "StopBtn", "Stop", "fa5s.stop", "Dừng game, Gradle, CMake và JDB", self.runner.stop
        )
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)
        self.check_button = self._command_button(
            "CheckBtn", "Check", "fa5s.check-circle", "Kiểm tra Java, javac, JDB và Gradle", self._check_environment
        )
        layout.addWidget(self.check_button)

        layout.addWidget(self._toolbar_separator())
        self.build_button = QToolButton()
        self.build_button.setObjectName("BuildBtn")
        self.build_button.setText("Build")
        self.build_button.setProperty("responsiveText", "Build")
        self.build_button.setIcon(icon("fa5s.box"))
        self.build_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.build_button.setIconSize(QSize(14, 14))
        self.build_button.setFixedHeight(29)
        self.build_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        build_menu = QMenu(self.build_button)
        self._build_menu_actions.clear()
        for index, (label, icon_name, _command) in enumerate(BUILD_TARGETS):
            action = QAction(icon(icon_name), label, build_menu)
            action.setCheckable(True)
            action.setChecked(index == self._selected_build_target_index)
            action.triggered.connect(
                lambda _checked=False, target_index=index: self._select_and_build_target(target_index)
            )
            build_menu.addAction(action)
            self._build_menu_actions.append(action)
        self.build_button.setMenu(build_menu)
        self.build_button.clicked.connect(self._build_selected_target)
        self._update_build_button_label()
        layout.addWidget(self.build_button)

        self.adb_button = QToolButton()
        self.adb_button.setObjectName("AdbBtn")
        self.adb_button.setText("ADB")
        self.adb_button.setProperty("responsiveText", "ADB")
        self.adb_button.setIcon(icon("fa5s.usb"))
        self.adb_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.adb_button.setIconSize(QSize(14, 14))
        self.adb_button.setFixedHeight(29)
        self.adb_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.adb_menu = QMenu(self.adb_button)
        self.adb_menu.aboutToShow.connect(self._prepare_adb_menu)
        self.adb_button.setMenu(self.adb_menu)
        self.adb_button.clicked.connect(self._run_android_on_device)
        layout.addWidget(self.adb_button)

        return bar

    def _command_button(self, object_name: str, text: str, icon_name: str, tooltip: str, callback) -> QToolButton:
        button = QToolButton()
        button.setObjectName(object_name)
        button.setText(text)
        button.setProperty("responsiveText", text)
        button.setIcon(icon(icon_name))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(14, 14))
        button.setFixedHeight(29)
        button.setToolTip(tooltip)
        button.clicked.connect(lambda _checked=False: callback())
        return button

    @staticmethod
    def _toolbar_separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("ToolbarSeparator")
        separator.setFrameShape(QFrame.VLine)
        separator.setFixedHeight(24)
        return separator

    def _exclusive_check(self, buttons: list[QToolButton], active: QToolButton) -> None:
        self._activate_tool(buttons, active)

    def _activate_tool(self, buttons: list[QToolButton], active: QToolButton) -> None:
        for button in buttons:
            button.setChecked(button is active)
        tool_name = str(active.property("toolName") or active.toolTip() or "Select")
        if self.viewport_2d is not None:
            self._ensure_scene_tab()
            self.viewport_2d.set_tool(tool_name)
            self.viewport_2d.setFocus()

    def _select_toolbar_tool(self, tool_name: str) -> None:
        button = self._toolbar_tool_buttons_by_name.get(tool_name)
        if button is not None:
            button.click()
            return
        if self.viewport_2d is not None:
            self.viewport_2d.set_tool(tool_name)

    def _build_content_area(self, project: ProjectInfo) -> QWidget:
        """Build a responsive three-column editor with center-only console."""
        workspace_split = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_split = workspace_split
        workspace_split.setObjectName("WorkspaceSplitter")
        workspace_split.setChildrenCollapsible(False)
        workspace_split.setHandleWidth(4)

        left_column = QSplitter(Qt.Orientation.Vertical)
        self.left_workspace_column = left_column
        left_column.setObjectName("LeftWorkspaceColumn")
        left_column.setChildrenCollapsible(False)
        left_column.setHandleWidth(4)
        scene_panel = panels.build_scene_panel(project.path)
        self.scene_panel = scene_panel
        assets_panel = panels.build_assets_panel(project.path, project.package_name)
        self.assets_panel = assets_panel
        assets_panel.file_open_requested.connect(self._open_asset_file)
        assets_panel.asset_editor_requested.connect(self._open_asset_editor)
        assets_panel.asset_insert_requested.connect(self._insert_asset_into_active_viewport)
        assets_panel.status_message.connect(self._append_console)
        assets_panel.error_message.connect(
            lambda message: NoticeDialog("Lỗi Assets", message, self, error=True).exec()
        )
        scene_panel.node_open_requested.connect(self._open_scene_node)
        scene_panel.node_action_requested.connect(self._handle_scene_node_action)
        scene_panel.screen_action_requested.connect(self._handle_screen_action)
        scene_panel.structure_changed.connect(self._handle_scene_structure_changed)
        left_column.addWidget(scene_panel)
        left_column.addWidget(assets_panel)
        left_column.setSizes([390, 430])
        left_column.setStretchFactor(0, 1)
        left_column.setStretchFactor(1, 1)
        left_column.setMinimumWidth(190)

        center_column = QSplitter(Qt.Orientation.Vertical)
        self.center_workspace_column = center_column
        center_column.setObjectName("CenterWorkspaceColumn")
        center_column.setChildrenCollapsible(True)
        center_column.setHandleWidth(4)
        center_tabs = self._build_center_tabs(project)
        console_panel = panels.build_console_panel(project.name)
        self.console_panel = console_panel
        console_panel.setMinimumHeight(0)
        self.console_log = getattr(console_panel, "console_output", None)
        self.output_log = getattr(console_panel, "output_log", None)
        self.debugger_panel = getattr(console_panel, "debugger_panel", None)
        self.problems_panel = getattr(console_panel, "problems_panel", None)
        self.console_tabs = getattr(console_panel, "console_tabs", None)
        if self.console_tabs is not None:
            collapse_button = QToolButton(self.console_tabs)
            collapse_button.setObjectName("ConsoleCollapseButton")
            collapse_button.setIcon(icon("fa5s.chevron-down"))
            collapse_button.setIconSize(QSize(11, 11))
            collapse_button.setFixedSize(25, 25)
            collapse_button.setToolTip("Ẩn Bottom Panel (Ctrl+J)")
            collapse_button.clicked.connect(lambda _checked=False: self._set_console_visible(False))
            self.console_tabs.setCornerWidget(collapse_button, Qt.Corner.TopRightCorner)
        if self.debugger_panel is not None:
            self.debugger_panel.command_requested.connect(self.runner.debug_command)
            self.debugger_panel.stop_requested.connect(self.runner.stop)
        if self.problems_panel is not None:
            self.problems_panel.diagnostic_open_requested.connect(self._open_diagnostic)
            self.problems_panel.set_diagnostics(self._build_diagnostics)
        center_column.addWidget(center_tabs)
        center_column.addWidget(console_panel)
        center_column.setSizes([650, 190])
        center_column.setStretchFactor(0, 1)
        center_column.setStretchFactor(1, 0)
        self._console_visible = True
        self._selected_build_target_index = 0
        self._build_menu_actions: list[QAction] = []
        if self.console_toggle_action is not None:
            self.console_toggle_action.setChecked(True)

        right_column = QSplitter(Qt.Orientation.Vertical)
        self.right_workspace_column = right_column
        right_column.setObjectName("RightWorkspaceColumn")
        right_column.setChildrenCollapsible(False)
        right_column.setHandleWidth(4)
        inspector = panels.build_inspector_panel(project.path)
        self.inspector_panel = inspector
        tilemap_panel = panels.build_tilemap_panel(project.path)
        self.tileset_panel = tilemap_panel
        tilemap_panel.insert_asset_requested.connect(self._insert_asset_into_active_viewport)
        tilemap_panel.replace_asset_requested.connect(self._replace_asset_in_active_viewport)
        tilemap_panel.edit_asset_requested.connect(self._open_asset_editor)
        tilemap_panel.insert_control_kit_requested.connect(self._insert_control_kit)
        tilemap_panel.assets_imported.connect(self._titleset_assets_imported)
        tilemap_panel.terrain_brush_requested.connect(self._set_terrain_brush_on_active_viewport)
        tilemap_panel.terrain_paint_stopped.connect(self._stop_terrain_paint_on_active_viewport)
        inspector.setMinimumWidth(210)
        right_column.addWidget(inspector)
        right_column.addWidget(tilemap_panel)
        right_column.setSizes([560, 280])
        right_column.setStretchFactor(0, 1)
        right_column.setStretchFactor(1, 0)
        right_column.setMinimumWidth(220)

        workspace_split.addWidget(left_column)
        workspace_split.addWidget(center_column)
        workspace_split.addWidget(right_column)
        workspace_split.setSizes([300, 900, 320])
        workspace_split.setStretchFactor(0, 0)
        workspace_split.setStretchFactor(1, 1)
        workspace_split.setStretchFactor(2, 0)

        inspector.property_changed.connect(self._update_active_viewport_property)
        inspector.delete_requested.connect(self._delete_active_viewport_selection)
        inspector.action_requested.connect(self._handle_inspector_action)
        if self.viewport_2d is not None:
            inspector.set_selection(self.viewport_2d.camera_payload())
            scene_panel.set_active_screen(self.viewport_2d.screen_id)

        if self.console_log is not None and self._console_backlog:
            append_colored_log(self.console_log, "\n".join(self._console_backlog))
            self._console_backlog.clear()

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(workspace_split)
        return wrapper

    def _build_center_tabs(self, project: ProjectInfo) -> QWidget:
        panel = PanelFrame("", show_header=False)
        panel.set_content_margins(0, 0, 0, 0)
        tabs = QTabWidget()
        self.center_tabs = tabs
        tabs.setDocumentMode(True)
        tabs.setMovable(True)
        tabs.setTabsClosable(False)
        tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabs.tabBar().customContextMenuRequested.connect(self._show_center_tab_context_menu)
        tabs.currentChanged.connect(self._center_tab_changed)

        screen_store = ScreenStore(project.path)
        active_screen = screen_store.active_screen()
        self.viewport_2d = self._create_scene_viewport(active_screen)
        self._add_center_tab(self.viewport_2d, "fa5s.map", active_screen.name, select=True)

        package_path = Path(*project.package_name.split("."))
        java_path = (
            Path(project.path)
            / "core" / "src" / "main" / "java"
            / package_path / "DutifulGame.java"
        )
        self._add_code_tab(tabs, java_path, "DutifulGame.java", "fa5b.java", JAVA_SAMPLE_CODE)

        runtime_path = (
            Path(project.path)
            / "core" / "src" / "main" / "java"
            / package_path / "runtime" / "DtfeSceneRuntime.java"
        )
        self._add_code_tab(
            tabs, runtime_path, "DtfeSceneRuntime.java", "fa5s.cogs", ""
        )

        try:
            bindings_path = ScreenStore(project.path).generate_java_bindings(project.package_name)
        except (OSError, ValueError, KeyError):
            bindings_path = runtime_path.parent / "DutifulSceneBindings.java"
        self._add_code_tab(
            tabs, bindings_path, "DutifulSceneBindings.java", "fa5s.link", ""
        )

        launcher_path = (
            Path(project.path)
            / "lwjgl3" / "src" / "main" / "java"
            / package_path / "lwjgl3" / "Lwjgl3Launcher.java"
        )
        self._add_code_tab(tabs, launcher_path, "Lwjgl3Launcher.java", "fa5s.desktop", "")

        if project.native_enabled:
            cpp_path = Path(project.path) / "native" / "src" / "main" / "cpp" / "native_performance.cpp"
            self._add_code_tab(tabs, cpp_path, "native_performance.cpp", "fa5s.microchip", "")

        panel.add_widget(tabs)
        return panel

    def _create_scene_viewport(self, screen: ScreenInfo) -> Viewport2D:
        if not self.current_project:
            raise RuntimeError("Chưa mở dự án.")
        scene_path = (Path(self.current_project.path) / screen.file).resolve()
        existing = self.scene_viewports.get(scene_path)
        if existing is not None:
            return existing
        viewport = Viewport2D(
            self.current_project.path,
            scene_path=scene_path,
            screen_id=screen.id,
        )
        self.scene_viewports[scene_path] = viewport
        viewport.selection_changed.connect(
            lambda payload, source=viewport: self._on_viewport_selection(source, payload)
        )
        viewport.status_message.connect(self._append_console)
        viewport.tool_changed.connect(self._on_viewport_tool_changed)
        viewport.history_changed.connect(self._on_viewport_history_changed)
        viewport.asset_editor_requested.connect(self._open_asset_editor)
        viewport.keyframe_editor_requested.connect(lambda payload, source=viewport: self._open_keyframe_editor(source, payload))
        viewport.event_mapping_requested.connect(lambda payload, source=viewport: self._configure_event_mapping(source, payload))
        viewport.automation_mapping_requested.connect(lambda payload, source=viewport: self._configure_automation_mapping(source, payload))
        viewport.scene_changed.connect(lambda source=viewport: self._on_viewport_scene_changed(source))
        viewport.screen_saved.connect(self._generate_scene_bindings)
        return viewport

    def _titleset_assets_imported(self, paths: list) -> None:
        if self.assets_panel is not None:
            self.assets_panel.refresh(Path(paths[-1]) if paths else None)
        self._append_console(f"[TitleSet] Đã import {len(paths)} tài nguyên bằng cửa sổ Windows và tự phân loại.")

    def _open_keyframe_editor(self, viewport: Viewport2D, payload: dict) -> None:
        if not self.current_project:
            return
        window = KeyframeEditorWindow(self.current_project.path, payload, parent=self)
        window.keyframes_applied.connect(
            lambda node_id, keyframes, anchor, source=viewport: source.apply_keyframe_data(node_id, keyframes, anchor)
        )
        window.destroyed.connect(
            lambda _obj=None, ref=window: self.keyframe_editor_windows.remove(ref) if ref in self.keyframe_editor_windows else None
        )
        self.keyframe_editor_windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()

    def _insert_asset_into_active_viewport(self, file_path: str) -> None:
        if self.viewport_2d is None:
            self._append_console('[TitleSet] Hãy mở một màn Preview 2D trước khi chèn tài nguyên.')
            return
        if self.viewport_2d.insert_asset_path(file_path):
            self._append_console(f'[TitleSet] Đã thêm {Path(file_path).name} vào Frame Preview và cập nhật scene/code bindings.')

    def _set_terrain_brush_on_active_viewport(self, file_path: str, tile_size: int, rule_mode: bool, erase: bool) -> None:
        if self.viewport_2d is None:
            self._append_console('[Terrain] Hãy mở một màn Preview 2D trước khi bật cọ.')
            return
        if self.viewport_2d.set_terrain_brush(file_path, tile_size, rule_mode, erase):
            mode = "Eraser" if erase else f"Material {Path(file_path).name}"
            self._append_console(f'[Terrain] {mode} · grid {tile_size}px · Rule Tile {"ON" if rule_mode else "OFF"}.')

    def _stop_terrain_paint_on_active_viewport(self) -> None:
        if self.viewport_2d is not None:
            self.viewport_2d.clear_terrain_brush()

    def _replace_asset_in_active_viewport(self, file_path: str) -> None:
        if self.viewport_2d is None:
            self._append_console('[TitleSet] Hãy mở một màn Preview 2D trước.')
            return
        if self.viewport_2d.replace_selected_asset(file_path):
            self._append_console(f'[TitleSet] Đã thay hình bằng {Path(file_path).name}; mapping nút/joystick được giữ nguyên.')
        else:
            self._append_console('[TitleSet] Hãy chọn một Sprite/nút/joystick trong Frame Preview trước khi thay hình.')

    def _insert_control_kit(self) -> None:
        if self.viewport_2d is None or not self.current_project:
            self._append_console('[TitleSet] Hãy mở màn Preview 2D trước.')
            return
        if self.viewport_2d.insert_control_kit():
            self._append_console('[TitleSet] Đã thêm bộ joystick đã ánh xạ di chuyển, nhân vật Player và các nút RUN/JUMP/ATTACK/INTERACT.')

    def _on_viewport_selection(self, viewport: Viewport2D, payload: dict) -> None:
        if viewport is not self.viewport_2d:
            return
        if self.inspector_panel is not None:
            self.inspector_panel.set_selection(payload)

    def _on_viewport_scene_changed(self, viewport: Viewport2D) -> None:
        if self.scene_panel is not None:
            self.scene_panel.current_screen_id = viewport.screen_id
            self.scene_panel.refresh(str(viewport.scene_file or ""))
        self._generate_scene_bindings(str(viewport.scene_file or ""))

    def _generate_scene_bindings(self, _scene_path: str = "") -> None:
        if not self.current_project:
            return
        try:
            output = ScreenStore(self.current_project.path).generate_java_bindings(
                self.current_project.package_name
            )
        except (OSError, ValueError, KeyError) as error:
            self._append_console(f"[Scene Bindings] Không thể tạo mã ánh xạ: {error}")
            return
        editor = self.code_editors.get(output.resolve())
        if editor is not None and not editor.document().isModified():
            try:
                editor.setPlainText(output.read_text(encoding="utf-8"))
                editor.document().setModified(False)
            except OSError:
                pass

    def _center_tab_changed(self, index: int) -> None:
        tabs = self.center_tabs
        if tabs is None or index < 0:
            return
        widget = tabs.widget(index)
        if not isinstance(widget, Viewport2D):
            return
        self.viewport_2d = widget
        self.active_scene_path = widget.scene_file.resolve() if widget.scene_file else None
        if self.current_project:
            try:
                ScreenStore(self.current_project.path).set_active(widget.screen_id)
            except (OSError, KeyError, ValueError):
                pass
        if self.scene_panel is not None:
            self.scene_panel.set_active_screen(widget.screen_id)
        if self.inspector_panel is not None:
            self.inspector_panel.set_selection(widget.camera_payload())
        widget.set_tool(widget.current_tool)

    def _update_active_viewport_property(self, key: str, value) -> None:
        if self.viewport_2d is not None:
            self.viewport_2d.update_selected_property(key, value)

    def _delete_active_viewport_selection(self) -> None:
        if self.viewport_2d is not None:
            self.viewport_2d.delete_selected()

    def _handle_inspector_action(self, action: str) -> None:
        viewport = self.viewport_2d
        if viewport is None:
            return
        if action in {"front", "forward", "backward", "back"}:
            viewport.move_selected_layer(action)
        elif action == "flip_h":
            viewport.flip_selected(True)
        elif action == "flip_v":
            viewport.flip_selected(False)
        elif action == "group":
            viewport.group_selected()
        elif action == "ungroup":
            viewport.ungroup_selected()
        elif action == "automation_mapping":
            self._configure_automation_mapping(viewport, viewport._selected_automation_payload())

    def _add_center_tab(
        self,
        widget: QWidget,
        icon_name: str,
        title: str,
        *,
        select: bool = True,
    ) -> int:
        tabs = self.center_tabs
        if tabs is None:
            return -1
        existing = tabs.indexOf(widget)
        if existing >= 0:
            if select:
                tabs.setCurrentIndex(existing)
            return existing
        index = tabs.addTab(widget, icon(icon_name), title)
        self._install_center_tab_close_button(index)
        if select:
            tabs.setCurrentIndex(index)
        return index

    def _install_center_tab_close_button(self, index: int) -> None:
        tabs = self.center_tabs
        if tabs is None or index < 0 or index >= tabs.count():
            return
        button = QToolButton(tabs.tabBar())
        button.setObjectName("CenterTabCloseButton")
        button.setIcon(icon("fa5s.times", "#A9B3C6"))
        button.setIconSize(QSize(12, 12))
        button.setFixedSize(23, 23)
        button.setToolTip("Đóng tab")
        widget = tabs.widget(index)
        button.clicked.connect(lambda _checked=False, target=widget: self._close_center_widget(target))
        tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, button)

    def _close_center_widget(self, widget: QWidget | None) -> None:
        tabs = self.center_tabs
        if tabs is None or widget is None:
            return
        index = tabs.indexOf(widget)
        if index < 0:
            return

        # Closing a source tab performs a lightweight autosave so the larger
        # close control and context menu cannot silently discard edits.
        for path, editor in list(self.code_editors.items()):
            if editor is widget:
                try:
                    if editor.document().isModified() or not path.exists():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(editor.toPlainText(), encoding="utf-8")
                        editor.document().setModified(False)
                        self._append_console(f"[Code] Đã tự lưu khi đóng tab: {path.name}")
                except OSError as error:
                    NoticeDialog("Không thể lưu tab", str(error), self, error=True).exec()
                    return
                self.code_editors.pop(path, None)

        tabs.removeTab(index)
        for path, preview in list(self.image_previews.items()):
            if preview is widget:
                self.image_previews.pop(path, None)
        if isinstance(widget, Viewport2D):
            for scene_path, viewport in list(self.scene_viewports.items()):
                if viewport is widget:
                    self.scene_viewports.pop(scene_path, None)
                    break
            if widget is self.viewport_2d:
                self.viewport_2d = None
                self.active_scene_path = None
            widget.deleteLater()
            current = tabs.currentWidget()
            if isinstance(current, Viewport2D):
                self._center_tab_changed(tabs.currentIndex())
        else:
            widget.deleteLater()

    def _show_center_tab_context_menu(self, position: QPoint) -> None:
        tabs = self.center_tabs
        if tabs is None:
            return
        bar = tabs.tabBar()
        clicked_index = bar.tabAt(position)
        if clicked_index >= 0:
            tabs.setCurrentIndex(clicked_index)

        menu = QMenu(self)
        close_current = QAction(icon("fa5s.times"), "Đóng tab", menu)
        close_current.setEnabled(clicked_index >= 0)
        close_current.triggered.connect(
            lambda _checked=False: self._close_center_widget(tabs.widget(clicked_index))
            if clicked_index >= 0 else None
        )
        close_others = QAction(icon("fa5s.window-close"), "Đóng các tab khác", menu)
        close_others.setEnabled(clicked_index >= 0 and tabs.count() > 1)
        close_others.triggered.connect(
            lambda _checked=False: self._close_other_center_tabs(clicked_index)
        )
        close_all = QAction(icon("fa5s.layer-group"), "Đóng tất cả tab", menu)
        close_all.setEnabled(tabs.count() > 0)
        close_all.triggered.connect(lambda _checked=False: self._close_all_center_tabs())
        menu.addAction(close_current)
        menu.addAction(close_others)
        menu.addSeparator()
        menu.addAction(close_all)
        menu.exec(bar.mapToGlobal(position))

    def _close_other_center_tabs(self, keep_index: int) -> None:
        tabs = self.center_tabs
        if tabs is None or keep_index < 0 or keep_index >= tabs.count():
            return
        keep_widget = tabs.widget(keep_index)
        for index in range(tabs.count() - 1, -1, -1):
            widget = tabs.widget(index)
            if widget is not keep_widget:
                self._close_center_widget(widget)

    def _close_all_center_tabs(self) -> None:
        tabs = self.center_tabs
        if tabs is None:
            return
        for index in range(tabs.count() - 1, -1, -1):
            self._close_center_widget(tabs.widget(index))

    def _screen_info_from_payload(self, payload: dict | None = None) -> ScreenInfo | None:
        if not self.current_project:
            return None
        store = ScreenStore(self.current_project.path)
        screens = store.screens()
        data = dict(payload or {})
        screen_id = str(data.get("screen_id") or data.get("id") or "")
        scene_file = str(data.get("scene_file") or data.get("file") or "").replace("\\", "/")
        if screen_id:
            match = next((item for item in screens if item.id == screen_id), None)
            if match is not None:
                return match
        if scene_file:
            normalized = scene_file.lower()
            match = next((item for item in screens if normalized.endswith(item.file.lower())), None)
            if match is not None:
                return match
        return store.active_screen()

    def _ensure_scene_tab(self, payload: dict | None = None) -> int:
        if not self.current_project:
            return -1
        screen = self._screen_info_from_payload(payload)
        if screen is None:
            return -1
        viewport = self._create_scene_viewport(screen)
        self.viewport_2d = viewport
        self.active_scene_path = viewport.scene_file.resolve() if viewport.scene_file else None
        index = self._add_center_tab(viewport, "fa5s.map", screen.name, select=True)
        try:
            ScreenStore(self.current_project.path).set_active(screen.id)
        except (OSError, KeyError, ValueError):
            pass
        if self.scene_panel is not None:
            self.scene_panel.set_active_screen(screen.id)
        if self.inspector_panel is not None:
            self.inspector_panel.set_selection(viewport.camera_payload())
        return index

    def _open_scene_node(self, payload: dict) -> None:
        index = self._ensure_scene_tab(payload)
        if index < 0 or self.viewport_2d is None:
            return
        self.viewport_2d.select_node(payload)
        node_name = str(payload.get("name") or payload.get("type") or "Scene")
        self._append_console(f"[Scene] Đã mở {node_name} trong tab Preview 2D.")

    def _handle_scene_structure_changed(self, structure: list) -> None:
        viewport = self.viewport_2d
        if viewport is None or not structure:
            return
        if viewport.apply_scene_structure(structure):
            self._append_console("[Scene] Đã cập nhật thứ tự lớp / nhóm từ bảng Scene.")
            if self.scene_panel is not None:
                self.scene_panel.refresh(str(viewport.scene_file))

    def _handle_scene_node_action(self, action: str, payload: dict) -> None:
        """Run the same component actions from the Scene tree and Preview 2D."""
        index = self._ensure_scene_tab(payload)
        if index < 0 or self.viewport_2d is None:
            return
        viewport = self.viewport_2d
        viewport.select_node(payload)
        if action == "asset_editor":
            viewport.open_selected_in_asset_editor()
        elif action == "rename":
            viewport.rename_selected()
        elif action == "duplicate":
            viewport.duplicate_selected()
        elif action in {"duplicate_clipping", "duplicate_clipping_mask"}:
            viewport.duplicate_selected(clipping_mask=True)
        elif action == "delete":
            viewport.delete_selected()
        elif action == "ungroup":
            viewport.ungroup_selected()
        elif action == "automation_mapping":
            self._configure_automation_mapping(viewport, viewport._selected_automation_payload())
        elif action in {"set_visible", "toggle_visible"}:
            value = payload.get("value", payload.get("visible", True))
            viewport.update_selected_property("visible", bool(value))
        elif action in {"set_locked", "toggle_locked"}:
            value = payload.get("value", payload.get("locked", False))
            viewport.update_selected_property("locked", bool(value))
        elif action == "event_mapping":
            self._configure_event_mapping(viewport, payload)
        elif action == "automation_mapping":
            self._configure_automation_mapping(viewport, payload)
        elif action in {"on_touch", "on_overlap", "screen_link"}:
            viewport.assign_basic_event(action)
        elif action in {"front", "forward", "backward", "back"}:
            viewport.move_selected_layer(action)

    def _configure_automation_mapping(self, viewport: Viewport2D, payload: dict) -> None:
        if not self.current_project:
            return
        viewport.select_node(payload)
        mapping = AutomationMappingDialog.get_mapping(ScreenStore(self.current_project.path).screens(), payload, self)
        if mapping is None:
            return
        if viewport.set_selected_automation(mapping):
            role = mapping.get("role", "custom")
            action = mapping.get("input_action", "")
            self._append_console(f"[Automation] {payload.get('name', 'Node')}: role={role}, input={action or 'none'}")

    def _configure_event_mapping(self, viewport: Viewport2D, payload: dict) -> None:
        if not self.current_project:
            return
        viewport.select_node(payload)
        mapping = EventMappingDialog.get_mapping(ScreenStore(self.current_project.path).screens(), payload, self)
        if mapping is None:
            return
        if viewport.set_selected_events(mapping):
            self._append_console(
                f"[Event] {payload.get('name', 'Node')}: {mapping['trigger']} → {mapping['action']}"
            )

    def _configure_map_transition(
        self,
        store: ScreenStore,
        *,
        source_id: str = "",
        target_id: str = "",
    ) -> bool:
        mapping = MapTransitionDialog.get_mapping(store.screens(), source_id, target_id, self)
        if mapping is None:
            return False
        store.add_transition(
            mapping["source"],
            mapping["target"],
            trigger=mapping["trigger"],
            bidirectional=bool(mapping["bidirectional"]),
        )
        self._generate_scene_bindings()
        self._append_console(
            f"[Screens] Đã nối map {mapping['source']} → {mapping['target']} ({mapping['trigger']})."
        )
        return True

    def _handle_screen_action(self, action: str, payload: dict) -> None:
        if not self.current_project:
            return
        store = ScreenStore(self.current_project.path)
        current = self._screen_info_from_payload(payload)
        try:
            if action == "create":
                source_before = current or store.active_screen()
                name, accepted = TextInputDialog.get_text(
                    self, "Thêm màn chơi", "Tên màn chơi mới:", text="Level 1"
                )
                if not accepted or not name.strip():
                    return
                target = store.create(name.strip())
                message = f"Đã tạo màn chơi '{target.name}'."
                if source_before is not None and ConfirmDialog.ask(
                    "Nối map mới",
                    f"Tạo ánh xạ sự kiện từ '{source_before.name}' sang '{target.name}'?",
                    self,
                    confirm_text="Tạo liên kết",
                ):
                    self._configure_map_transition(store, source_id=source_before.id, target_id=target.id)
            elif action == "rename" and current is not None:
                name, accepted = TextInputDialog.get_text(
                    self, "Đổi tên màn chơi", "Tên mới:", text=current.name
                )
                if not accepted or not name.strip():
                    return
                target = store.rename(current.id, name.strip())
                message = f"Đã đổi tên màn chơi thành '{target.name}'."
            elif action == "duplicate" and current is not None:
                name, accepted = TextInputDialog.get_text(
                    self, "Nhân đôi màn chơi", "Tên bản sao:", text=f"{current.name} Copy"
                )
                if not accepted or not name.strip():
                    return
                target = store.duplicate(current.id, name.strip())
                message = f"Đã nhân đôi thành màn '{target.name}'."
                if ConfirmDialog.ask(
                    "Nối map bản sao",
                    f"Tạo ánh xạ sự kiện từ '{current.name}' sang '{target.name}'?",
                    self,
                    confirm_text="Tạo liên kết",
                ):
                    self._configure_map_transition(store, source_id=current.id, target_id=target.id)
            elif action == "map_event":
                source = current.id if current is not None else store.active_screen().id
                self._configure_map_transition(store, source_id=source)
                return
            elif action == "delete" and current is not None:
                if current.id == "main":
                    NoticeDialog("Không thể xóa", "Màn Main là màn khởi động của project.", self, error=True).exec()
                    return
                confirmed = ConfirmDialog.ask(
                    "Xóa màn chơi",
                    f"Xóa màn '{current.name}' và tệp {Path(current.file).name}?",
                    self,
                    confirm_text="Xóa màn",
                    danger=True,
                )
                if not confirmed:
                    return
                removed_path = (Path(self.current_project.path) / current.file).resolve()
                target = store.delete(current.id)
                viewport = self.scene_viewports.pop(removed_path, None)
                if viewport is not None:
                    self._close_center_widget(viewport)
                target = store.active_screen()
                message = f"Đã xóa màn '{current.name}'."
            else:
                return
        except (OSError, ValueError, KeyError) as error:
            NoticeDialog("Không thể cập nhật màn chơi", str(error), self, error=True).exec()
            return
        self._generate_scene_bindings()
        if self.scene_panel is not None:
            self.scene_panel.current_screen_id = target.id
            self.scene_panel.refresh(str(store.path_for(target)))
        self._ensure_scene_tab({
            "screen_id": target.id, "scene_file": target.file, "name": target.name, "kind": "scene"
        })
        self._append_console(f"[Screens] {message}")

    def _add_code_tab(
        self,
        tabs: QTabWidget,
        path: Path,
        title: str,
        icon_name: str,
        fallback: str,
    ) -> int:
        resolved_path = path.expanduser().resolve()
        existing = self.code_editors.get(resolved_path)
        if existing is not None:
            existing_index = tabs.indexOf(existing)
            if existing_index >= 0:
                return existing_index
        language = (
            "cpp"
            if resolved_path.suffix.lower() in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
            else "java"
        )
        editor = CodeEditor(language=language)
        editor.set_source_path(resolved_path)
        try:
            editor.setPlainText(resolved_path.read_text(encoding="utf-8"))
        except OSError:
            editor.setPlainText(fallback)
        editor.document().setModified(False)
        editor.breakpoint_toggled.connect(
            lambda line, enabled, source=resolved_path: self._breakpoint_changed(source, line, enabled)
        )
        editor.set_diagnostics(self._diagnostics_for_path(resolved_path))
        self.code_editors[resolved_path] = editor
        index = tabs.addTab(editor, icon(icon_name), title)
        self._install_center_tab_close_button(index)
        return index

    def _open_asset_editor(self, file_path: str = "", destination_relative: str = "") -> None:
        """Open Editor Assets as a standalone frameless window."""
        if not self.current_project:
            NoticeDialog(
                "Chưa mở dự án",
                "Hãy mở một dự án 2Dutiful trước khi tạo hoặc chỉnh sửa tài nguyên.",
                self,
                error=True,
            ).exec()
            return
        initial = Path(file_path).resolve() if file_path else None
        if initial is not None and not initial.exists():
            initial = None
        destination = destination_relative.strip().replace("\\", "/")
        dialog = AssetEditorDialog(
            self.current_project.path,
            initial_file=initial,
            initial_destination=destination or None,
            parent=self,
        )
        scene_context = self.viewport_2d.take_asset_edit_context() if self.viewport_2d is not None else None
        if isinstance(scene_context, dict) and scene_context.get("mode") == "flatten_selection":
            raw_name = str(scene_context.get("name") or "edited_asset")
            safe_name = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in raw_name).strip("_") or "edited_asset"
            dialog.asset_name.setText(f"{safe_name}.png")
            dialog.allow_overwrite.setChecked(False)
        dialog.setProperty("sceneEditContext", scene_context or {})
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.asset_saved.connect(lambda saved, source=dialog: self._asset_editor_saved(saved, source))
        dialog.destroyed.connect(
            lambda _obj=None, ref=dialog: self.asset_editor_windows.remove(ref)
            if ref in self.asset_editor_windows else None
        )
        self.asset_editor_windows.append(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _asset_editor_saved(self, file_path: str, editor_window: AssetEditorDialog | None = None) -> None:
        path = Path(file_path).expanduser().resolve()
        if self.assets_panel is not None:
            self.assets_panel.refresh(path)
        if self.tileset_panel is not None:
            self.tileset_panel.refresh()
        context = editor_window.property("sceneEditContext") if editor_window is not None else {}
        target_viewport = None
        if isinstance(context, dict) and context.get("scene_file"):
            try:
                target_viewport = self.scene_viewports.get(Path(str(context["scene_file"])).resolve())
            except OSError:
                target_viewport = None
        if target_viewport is not None:
            target_viewport.apply_asset_editor_result(path, context)
        for viewport in self.scene_viewports.values():
            if viewport is not target_viewport:
                viewport.refresh_asset(path)
        try:
            relative = (
                path.relative_to(Path(self.current_project.path).resolve()).as_posix()
                if self.current_project else path.name
            )
        except ValueError:
            relative = path.name
        self._generate_scene_bindings(str(target_viewport.scene_file) if target_viewport is not None else "")
        self._append_console(
            f"[Editor Assets] Đã lưu, đồng bộ Preview và mã ánh xạ: project://{relative}."
        )

    def _open_asset_file(self, file_path: str) -> None:
        """Open source/text assets in the center editor; use Windows for binaries."""
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            NoticeDialog("Không tìm thấy tệp", str(path), self, error=True).exec()
            return

        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg"}:
            self._open_image_preview_tab(path)
            return

        text_suffixes = {
            ".java", ".kt", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
            ".json", ".dtfe", ".nova", ".xml", ".gradle", ".properties", ".md", ".txt",
            ".vert", ".frag", ".glsl", ".yaml", ".yml", ".csv", ".cmake",
        }
        is_text = path.suffix.lower() in text_suffixes or path.name in {
            "CMakeLists.txt", "build.gradle", "settings.gradle", "gradlew", "gradlew.bat"
        }
        if not is_text:
            self._open_generic_asset_tab(path)
            return

        tabs = self.center_tabs
        if tabs is None:
            return
        existing = self.code_editors.get(path)
        if existing is not None:
            index = tabs.indexOf(existing)
            if index >= 0:
                tabs.setCurrentIndex(index)
                existing.setFocus()
                return

        suffix = path.suffix.lower()
        if suffix == ".java":
            icon_name = "fa5b.java"
        elif suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}:
            icon_name = "fa5s.microchip"
        elif suffix in {".dtfe", ".nova", ".json"}:
            icon_name = "fa5s.cube"
        elif suffix in {".vert", ".frag", ".glsl"}:
            icon_name = "fa5s.magic"
        else:
            icon_name = "fa5s.file-code"
        index = self._add_code_tab(tabs, path, path.name, icon_name, "")
        tabs.setCurrentIndex(index)
        self.code_editors[path].setFocus()
        self._append_console(f"[Assets] Đã mở project://{path.relative_to(Path(self.current_project.path)).as_posix() if self.current_project else path.name}")

    def _open_generic_asset_tab(self, path: Path) -> None:
        tabs = self.center_tabs
        if tabs is None:
            return
        existing = self.image_previews.get(path)
        if existing is not None:
            index = tabs.indexOf(existing)
            if index >= 0:
                tabs.setCurrentIndex(index)
                return

        page = QWidget()
        page.setObjectName("AssetPreviewPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addStretch(1)

        file_icon = QLabel()
        file_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_icon.setPixmap(icon("fa5s.file", "#72A8FF").pixmap(56, 56))
        layout.addWidget(file_icon)

        name = QLabel(path.name)
        name.setObjectName("AssetPreviewTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        try:
            size_text = f"{path.stat().st_size / 1024:.1f} KB"
        except OSError:
            size_text = "Không đọc được kích thước"
        details = QLabel(f"{path.suffix.lower() or 'Tệp'}  •  {size_text}\n{path}")
        details.setObjectName("AssetPreviewDetails")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details.setWordWrap(True)
        layout.addWidget(details)

        open_button = QPushButton("Mở bằng ứng dụng mặc định")
        open_button.setIcon(icon("fa5s.external-link-alt"))
        open_button.setMaximumWidth(260)
        open_button.clicked.connect(
            lambda _checked=False: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        )
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(open_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)

        self.image_previews[path] = page
        self._add_center_tab(page, "fa5s.file", path.name, select=True)
        self._append_console(f"[Assets] Đã mở {path.name} trong tab tài nguyên.")

    def _open_image_preview_tab(self, path: Path) -> None:
        tabs = self.center_tabs
        if tabs is None:
            return
        existing = self.image_previews.get(path)
        if existing is not None:
            index = tabs.indexOf(existing)
            if index >= 0:
                tabs.setCurrentIndex(index)
                return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            NoticeDialog("Không thể xem ảnh", f"2Dutiful không thể đọc {path.name}.", self, error=True).exec()
            return

        page = QWidget()
        page.setObjectName("AssetPreviewPage")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        info = QLabel(f"{path.name}   •   {pixmap.width()} × {pixmap.height()} px")
        info.setObjectName("AssetPreviewInfo")
        info.setContentsMargins(12, 6, 12, 6)
        page_layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setObjectName("AssetPreviewScroll")
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        image_label = QLabel()
        image_label.setObjectName("AssetPreviewImage")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(pixmap)
        image_label.setMinimumSize(pixmap.size())
        scroll.setWidget(image_label)
        page_layout.addWidget(scroll, 1)

        self.image_previews[path] = page
        self._add_center_tab(page, "fa5s.image", path.name, select=True)
        self._append_console(f"[Assets] Đã mở {path.name} trong tab xem trước.")

    def _build_status_bar(self, project: ProjectInfo) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 8, 0)
        ready_icon = QLabel()
        ready_icon.setPixmap(icon("fa5s.circle", "#4BD37B").pixmap(9, 9))
        layout.addWidget(ready_icon)
        self.engine_state_label = QLabel("libGDX Ready")
        layout.addWidget(self.engine_state_label)
        layout.addSpacing(8)
        self.bottom_panel_button = QToolButton()
        self.bottom_panel_button.setObjectName("StatusBottomPanelButton")
        self.bottom_panel_button.setIcon(icon("fa5s.terminal"))
        self.bottom_panel_button.setIconSize(QSize(12, 12))
        self.bottom_panel_button.setToolTip("Hiện/ẩn Console, Problems, Debugger và Output (Ctrl+J)")
        self.bottom_panel_button.setFixedSize(25, 24)
        self.bottom_panel_button.setProperty("panelVisible", True)
        self.bottom_panel_button.clicked.connect(self._toggle_console_panel)
        layout.addWidget(self.bottom_panel_button)
        self.task_progress = BottomTaskProgress(self.root_frame)
        self.task_progress.attach_to_host(self.root_frame)
        self.task_progress.open_requested.connect(self._show_run_session)
        self.task_progress.cancel_requested.connect(self.runner.stop)
        self.task_progress.hide()
        path_label = QLabel(project.path)
        path_label.setObjectName("StatusPath")
        path_label.setToolTip(project.path)
        layout.addWidget(path_label, 1)
        java_label = QLabel("Java 17")
        libgdx_label = QLabel(f"libGDX {project.framework_version}")
        target_label = QLabel("LWJGL3 + Android on demand")
        native_text = "JNI/C++" if project.native_enabled else "Java only"
        native_label = QLabel(native_text)
        version_label = QLabel(f"v{ENGINE_VERSION}")
        self._status_optional_widgets = [target_label, native_label, java_label, libgdx_label]
        for widget in (java_label, libgdx_label, target_label, native_label, version_label):
            layout.addWidget(widget)
        layout.addWidget(QSizeGrip(bar), 0, Qt.AlignBottom | Qt.AlignRight)
        return bar

    def _save_open_files(self) -> bool:
        if not self.current_project:
            return False
        saved = 0
        try:
            for path, editor in self.code_editors.items():
                if not editor.document().isModified() and path.exists():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(editor.toPlainText(), encoding="utf-8")
                editor.document().setModified(False)
                saved += 1
        except OSError as error:
            NoticeDialog("Không thể lưu mã nguồn", str(error), self, error=True).exec()
            return False
        if self.viewport_2d is not None:
            # Scene writes are debounced; forcing focus change is unnecessary because
            # the viewport persists every edit itself.
            pass
        if saved:
            self._append_console(f"[2Dutiful] Đã lưu {saved} tệp mã nguồn.")
        return True

    def _prepare_runner_task(self) -> bool:
        if not self.current_project:
            NoticeDialog("Chưa mở dự án", "Hãy mở một dự án libGDX trước.", self, error=True).exec()
            return False
        if not self._save_open_files():
            return False
        self._clear_build_diagnostics()
        return True

    def _run_desktop(self) -> None:
        if not self._prepare_runner_task():
            return
        self.runner.run_desktop(self.current_project.path)

    def _debug_desktop(self) -> None:
        if not self._prepare_runner_task():
            return
        breakpoints = self._collect_breakpoints()
        self._set_console_visible(True)
        if self.console_tabs is not None and self.debugger_panel is not None:
            self.console_tabs.setCurrentWidget(self.debugger_panel)
        self._append_debugger(
            f"[2Dutiful] Bắt đầu debug với {len(breakpoints)} breakpoint. JVM sẽ tạm dừng tại cổng 5005.\n"
        )
        self.runner.debug_desktop(self.current_project.path, breakpoints)

    def _compile_java(self) -> None:
        if not self._prepare_runner_task():
            return
        if self.console_tabs is not None and self.problems_panel is not None:
            self.console_tabs.setCurrentWidget(self.problems_panel)
        self.runner.compile_java(self.current_project.path)

    def _run_gradle_task(self, task: str) -> None:
        if not self._prepare_runner_task():
            return
        self.runner.run_gradle(self.current_project.path, task)

    def _select_and_build_target(self, index: int) -> None:
        self._selected_build_target_index = max(0, min(index, len(BUILD_TARGETS) - 1))
        for action_index, action in enumerate(getattr(self, "_build_menu_actions", [])):
            action.setChecked(action_index == self._selected_build_target_index)
        self._update_build_button_label()
        self._build_selected_target()

    def _update_build_button_label(self) -> None:
        if not hasattr(self, "build_button"):
            return
        label = BUILD_TARGETS[self._selected_build_target_index][0]
        short_label = {
            "Compile Java (core + lwjgl3)": "Compile",
            "Desktop JAR (LWJGL3)": "JAR",
            "Desktop JAR + JAD": "JAR + JAD",
            "Android APK Debug": "APK Debug",
            "Android APK Release": "APK Release",
            "Android AAB Release": "AAB Release",
            "C/C++ Native DLL": "Native",
            "Clean Project": "Clean",
        }.get(label, label)
        self.build_button.setText(f"Build · {short_label}")
        self.build_button.setProperty("responsiveText", f"Build · {short_label}")
        self.build_button.setToolTip(f"Thực thi: {label}")

    def _build_selected_target(self) -> None:
        _label, _icon_name, command = BUILD_TARGETS[self._selected_build_target_index]
        if command == "compile":
            self._compile_java()
        elif command == "desktop_jad":
            self._build_desktop_jad()
        elif command == "native":
            self._build_native_windows()
        else:
            self._run_gradle_task(command)

    def _build_desktop_jad(self) -> None:
        if not self._prepare_runner_task():
            return
        self.runner.build_desktop_jad(self.current_project.path)

    def _build_native_windows(self) -> None:
        if not self.current_project:
            NoticeDialog("Chưa mở dự án", "Hãy mở một dự án libGDX trước.", self, error=True).exec()
            return
        if not self.current_project.native_enabled:
            NoticeDialog(
                "Module native đang tắt",
                "Dự án này sử dụng Java thuần và không có module JNI/CMake.",
                self,
            ).exec()
            return
        if not self._prepare_runner_task():
            return
        self.runner.run_native_windows(self.current_project.path)

    def _check_environment(self) -> None:
        if not self.current_project:
            NoticeDialog(
                "Chưa mở dự án",
                "Mở một dự án để kiểm tra Java, Gradle, JDB và cấu hình build.",
                self,
            ).exec()
            return
        self._clear_build_diagnostics()
        self.runner.check_environment(self.current_project.path)
        QTimer.singleShot(0, self._show_run_session)

    def _on_environment_checked(self, report: dict) -> None:
        required = list(report.get("missing_required", []))
        optional = list(report.get("missing_optional", []))
        missing = required + optional
        check_success = not required
        if self.run_session_dialog is not None and not self.runner.is_running:
            self.run_session_dialog.set_running(False, check_success)
        if self.task_progress is not None and not self.runner.is_running:
            self.task_progress.finish(check_success, "Sẵn sàng" if check_success else "Thiếu môi trường")
        if not missing:
            self.app_toast.show_message("Môi trường lập trình và thư viện đã sẵn sàng.")
            return
        packages = self.runner.environment_install_packages(report)
        details = ", ".join(missing)
        package_names = ", ".join(name for name, _package_id in packages)
        message = f"Không thể cập nhật/hoàn tất môi trường vì còn thiếu: {details}."
        if packages:
            message += f"\n\nBạn có muốn Install tự động: {package_names}?"
        else:
            message += "\n\nKhông có gói cài tự động phù hợp; hãy kiểm tra Gradle wrapper của project."
        if not packages or not ConfirmDialog.ask(
            "Install môi trường lập trình",
            message,
            self,
            confirm_text="Install",
        ):
            return
        if not self.runner.install_environment(report):
            NoticeDialog(
                "Không thể Install",
                "Không tìm thấy Windows Package Manager (winget) hoặc không có gói phù hợp. Hãy cài App Installer rồi thử lại.",
                self,
                error=True,
            ).exec()

    def _on_environment_install_completed(self, success: bool) -> None:
        if success:
            self.app_toast.show_message(
                "Đã cài/cập nhật môi trường. Hãy mở lại Engine để PATH mới có hiệu lực.",
                timeout_ms=10000,
            )
        else:
            NoticeDialog(
                "Install chưa hoàn tất",
                "Một gói môi trường không thể cài. Xem log trong hộp thoại để biết mã lỗi và thử lại.",
                self,
                error=True,
            ).exec()

    def _on_update_available(self, release: dict) -> None:
        version = str(release.get("version") or "")
        self._pending_update_url = str(release.get("url") or "")
        action = "Cập nhật" if self._pending_update_url else ""
        self.app_toast.show_message(
            f"Có 2Dutiful Engine {version}. Bạn đang dùng {ENGINE_VERSION}.",
            action_text=action,
            timeout_ms=20000,
        )

    def _on_update_current(self) -> None:
        if self.update_checker.last_check_was_manual:
            self.app_toast.show_message(f"2Dutiful Engine {ENGINE_VERSION} là phiên bản mới nhất.")

    def _on_update_failed(self, message: str) -> None:
        # Automatic checks stay quiet when offline; manual checks surface the error.
        self._append_console(f"[Update] {message}")
        if self.update_checker.last_check_was_manual:
            self.app_toast.show_message(f"Không thể kiểm tra cập nhật: {message}", timeout_ms=9000)

    def _open_pending_update(self) -> None:
        if self._pending_update_url:
            QDesktopServices.openUrl(QUrl(self._pending_update_url))

    def _append_console(self, text: str) -> None:
        if not text:
            return
        if self.console_log is None:
            self._console_backlog.append(text)
            return
        append_colored_log(self.console_log, text)
        if self.run_session_dialog is not None:
            self.run_session_dialog.append_output(text)
        if self.output_log is not None:
            append_colored_log(self.output_log, text)
        scrollbar = self.console_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_debugger(self, text: str) -> None:
        if not text:
            return
        if self.debugger_panel is not None:
            self.debugger_panel.append(text)
        else:
            self._console_backlog.append(text.rstrip("\n"))

    def _on_debugger_state(self, state: str) -> None:
        if self.debugger_panel is not None:
            self.debugger_panel.set_state(state)
        if getattr(self, "engine_state_label", None) is not None:
            self.engine_state_label.setText(state)

    def _on_phase_changed(self, phase: str) -> None:
        if getattr(self, "engine_state_label", None) is not None:
            self.engine_state_label.setText(phase or "libGDX Ready")
        if self.run_session_dialog is not None:
            self.run_session_dialog.set_phase(phase or "Đang chạy")
        if self.task_progress is not None and self.task_progress.isVisible():
            self.task_progress.set_phase(phase or "Đang chạy")

    def _on_runner_started(self, label: str) -> None:
        project_name = self.current_project.name if self.current_project else "Dự án"
        title = f"{label} • {project_name}"
        if self.run_session_dialog is None:
            self.run_session_dialog = RunSessionDialog("Run & Build", self)
            self.run_session_dialog.stop_requested.connect(self.runner.stop)
        # Keep the detailed monitor hidden, like Android Studio/VS Code. The user
        # can open it from the compact progress surface in the status bar.
        show_monitor = label.startswith("Kiểm tra môi trường") or label.startswith("Cài đặt môi trường")
        self.run_session_dialog.begin(title, show_window=show_monitor)
        if self.task_progress is not None:
            self.task_progress.begin(title)

    def _on_artifact_found(self, artifact_path: str) -> None:
        self._last_artifact = Path(artifact_path)
        self._append_console(f"[Build] Đầu ra: {artifact_path}")

    def _on_runner_finished(self, exit_code: int, success: bool) -> None:
        if self.run_session_dialog is not None:
            self.run_session_dialog.set_running(False, success)
            self.run_session_dialog.append_output(
                f"[2Dutiful] Tác vụ {'hoàn tất' if success else 'thất bại'} với mã {exit_code}."
            )
        if self.task_progress is not None:
            self.task_progress.finish(success, "Hoàn tất" if success else f"Lỗi {exit_code}")
        if not success and self._build_diagnostics and self.console_tabs is not None and self.problems_panel is not None:
            self._set_console_visible(True)
            self.console_tabs.setCurrentWidget(self.problems_panel)
        if success and self._last_artifact is not None:
            self._append_console(f"[Build] Hoàn tất. Artifact mới nhất: {self._last_artifact}")
        elif not success:
            self._append_console(f"[Build] Tác vụ thất bại với mã {exit_code}. Nhấp đúp Problems để tới dòng lỗi.")

    def _project_structure_changed(self, project_path: str) -> None:
        if self.current_project and Path(self.current_project.path).resolve() == Path(project_path).resolve():
            if self.assets_panel is not None:
                self.assets_panel.refresh(Path(project_path) / "android")
            self._append_console("[Assets] Cấu trúc dự án đã được cập nhật với module android.")

    def _runner_state_changed(self, running: bool) -> None:
        for attr in ("debug_button", "run_button", "build_button", "check_button", "adb_button"):
            button = getattr(self, attr, None)
            if button is not None:
                button.setEnabled(not running)
        stop_button = getattr(self, "stop_button", None)
        if stop_button is not None:
            stop_button.setEnabled(running)
        if not running and getattr(self, "engine_state_label", None) is not None:
            current = self.engine_state_label.text()
            if current not in {"Lỗi", "Lỗi tiến trình", "Debugger đã dừng"}:
                self.engine_state_label.setText("libGDX Ready")

    def _on_diagnostic(self, diagnostic: dict) -> None:
        normalized = dict(diagnostic)
        try:
            normalized["file"] = str(Path(str(normalized.get("file", ""))).resolve())
        except OSError:
            pass
        key = (
            normalized.get("file"), normalized.get("line"), normalized.get("column"),
            normalized.get("severity"), normalized.get("message"),
        )
        for item in self._build_diagnostics:
            other = (item.get("file"), item.get("line"), item.get("column"), item.get("severity"), item.get("message"))
            if other == key:
                return
        self._build_diagnostics.append(normalized)
        self._refresh_diagnostic_views()

    def _clear_build_diagnostics(self) -> None:
        self._build_diagnostics.clear()
        self._refresh_diagnostic_views()
        self._last_artifact = None

    def _refresh_diagnostic_views(self) -> None:
        if self.problems_panel is not None:
            self.problems_panel.set_diagnostics(self._build_diagnostics)
        for source_path, editor in self.code_editors.items():
            editor.set_diagnostics(self._diagnostics_for_path(source_path))

    def _diagnostics_for_path(self, path: Path) -> list[dict]:
        try:
            target = path.resolve()
        except OSError:
            target = path
        result: list[dict] = []
        for diagnostic in self._build_diagnostics:
            try:
                diagnostic_path = Path(str(diagnostic.get("file", ""))).resolve()
            except OSError:
                continue
            if diagnostic_path == target:
                result.append(diagnostic)
        return result

    def _open_diagnostic(self, diagnostic: dict) -> None:
        source = Path(str(diagnostic.get("file", ""))).expanduser()
        if not source.exists():
            self._append_console(f"[Problems] Không tìm thấy tệp: {source}")
            return
        self._open_asset_file(str(source))
        editor = self.code_editors.get(source.resolve())
        if editor is None:
            return
        try:
            line = int(diagnostic.get("line", 1))
            column = int(diagnostic.get("column", 1))
        except (TypeError, ValueError):
            line, column = 1, 1
        editor.go_to_line(line, column)

    def _breakpoint_changed(self, path: Path, line: int, enabled: bool) -> None:
        state = "đã bật" if enabled else "đã tắt"
        self._append_console(f"[Debug] Breakpoint {state}: {path.name}:{line}")

    def _collect_breakpoints(self) -> list[dict]:
        result: list[dict] = []
        for path, editor in self.code_editors.items():
            if path.suffix.lower() != ".java":
                continue
            class_name = self._java_class_name(path)
            if not class_name:
                continue
            for line in sorted(editor.breakpoints):
                result.append({"class": class_name, "line": int(line), "file": str(path)})
        return result

    def _java_class_name(self, path: Path) -> str:
        if not self.current_project:
            return ""
        root = Path(self.current_project.path)
        for source_root in (
            root / "core" / "src" / "main" / "java",
            root / "lwjgl3" / "src" / "main" / "java",
            root / "android" / "src" / "main" / "java",
        ):
            try:
                relative = path.resolve().relative_to(source_root.resolve())
            except ValueError:
                continue
            return ".".join(relative.with_suffix("").parts)
        return ""

    def _current_code_editor(self) -> CodeEditor | None:
        focused = QApplication.focusWidget()
        if isinstance(focused, CodeEditor):
            return focused
        if self.center_tabs is not None:
            widget = self.center_tabs.currentWidget()
            if isinstance(widget, CodeEditor):
                return widget
        return None

    def _dispatch_focused_editor_method(self, method_name: str) -> None:
        editor = self._current_code_editor()
        target = editor or QApplication.focusWidget()
        method = getattr(target, method_name, None) if target is not None else None
        if callable(method):
            method()

    def _undo_action(self) -> None:
        editor = self._current_code_editor()
        if editor is not None and editor.hasFocus():
            editor.undo()
        elif self.viewport_2d is not None:
            self.viewport_2d.undo()

    def _redo_action(self) -> None:
        editor = self._current_code_editor()
        if editor is not None and editor.hasFocus():
            editor.redo()
        elif self.viewport_2d is not None:
            self.viewport_2d.redo()

    def _duplicate_selected(self) -> None:
        if self.viewport_2d is not None:
            self._ensure_scene_tab()
            self.viewport_2d.duplicate_selected()

    def _frame_selection(self) -> None:
        if self.viewport_2d is not None:
            self._ensure_scene_tab()
            self.viewport_2d.frame_selection()

    def _reset_viewport(self) -> None:
        if self.viewport_2d is not None:
            self._ensure_scene_tab()
            self.viewport_2d.reset_view()

    def _zoom_viewport(self, factor: float) -> None:
        if self.viewport_2d is not None:
            self._ensure_scene_tab()
            self.viewport_2d.zoom_by(factor)

    def _toggle_console_panel(self) -> None:
        self._set_console_visible(not self._console_visible)

    def _set_console_visible(self, visible: bool) -> None:
        panel = self.console_panel
        splitter = self.center_workspace_column
        self._console_visible = bool(visible)
        if panel is None or splitter is None:
            if self.console_toggle_action is not None:
                self.console_toggle_action.setChecked(bool(visible))
            return
        if visible:
            panel.show()
            total = max(1, sum(splitter.sizes()))
            restored = max(130, min(self._console_last_height, int(total * 0.48)))
            splitter.setSizes([max(180, total - restored), restored])
        else:
            sizes = splitter.sizes()
            if len(sizes) > 1 and sizes[1] > 0:
                self._console_last_height = max(130, sizes[1])
            panel.hide()
            splitter.setSizes([max(1, sum(sizes)), 0])
        if self.console_toggle_action is not None:
            self.console_toggle_action.blockSignals(True)
            self.console_toggle_action.setChecked(bool(visible))
            self.console_toggle_action.blockSignals(False)
        button = getattr(self, "bottom_panel_button", None)
        if button is not None:
            button.setProperty("panelVisible", bool(visible))
            button.style().unpolish(button)
            button.style().polish(button)

    def _show_run_session(self) -> None:
        if self.run_session_dialog is None:
            return
        self.run_session_dialog.show()
        self.run_session_dialog.raise_()
        self.run_session_dialog.activateWindow()

    def _refresh_adb_devices(self) -> None:
        project_path = self.current_project.path if self.current_project else None
        if not self.adb_manager.refresh(project_path):
            self._prepare_adb_menu(refresh=False)

    def _on_adb_devices_changed(self, devices: list) -> None:
        self.adb_devices = [dict(item) for item in devices]
        available = [item for item in self.adb_devices if item.get("state") == "device"]
        serials = {str(item.get("serial", "")) for item in available}
        if self.selected_adb_serial not in serials:
            self.selected_adb_serial = str(available[0].get("serial", "")) if available else ""
        self._prepare_adb_menu(refresh=False)
        button = getattr(self, "adb_button", None)
        if button is not None:
            if self.selected_adb_serial:
                device = next((item for item in available if item.get("serial") == self.selected_adb_serial), available[0])
                button.setToolTip(f"Run Android qua ADB: {device.get('display') or self.selected_adb_serial}")
            else:
                button.setToolTip("Quét và chạy project trên thiết bị Android qua USB/Type-C")

    def _on_adb_error(self, message: str) -> None:
        self._append_console(f"[ADB] {message}")
        NoticeDialog("ADB / Thiết bị Android", message, self, error=True).exec()

    def _prepare_adb_menu(self, refresh: bool = True) -> None:
        menu = self.adb_menu
        if menu is None:
            return
        menu.clear()
        refresh_action = QAction(icon("fa5s.sync-alt"), "Làm mới thiết bị", menu)
        refresh_action.triggered.connect(self._refresh_adb_devices)
        menu.addAction(refresh_action)
        restart_action = QAction(icon("fa5s.redo-alt"), "Khởi động lại ADB server", menu)
        restart_action.triggered.connect(
            lambda _checked=False: self.adb_manager.restart_server(
                self.current_project.path if self.current_project else None
            )
        )
        menu.addAction(restart_action)
        menu.addSeparator()

        if not self.adb_devices:
            empty = QAction("Không có thiết bị — kết nối USB rồi bật USB debugging", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
        else:
            for device in self.adb_devices:
                serial = str(device.get("serial", ""))
                state = str(device.get("state", "unknown"))
                display = str(device.get("display") or serial)
                label = f"{display}  [{state}]"
                action = QAction(icon("fa5s.mobile-alt"), label, menu)
                action.setCheckable(True)
                action.setChecked(serial == self.selected_adb_serial)
                action.setEnabled(state == "device")
                action.triggered.connect(
                    lambda _checked=False, selected=serial: self._select_adb_device(selected)
                )
                menu.addAction(action)
        menu.addSeparator()
        self.adb_run_action = QAction(icon("fa5s.play"), "Build, cài và chạy trên thiết bị", menu)
        self.adb_run_action.setEnabled(bool(self.selected_adb_serial))
        self.adb_run_action.triggered.connect(self._run_android_on_device)
        menu.addAction(self.adb_run_action)
        if refresh and not self.adb_devices:
            QTimer.singleShot(0, self._refresh_adb_devices)

    def _select_adb_device(self, serial: str) -> None:
        self.selected_adb_serial = serial
        self._prepare_adb_menu(refresh=False)

    def _run_android_on_device(self) -> None:
        if not self.current_project:
            NoticeDialog("Chưa mở dự án", "Hãy mở một dự án trước khi chạy ADB.", self, error=True).exec()
            return
        if not self.selected_adb_serial:
            self._refresh_adb_devices()
            NoticeDialog(
                "Chưa chọn thiết bị Android",
                "Kết nối điện thoại bằng cáp USB/Type-C, bật Developer options và USB debugging, "
                "sau đó chấp nhận khóa RSA trên thiết bị rồi mở lại menu ADB.",
                self,
                warning=True,
            ).exec()
            return
        device = next(
            (item for item in self.adb_devices if item.get("serial") == self.selected_adb_serial),
            None,
        )
        if not device or device.get("state") != "device":
            state = str(device.get("state", "không xác định")) if device else "không tìm thấy"
            NoticeDialog(
                "Thiết bị ADB chưa sẵn sàng",
                f"Trạng thái thiết bị: {state}. Nếu là unauthorized, hãy mở khóa điện thoại và chấp nhận USB debugging.",
                self,
                warning=True,
            ).exec()
            return
        if not self._prepare_runner_task():
            return
        label = str(device.get("display") or self.selected_adb_serial)
        self.runner.run_android_device(
            self.current_project.path,
            self.selected_adb_serial,
            self.current_project.package_name,
            label,
        )

    def _set_panel_visible(self, attribute: str, visible: bool) -> None:
        widget = getattr(self, attribute, None)
        if widget is not None:
            widget.setVisible(bool(visible))

    def _open_current_project_folder(self) -> None:
        if self.current_project:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_project.path))

    def _on_viewport_tool_changed(self, tool_name: str) -> None:
        button = self._toolbar_tool_buttons_by_name.get(tool_name)
        if button is not None:
            for candidate in self._toolbar_tool_buttons:
                candidate.setChecked(candidate is button)

    def _on_viewport_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        undo_button = getattr(self, "undo_button", None)
        redo_button = getattr(self, "redo_button", None)
        if undo_button is not None:
            undo_button.setEnabled(bool(can_undo))
        if redo_button is not None:
            redo_button.setEnabled(bool(can_redo))

    def _toggle_maximize(self) -> None:
        """Compatibility wrapper used by older actions/tests."""
        self.window_state_controller.toggle_maximize_restore()

    def show_initial(self) -> None:
        self.window_state_controller.show_initial()

    def set_window_visible(self, visible: bool) -> None:
        """Hide/show the app without losing normal or maximized placement."""
        if visible:
            self.window_state_controller.show_window()
        else:
            self.window_state_controller.hide_window()

    def restore_from_title_drag(
        self,
        global_position: QPoint,
        horizontal_ratio: float,
        local_y: int,
    ) -> None:
        self.window_state_controller.restore_from_title_drag(
            global_position,
            horizontal_ratio,
            local_y,
        )

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            controller = getattr(self, "window_state_controller", None)
            if controller is not None:
                controller.handle_window_state_change()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        controller = getattr(self, "window_state_controller", None)
        if controller is not None:
            controller.handle_geometry_change()
        self._position_task_progress()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        controller = getattr(self, "window_state_controller", None)
        if controller is not None:
            controller.handle_geometry_change()
        self._apply_responsive_layout(event.size().width())
        self._position_task_progress()
        toast = getattr(self, "app_toast", None)
        if toast is not None and toast.isVisible():
            toast.move(max(12, self.root_frame.width() - toast.width() - 24), 48)

    def _apply_responsive_layout(self, width: int) -> None:
        """Keep controls reachable instead of allowing fixed layouts to clip."""
        compact = width < 1180
        very_compact = width < 1000
        title_bar = getattr(self, "title_bar", None)
        if title_bar is not None and hasattr(title_bar, "set_compact_mode"):
            title_bar.set_compact_mode(very_compact)
        home_page = getattr(self, "home_page", None)
        if home_page is not None and hasattr(home_page, "set_compact_mode"):
            home_page.set_compact_mode(width < 980)

        for button_name in ("debug_button", "run_button", "stop_button", "check_button", "build_button", "adb_button"):
            button = getattr(self, button_name, None)
            if button is None:
                continue
            text = str(button.property("responsiveText") or "")
            button.setText("" if compact else text)
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonIconOnly
                if compact else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
            )
            button.setMinimumWidth(31 if compact else 0)
        for index, button in enumerate(getattr(self, "_toolbar_tool_buttons", [])):
            # Keep core transform tools visible and move the rest into the overflow menu.
            button.setVisible(not very_compact or index < 6)
        overflow = getattr(self, "toolbar_overflow", None)
        if overflow is not None:
            overflow.setVisible(very_compact)
        for index, widget in enumerate(getattr(self, "_status_optional_widgets", [])):
            widget.setVisible(not very_compact or index >= 2)
        self._position_task_progress()

    def _position_task_progress(self) -> None:
        task = getattr(self, "task_progress", None)
        if task is not None and hasattr(task, "snap_to_default") and not task._drag_active:
            task.snap_to_default()

    def closeEvent(self, event) -> None:
        if self._closing:
            event.accept()
            return
        self._closing = True
        controller = getattr(self, "window_state_controller", None)
        if controller is not None:
            controller.save_persisted_placement()
        try:
            if self.runner.is_running:
                self.runner.stop()
            for process in (getattr(self.runner, "debugger", None), getattr(self.runner, "process", None)):
                if process is not None:
                    process.waitForFinished(1800)
        except Exception as error:
            self._append_console(f"[Warning] Không thể dừng hoàn toàn tiến trình con: {error}")

        for window_list_name in ("asset_editor_windows", "keyframe_editor_windows"):
            windows = list(getattr(self, window_list_name, []))
            for child in windows:
                try:
                    child.close()
                    child.deleteLater()
                except RuntimeError:
                    pass
            getattr(self, window_list_name, []).clear()

        for viewport in list(self.scene_viewports.values()):
            try:
                viewport.shutdown()
            except RuntimeError:
                pass
        self.scene_viewports.clear()
        self.viewport_2d = None
        QApplication.processEvents()
        event.accept()
        super().closeEvent(event)

    def _edge_at(self, position: QPoint) -> str | None:
        if self.isMaximized():
            return None
        rect = self.rect()
        margin = RESIZE_MARGIN
        left = position.x() <= margin
        right = position.x() >= rect.width() - margin
        top = position.y() <= margin
        bottom = position.y() >= rect.height() - margin
        if top and left: return "top_left"
        if top and right: return "top_right"
        if bottom and left: return "bottom_left"
        if bottom and right: return "bottom_right"
        if left: return "left"
        if right: return "right"
        if top: return "top"
        if bottom: return "bottom"
        return None

    _CURSORS = {
        "left": Qt.SizeHorCursor,
        "right": Qt.SizeHorCursor,
        "top": Qt.SizeVerCursor,
        "bottom": Qt.SizeVerCursor,
        "top_left": Qt.SizeFDiagCursor,
        "bottom_right": Qt.SizeFDiagCursor,
        "top_right": Qt.SizeBDiagCursor,
        "bottom_left": Qt.SizeBDiagCursor,
    }

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            edge = self._edge_at(event.position().toPoint())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._drag_start_geo = self.geometry()
                self._drag_start_pos = event.globalPosition().toPoint()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._resize_edge:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            geometry = self._drag_start_geo
            x, y, width, height = (
                geometry.x(), geometry.y(), geometry.width(), geometry.height()
            )
            edge = self._resize_edge
            min_width, min_height = self.minimumWidth(), self.minimumHeight()

            if "left" in edge:
                new_width = max(min_width, width - delta.x())
                x += width - new_width
                width = new_width
            if "right" in edge:
                width = max(min_width, width + delta.x())
            if "top" in edge:
                new_height = max(min_height, height - delta.y())
                y += height - new_height
                height = new_height
            if "bottom" in edge:
                height = max(min_height, height + delta.y())
            self.setGeometry(x, y, width, height)
            event.accept()
            return

        edge = self._edge_at(event.position().toPoint())
        self.setCursor(QCursor(self._CURSORS.get(edge, Qt.ArrowCursor)))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resizing = False
        self._resize_edge = None
        super().mouseReleaseEvent(event)


def configure_crash_diagnostics() -> None:
    """Capture Python/native traces and prefer a stable Windows graphics path."""
    global _CRASH_LOG_HANDLE
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")
    try:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "2Dutiful" / "logs"
        base.mkdir(parents=True, exist_ok=True)
        _CRASH_LOG_HANDLE = (base / "native_crash.log").open("a", encoding="utf-8")
        faulthandler.enable(_CRASH_LOG_HANDLE, all_threads=True)
    except (OSError, RuntimeError):
        _CRASH_LOG_HANDLE = None

    def exception_hook(exc_type, exc_value, exc_traceback):
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        if _CRASH_LOG_HANDLE is not None:
            try:
                _CRASH_LOG_HANDLE.write(message + "\n")
                _CRASH_LOG_HANDLE.flush()
            except OSError:
                pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = exception_hook


def load_stylesheet(app: QApplication) -> None:
    path = Path(__file__).parent / "resources" / "dark_theme.qss"
    app.setStyleSheet(path.read_text(encoding="utf-8"))


def configure_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dutiful2D.Engine.4.1")
    except Exception:
        pass


def main() -> None:
    configure_crash_diagnostics()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    configure_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("2Dutiful Engine")
    app.setOrganizationName("2Dutiful")
    app.setOrganizationDomain("2dutiful.local")
    app.setWindowIcon(app_icon())
    load_stylesheet(app)
    window = MainWindow()
    window.show_initial()
    exit_code = app.exec()
    try:
        if _CRASH_LOG_HANDLE is not None:
            _CRASH_LOG_HANDLE.flush()
    except OSError:
        pass
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
