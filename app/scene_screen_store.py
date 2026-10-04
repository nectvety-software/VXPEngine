"""Screen registry and C binding generation for VXPEngine (MRE VXP, core coremre).

This module deliberately has no Qt dependency so project/screen operations can be
unit-tested and reused by build scripts.
"""
from __future__ import annotations

import copy
import json
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

SCREEN_REGISTRY_FILE = "assets/scenes/screens.dtfe"
DEFAULT_SCREEN_FILE = "assets/scenes/main.dtfe"


def _ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def slugify(value: str, fallback: str = "screen") -> str:
    text = re.sub(r"[^a-z0-9]+", "_", _ascii(value).lower()).strip("_")
    text = re.sub(r"_+", "_", text) or fallback
    if text[0].isdigit():
        text = f"screen_{text}"
    return text[:64].rstrip("_") or fallback


def c_identifier(value: str, fallback: str = "Screen") -> str:
    words = [part for part in re.split(r"[^A-Za-z0-9]+", _ascii(value)) if part]
    result = "".join(part[:1].upper() + part[1:] for part in words) or fallback
    if result[0].isdigit():
        result = f"Screen{result}"
    return result


def c_constant(value: str, fallback: str = "NODE") -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", _ascii(value)).strip("_").upper()
    text = re.sub(r"_+", "_", text) or fallback
    if text[0].isdigit():
        text = f"NODE_{text}"
    return text


def _atomic_json_write(path: Path, payload: dict) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        existing = None
    if existing == content:
        return  # không đổi — khỏi ghi, tránh đụng file đang bị khóa
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    last_error: OSError | None = None
    for attempt in range(4):
        try:
            temporary.replace(path)
            return
        except OSError as error:
            # Windows có thể giữ file tạm thời (AV / OneDrive / tiến trình IDE cũ).
            last_error = error
            time.sleep(0.05 * (attempt + 1))
    try:
        path.write_text(content, encoding="utf-8")
    except OSError:
        raise last_error from None
    try:
        temporary.unlink()
    except OSError:
        pass


@dataclass(frozen=True, slots=True)
class ScreenInfo:
    id: str
    name: str
    file: str
    code_name: str

    @classmethod
    def from_dict(cls, payload: dict) -> "ScreenInfo":
        screen_id = slugify(str(payload.get("id") or payload.get("name") or "screen"))
        name = str(payload.get("name") or screen_id).strip() or screen_id
        file_value = str(payload.get("file") or f"assets/scenes/{screen_id}.dtfe").replace("\\", "/")
        return cls(screen_id, name, file_value, c_identifier(str(payload.get("code_name") or payload.get("java_name") or name)))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "file": self.file, "code_name": self.code_name}


class ScreenStore:
    """Manage named level screens for VXPEngine MRE VXP projects."""

    def __init__(self, project_path: str | Path) -> None:
        self.root = Path(project_path).expanduser().resolve()
        self.registry_path = self.root / SCREEN_REGISTRY_FILE

    def ensure(self) -> dict:
        scene_path = self.root / DEFAULT_SCREEN_FILE
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        if not scene_path.exists():
            _atomic_json_write(scene_path, self.blank_scene("Main", "main"))
        else:
            self._upgrade_scene(scene_path, "Main", "main")

        registry = self._read_registry()
        screens = [ScreenInfo.from_dict(item) for item in registry.get("screens", []) if isinstance(item, dict)]
        if not any(item.id == "main" for item in screens):
            screens.insert(0, ScreenInfo("main", "Main", DEFAULT_SCREEN_FILE, "Main"))
        # Remove duplicate IDs/files while retaining order.
        deduped: list[ScreenInfo] = []
        seen_ids: set[str] = set()
        seen_files: set[str] = set()
        for item in screens:
            if item.id in seen_ids or item.file.lower() in seen_files:
                continue
            seen_ids.add(item.id)
            seen_files.add(item.file.lower())
            deduped.append(item)
            path = self.root / item.file
            if path.exists():
                self._upgrade_scene(path, item.name, item.id)
        active = str(registry.get("active_screen") or "main")
        if active not in seen_ids:
            active = "main"
        transitions = [dict(item) for item in registry.get("transitions", []) if isinstance(item, dict)]
        valid_ids = {item.id for item in deduped}
        transitions = [item for item in transitions if str(item.get("from", "")) in valid_ids and str(item.get("to", "")) in valid_ids]
        payload = {
            "format": "VXPEngine Screen Registry",
            "format_version": 2,
            "active_screen": active,
            "screens": [item.to_dict() for item in deduped],
            "transitions": transitions,
        }
        _atomic_json_write(self.registry_path, payload)
        return payload

    def _read_registry(self) -> dict:
        if not self.registry_path.exists():
            return {}
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def screens(self) -> list[ScreenInfo]:
        return [ScreenInfo.from_dict(item) for item in self.ensure().get("screens", [])]

    def active_screen(self) -> ScreenInfo:
        registry = self.ensure()
        active = str(registry.get("active_screen") or "main")
        screens = [ScreenInfo.from_dict(item) for item in registry.get("screens", []) if isinstance(item, dict)]
        return next((item for item in screens if item.id == active), screens[0])

    def set_active(self, screen_id: str) -> ScreenInfo:
        registry = self.ensure()
        screens = [ScreenInfo.from_dict(item) for item in registry["screens"]]
        selected = next((item for item in screens if item.id == screen_id), None)
        if selected is None:
            raise KeyError(f"Không tìm thấy màn chơi: {screen_id}")
        registry["active_screen"] = selected.id
        _atomic_json_write(self.registry_path, registry)
        return selected

    def path_for(self, screen: ScreenInfo | str) -> Path:
        if isinstance(screen, ScreenInfo):
            return self.root / screen.file
        info = next((item for item in self.screens() if item.id == screen), None)
        if info is None:
            raise KeyError(f"Không tìm thấy màn chơi: {screen}")
        return self.root / info.file

    def create(self, name: str, *, width: int | None = None, height: int | None = None) -> ScreenInfo:
        clean = str(name).strip()
        if not clean:
            raise ValueError("Tên màn chơi không được để trống.")
        registry = self.ensure()
        if width is None or height is None:
            active_id = str(registry.get("active_screen") or "main")
            active_raw = next((item for item in registry.get("screens", []) if isinstance(item, dict) and str(item.get("id", "")) == active_id), None)
            active_info = ScreenInfo.from_dict(active_raw) if active_raw else ScreenInfo("main", "Main", DEFAULT_SCREEN_FILE, "Main")
            active_scene = self.read_scene(self.root / active_info.file)
            viewport = active_scene.get("viewport") if isinstance(active_scene.get("viewport"), dict) else {}
            try:
                inherited_width = max(64, int(viewport.get("width", 1280)))
                inherited_height = max(64, int(viewport.get("height", 720)))
            except (TypeError, ValueError):
                inherited_width, inherited_height = 1280, 720
            width = inherited_width if width is None else width
            height = inherited_height if height is None else height
        width = max(64, int(width))
        height = max(64, int(height))
        existing = [ScreenInfo.from_dict(item) for item in registry["screens"]]
        base = slugify(clean)
        screen_id = base
        index = 2
        while any(item.id == screen_id for item in existing) or (self.root / f"assets/scenes/{screen_id}.dtfe").exists():
            screen_id = f"{base}_{index}"
            index += 1
        info = ScreenInfo(screen_id, clean, f"assets/scenes/{screen_id}.dtfe", c_identifier(clean))
        _atomic_json_write(self.root / info.file, self.blank_scene(clean, screen_id, width, height))
        registry["screens"].append(info.to_dict())
        registry["active_screen"] = info.id
        _atomic_json_write(self.registry_path, registry)
        return info

    def rename(self, screen_id: str, new_name: str) -> ScreenInfo:
        clean = str(new_name).strip()
        if not clean:
            raise ValueError("Tên màn chơi không được để trống.")
        registry = self.ensure()
        result: ScreenInfo | None = None
        for index, raw in enumerate(registry["screens"]):
            info = ScreenInfo.from_dict(raw)
            if info.id != screen_id:
                continue
            result = ScreenInfo(info.id, clean, info.file, c_identifier(clean))
            registry["screens"][index] = result.to_dict()
            scene_path = self.root / info.file
            payload = self.read_scene(scene_path)
            payload["name"] = clean
            payload["screen_id"] = info.id
            _atomic_json_write(scene_path, payload)
            break
        if result is None:
            raise KeyError(f"Không tìm thấy màn chơi: {screen_id}")
        _atomic_json_write(self.registry_path, registry)
        return result

    def duplicate(self, screen_id: str, new_name: str | None = None) -> ScreenInfo:
        source = next((item for item in self.screens() if item.id == screen_id), None)
        if source is None:
            raise KeyError(f"Không tìm thấy màn chơi: {screen_id}")
        target = self.create(new_name or f"{source.name} Copy")
        payload = copy.deepcopy(self.read_scene(self.root / source.file))
        payload["name"] = target.name
        payload["screen_id"] = target.id
        # Preserve node IDs for duplicate screens? No: IDs are scoped by screen, but
        # fresh IDs make code bindings unambiguous when scenes are merged later.
        for node in payload.get("children", []):
            if isinstance(node, dict) and "camera" not in str(node.get("type", "")).lower():
                node["id"] = uuid.uuid4().hex[:12]
        for group in payload.get("groups", []):
            if isinstance(group, dict):
                old_id = str(group.get("id", ""))
                new_id = f"group_{uuid.uuid4().hex[:10]}"
                group["id"] = new_id
                for node in payload.get("children", []):
                    if isinstance(node, dict) and str(node.get("group_id", "")) == old_id:
                        node["group_id"] = new_id
        _atomic_json_write(self.root / target.file, payload)
        return target

    def transitions(self) -> list[dict]:
        return [dict(item) for item in self.ensure().get("transitions", []) if isinstance(item, dict)]

    def add_transition(
        self,
        source_id: str,
        target_id: str,
        *,
        trigger: str = "on_overlap",
        event_name: str = "change_screen",
        bidirectional: bool = False,
    ) -> dict:
        registry = self.ensure()
        valid_ids = {ScreenInfo.from_dict(item).id for item in registry.get("screens", []) if isinstance(item, dict)}
        if source_id not in valid_ids or target_id not in valid_ids:
            raise KeyError("Màn nguồn hoặc màn đích không tồn tại.")
        transition = {
            "id": f"transition_{uuid.uuid4().hex[:10]}",
            "from": source_id,
            "to": target_id,
            "trigger": str(trigger or "on_overlap"),
            "action": str(event_name or "change_screen"),
        }
        registry.setdefault("transitions", []).append(transition)
        if bidirectional and source_id != target_id:
            registry["transitions"].append({
                "id": f"transition_{uuid.uuid4().hex[:10]}",
                "from": target_id,
                "to": source_id,
                "trigger": str(trigger or "on_overlap"),
                "action": str(event_name or "change_screen"),
            })
        _atomic_json_write(self.registry_path, registry)
        return transition

    def remove_transition(self, transition_id: str) -> bool:
        registry = self.ensure()
        before = len(registry.get("transitions", []))
        registry["transitions"] = [
            item for item in registry.get("transitions", [])
            if not isinstance(item, dict) or str(item.get("id", "")) != str(transition_id)
        ]
        changed = len(registry["transitions"]) != before
        if changed:
            _atomic_json_write(self.registry_path, registry)
        return changed

    def delete(self, screen_id: str, *, remove_file: bool = True) -> ScreenInfo:
        registry = self.ensure()
        screens = [ScreenInfo.from_dict(item) for item in registry["screens"]]
        target = next((item for item in screens if item.id == screen_id), None)
        if target is None:
            raise KeyError(f"Không tìm thấy màn chơi: {screen_id}")
        if target.id == "main":
            raise ValueError("Màn Main là màn khởi động và không thể xóa.")
        remaining = [item for item in screens if item.id != target.id]
        registry["screens"] = [item.to_dict() for item in remaining]
        registry["transitions"] = [
            item for item in registry.get("transitions", [])
            if isinstance(item, dict) and str(item.get("from", "")) != target.id and str(item.get("to", "")) != target.id
        ]
        if registry.get("active_screen") == target.id:
            registry["active_screen"] = "main"
        _atomic_json_write(self.registry_path, registry)
        if remove_file:
            try:
                (self.root / target.file).unlink(missing_ok=True)
            except OSError:
                pass
        return target

    @staticmethod
    def blank_scene(name: str, screen_id: str, width: int = 240, height: int = 320) -> dict:
        return {
            "name": name,
            "screen_id": screen_id,
            "type": "VXPScene",
            "viewport": {"type": "FitViewport", "width": int(width), "height": int(height)},
            "groups": [],
            "children": [
                {
                    "id": "camera2d",
                    "code_name": "Camera2D",
                    "name": "Camera2D",
                    "type": "OrthographicCamera",
                    "position": [0, 0],
                    "rotation": 0.0,
                    "zoom": [1.0, 1.0],
                }
            ],
        }

    @staticmethod
    def read_scene(path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _upgrade_scene(self, path: Path, default_name: str, screen_id: str) -> None:
        payload = self.read_scene(path)
        if not payload:
            payload = self.blank_scene(default_name, screen_id)
        changed = False
        if not payload.get("name"):
            payload["name"] = default_name
            changed = True
        if payload.get("screen_id") != screen_id:
            payload["screen_id"] = screen_id
            changed = True
        if not isinstance(payload.get("groups"), list):
            payload["groups"] = []
            changed = True
        children = payload.get("children")
        if not isinstance(children, list):
            payload["children"] = self.blank_scene(default_name, screen_id)["children"]
            children = payload["children"]
            changed = True
        used_codes: set[str] = set()
        for node in children:
            if not isinstance(node, dict):
                continue
            if not node.get("id"):
                node["id"] = "camera2d" if "camera" in str(node.get("type", "")).lower() else uuid.uuid4().hex[:12]
                changed = True
            base = c_identifier(str(node.get("code_name") or node.get("name") or node.get("type") or "Node"), "Node")
            code = base
            suffix = 2
            while code.lower() in used_codes:
                code = f"{base}{suffix}"
                suffix += 1
            used_codes.add(code.lower())
            if node.get("code_name") != code:
                node["code_name"] = code
                changed = True
            node.setdefault("locked", False)
            node.setdefault("blend_mode", "Normal")
            node.setdefault("tint", "#FFFFFFFF")
            node.setdefault("events", [])
            node.setdefault("automation", {})
            node.setdefault("clipping_mask", {})
        if changed:
            _atomic_json_write(path, payload)

    def generate_c_bindings(self) -> Path:
        """Generate src/scene_bindings.h with flat C defines for the coremre core."""
        registry = self.ensure()
        screens = [ScreenInfo.from_dict(item) for item in registry["screens"]]
        active_id = str(registry.get("active_screen") or "main")
        active_prefix: str | None = None
        self.last_component_rows: list[dict] = []
        lines: list[str] = []
        lines.append(dedent("""
            /* Generated by VXPEngine - do not edit manually.
             * Identifiers for screens and components designed in the 2D workspace.
             * Regenerated whenever a scene is saved.
             */
            #ifndef VXP_SCENE_BINDINGS_H
            #define VXP_SCENE_BINDINGS_H

            /* VXPE_GENERATED_SCENE_BINDINGS_V1 */

            /* Bảng component của màn thiết kế Camera 2D — build đọc bảng này để
             * vẽ đúng vị trí/kích thước đã thiết kế. */
            typedef struct VxpDesignComponent {
                const char* id;
                const char* type;
                const char* asset;
                const char* res;   /* sprite .raw đóng gói sẵn ("" nếu không có ảnh) */
                float x;
                float y;
                float rotation;
                float scale_x;
                float scale_y;
                float width;
                float height;
                int z_index;
                int visible;
            } VxpDesignComponent;
        """).rstrip())
        lines.append("")

        lines.append("/* Screens */")
        used_screen_constants: set[str] = set()
        for screen in screens:
            constant = c_constant(screen.name, "SCREEN")
            base = constant
            index = 2
            while constant in used_screen_constants:
                constant = f"{base}_{index}"
                index += 1
            used_screen_constants.add(constant)
            runtime_path = screen.file.replace("\\", "/")
            if runtime_path.startswith("assets/"):
                runtime_path = runtime_path[len("assets/"):]
            lines.append(f'#define SCREEN_{constant} "{runtime_path}"')
        lines.append("")

        lines.append("/* Transitions */")
        for index, transition in enumerate(self.transitions(), 1):
            source_id = str(transition.get("from", "")).replace('"', '\\"')
            target_id = str(transition.get("to", "")).replace('"', '\\"')
            trigger = str(transition.get("trigger", "on_overlap")).replace('"', '\\"')
            action = str(transition.get("action", "change_screen")).replace('"', '\\"')
            lines.append(f'#define LINK_{index}_FROM "{source_id}"')
            lines.append(f'#define LINK_{index}_TO "{target_id}"')
            lines.append(f'#define LINK_{index}_TRIGGER "{trigger}"')
            lines.append(f'#define LINK_{index}_ACTION "{action}"')
        lines.append("")

        used_classes: set[str] = set()
        for screen in screens:
            scene_path = self.root / screen.file
            self._upgrade_scene(scene_path, screen.name, screen.id)
            scene = self.read_scene(scene_path)
            prefix = c_constant(screen.code_name or screen.name, "SCREEN")
            base_prefix = prefix
            suffix = 2
            while prefix in used_classes:
                prefix = f"{base_prefix}_{suffix}"
                suffix += 1
            used_classes.add(prefix)
            lines.append(f"/* Screen: {screen.name} */")
            lines.append(f'#define {prefix}_ID "{screen.id}"')
            runtime_path = screen.file.replace("\\", "/")
            if runtime_path.startswith("assets/"):
                runtime_path = runtime_path[len("assets/"):]
            lines.append(f'#define {prefix}_FILE "{runtime_path}"')
            camera_node = next(
                (
                    child for child in scene.get("children", [])
                    if isinstance(child, dict)
                    and "camera" in str(child.get("type", "")).lower()
                ),
                {},
            )
            perspective = camera_node.get("frame_perspective")
            if not isinstance(perspective, dict):
                perspective = {}
            perspective_kind = str(perspective.get("kind", "none")).replace('"', '\\"')
            perspective_projection = str(perspective.get("projection", "orthographic")).replace('"', '\\"')
            perspective_axes = str(perspective.get("movement_axes", "none")).replace('"', '\\"')
            try:
                perspective_angle = int(perspective.get("camera_angle", 0))
            except (TypeError, ValueError):
                perspective_angle = 0
            lines.append(f'#define {prefix}_FRAME_PERSPECTIVE "{perspective_kind}"')
            lines.append(f'#define {prefix}_FRAME_PROJECTION "{perspective_projection}"')
            lines.append(f'#define {prefix}_MOVEMENT_AXES "{perspective_axes}"')
            lines.append(f"#define {prefix}_CAMERA_ANGLE {perspective_angle}")
            # Camera2D describes the viewport itself; it is not a renderable UI/
            # sprite component and must not inflate the generated runtime table.
            nodes = [
                child for child in scene.get("children", [])
                if isinstance(child, dict)
                and "camera" not in str(child.get("type", "")).lower()
                and not bool(child.get("editor_guide", False))
            ]
            lines.append(f"#define {prefix}_COMPONENT_COUNT {len(nodes)}")
            lines.append(f"#define {prefix}_HAS_DESIGN {1 if nodes else 0}")
            lines.append("")

            used_constants: set[str] = set()
            input_bindings: list[tuple[str, str]] = []
            role_bindings: list[tuple[str, str]] = []
            component_rows: list[dict] = []
            for node in nodes:
                display = str(node.get("code_name") or node.get("name") or node.get("type") or "Node")
                constant = c_constant(display)
                base = constant
                index = 2
                while constant in used_constants:
                    constant = f"{base}_{index}"
                    index += 1
                used_constants.add(constant)
                node_id = str(node.get("id") or display)
                node_name = str(node.get("name") or display).replace('"', '\\"')
                lines.append(f'#define {prefix}_{constant} "{node_id}" /* {node_name} */')
                position = node.get("position") if isinstance(node.get("position"), list) else [0, 0]
                scale = node.get("scale") if isinstance(node.get("scale"), list) else [1, 1]

                def number(values, index, fallback):
                    try:
                        return float(values[index])
                    except (TypeError, ValueError, IndexError):
                        return float(fallback)

                px, py = number(position, 0, 0), number(position, 1, 0)
                sx = number(scale, 0, 1)
                sy = number(scale, 1, sx)
                rotation = number([node.get("rotation", 0)], 0, 0)
                opacity = number([node.get("opacity", 1)], 0, 1)
                z_index = int(number([node.get("z_index", 0)], 0, 0))
                visible = "1" if bool(node.get("visible", True)) else "0"
                node_type = str(node.get("type", "Node")).replace('"', '\\"')
                asset = str(node.get("asset", "")).replace('"', '\\"')
                background_bitmap = str(node.get("background_bitmap", "")).replace('"', '\\"')
                background_bitmap_mode = str(node.get("background_bitmap_mode", "Fill")).replace('"', '\\"')
                render_asset = asset or background_bitmap
                blend = str(node.get("blend_mode", "Normal")).replace('"', '\\"')
                tint = str(node.get("tint", "#FFFFFFFF")).replace('"', '\\"')
                lines.append(f"#define {prefix}_{constant}_X {px:.4f}f")
                lines.append(f"#define {prefix}_{constant}_Y {py:.4f}f")
                lines.append(f"#define {prefix}_{constant}_ROTATION {rotation:.4f}f")
                lines.append(f"#define {prefix}_{constant}_SCALE_X {sx:.4f}f")
                lines.append(f"#define {prefix}_{constant}_SCALE_Y {sy:.4f}f")
                display_size = node.get("display_size") if isinstance(node.get("display_size"), list) else [0, 0]
                display_width = number(display_size, 0, 0)
                display_height = number(display_size, 1, 0)
                lines.append(f"#define {prefix}_{constant}_DISPLAY_WIDTH {display_width:.4f}f")
                lines.append(f"#define {prefix}_{constant}_DISPLAY_HEIGHT {display_height:.4f}f")
                res_name = ""
                if render_asset:
                    res_name = f"{prefix}_{constant}.raw".lower()
                    lines.append(f'#define {prefix}_{constant}_RES "{res_name}"')
                row = {
                    "screen_id": screen.id,
                    "screen_prefix": prefix,
                    "constant": constant,
                    "id": node_id,
                    "name": node_name,
                    "type": node_type,
                    "asset": render_asset,
                    "background_bitmap": background_bitmap,
                    "background_bitmap_mode": background_bitmap_mode,
                    "res": res_name,
                    "x": px,
                    "y": py,
                    "rotation": rotation,
                    "scale_x": sx,
                    "scale_y": sy,
                    "width": display_width,
                    "height": display_height,
                    "z_index": z_index,
                    "visible": 1 if visible == "1" else 0,
                }
                component_rows.append(row)
                self.last_component_rows.append(row)
                lines.append(f"#define {prefix}_{constant}_RESIZABLE {1 if bool(node.get('resizable', True)) else 0}")
                lines.append(f"#define {prefix}_{constant}_LOCK_ASPECT {1 if bool(node.get('lock_aspect', False)) else 0}")
                lines.append(f"#define {prefix}_{constant}_OPACITY {opacity:.4f}f")
                lines.append(f"#define {prefix}_{constant}_Z_INDEX {z_index}")
                lines.append(f"#define {prefix}_{constant}_VISIBLE {visible}")
                lines.append(f'#define {prefix}_{constant}_TYPE "{node_type}"')
                lines.append(f'#define {prefix}_{constant}_ASSET "{asset}"')
                lines.append(f'#define {prefix}_{constant}_BACKGROUND_BITMAP "{background_bitmap}"')
                lines.append(f'#define {prefix}_{constant}_BACKGROUND_BITMAP_MODE "{background_bitmap_mode}"')
                lines.append(f'#define {prefix}_{constant}_BLEND_MODE "{blend}"')
                lines.append(f'#define {prefix}_{constant}_TINT "{tint}"')
                layout_box = node.get("layout") if isinstance(node.get("layout"), dict) else {}
                shape_style = node.get("shape") if isinstance(node.get("shape"), dict) else {}
                text_style = node.get("text") if isinstance(node.get("text"), dict) else {}
                padding = int(number([layout_box.get("padding", 0)], 0, 0))
                margin = int(number([layout_box.get("margin", 0)], 0, 0))
                corner_radius = number([shape_style.get("corner_radius", 0)], 0, 0)
                font_name = str(text_style.get("font", "Segoe UI")).replace('"', '\\"')
                text_color = str(text_style.get("color", "#f4f7ff")).replace('"', '\\"')
                text_content = str(text_style.get("content", "")).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                lines.append(f"#define {prefix}_{constant}_PADDING {padding}")
                lines.append(f"#define {prefix}_{constant}_MARGIN {margin}")
                lines.append(f"#define {prefix}_{constant}_CORNER_RADIUS {corner_radius:.4f}f")
                lines.append(f'#define {prefix}_{constant}_TEXT "{text_content}"')
                lines.append(f'#define {prefix}_{constant}_FONT "{font_name}"')
                lines.append(f"#define {prefix}_{constant}_FONT_SIZE {int(number([text_style.get('font_size', 24)], 0, 24))}")
                lines.append(f'#define {prefix}_{constant}_TEXT_COLOR "{text_color}"')
                lines.append(f"#define {prefix}_{constant}_FONT_BOLD {1 if bool(text_style.get('bold', False)) else 0}")
                lines.append(f"#define {prefix}_{constant}_FONT_ITALIC {1 if bool(text_style.get('italic', False)) else 0}")
                lines.append(f"#define {prefix}_{constant}_FONT_UNDERLINE {1 if bool(text_style.get('underline', False)) else 0}")
                lines.append(f"#define {prefix}_{constant}_FONT_STRIKEOUT {1 if bool(text_style.get('strikeout', False)) else 0}")
                motion = node.get("motion") if isinstance(node.get("motion"), dict) else {}
                motion_type = str(motion.get("type", "")).replace('"', '\\"')
                lines.append(f'#define {prefix}_{constant}_MOTION_TYPE "{motion_type}"')
                if motion:
                    motion_json = json.dumps(
                        motion, ensure_ascii=False, separators=(",", ":")
                    ).replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'#define {prefix}_{constant}_MOTION_JSON "{motion_json}"')
                ui_role = str(node.get("ui_role", "")).replace('"', '\\"')
                input_binding = str(node.get("input_binding", "")).replace('"', '\\"')
                component_category = str(node.get("component_category", "sprite")).replace('"', '\\"')
                lines.append(f'#define {prefix}_{constant}_UI_ROLE "{ui_role}"')
                lines.append(f'#define {prefix}_{constant}_INPUT_BINDING "{input_binding}"')
                lines.append(f'#define {prefix}_{constant}_COMPONENT_CATEGORY "{component_category}"')
                automation = node.get("automation") if isinstance(node.get("automation"), dict) else {}
                automation_json = json.dumps(automation, ensure_ascii=False, separators=(",", ":")).replace("\\", "\\\\").replace('"', '\\"')
                automation_role = str(automation.get("role", "")).replace('"', '\\"')
                automation_physics = str(automation.get("physics", "none")).replace('"', '\\"')
                automation_shape = str(automation.get("collision_shape", "bounds")).replace('"', '\\"')
                collision_enabled = 1 if bool(automation.get("collision_enabled", automation_shape != "none")) else 0
                automation_channel = str(automation.get("event_channel", "")).replace('"', '\\"')
                automation_target = str(automation.get("target_screen", "")).replace('"', '\\"')
                tags = automation.get("tags") if isinstance(automation.get("tags"), list) else []
                tags_json = json.dumps(tags, ensure_ascii=False, separators=(",", ":")).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'#define {prefix}_{constant}_AUTOMATION_ROLE "{automation_role}"')
                lines.append(f'#define {prefix}_{constant}_AUTOMATION_PHYSICS "{automation_physics}"')
                lines.append(f'#define {prefix}_{constant}_COLLISION_SHAPE "{automation_shape}"')
                lines.append(f"#define {prefix}_{constant}_COLLISION_ENABLED {collision_enabled}")
                lines.append(f'#define {prefix}_{constant}_EVENT_CHANNEL "{automation_channel}"')
                lines.append(f'#define {prefix}_{constant}_TARGET_SCREEN "{automation_target}"')
                lines.append(f"#define {prefix}_{constant}_DEAD_ZONE {number([automation.get('dead_zone', 0.18)], 0, 0.18):.4f}f")
                lines.append(f"#define {prefix}_{constant}_SENSITIVITY {number([automation.get('sensitivity', 1.0)], 0, 1.0):.4f}f")
                lines.append(f'#define {prefix}_{constant}_AUTOMATION_TAGS_JSON "{tags_json}"')
                lines.append(f'#define {prefix}_{constant}_AUTOMATION_JSON "{automation_json}"')
                events = node.get("events") if isinstance(node.get("events"), list) else []
                events_json = json.dumps(events, ensure_ascii=False, separators=(",", ":")).replace("\\", "\\\\").replace('"', '\\"')
                clipping = node.get("clipping_mask") if isinstance(node.get("clipping_mask"), dict) else {}
                clipping_json = json.dumps(clipping, ensure_ascii=False, separators=(",", ":")).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f"#define {prefix}_{constant}_EVENT_COUNT {len(events)}")
                lines.append(f'#define {prefix}_{constant}_EVENTS_JSON "{events_json}"')
                lines.append(f'#define {prefix}_{constant}_CLIPPING_MASK_JSON "{clipping_json}"')
                anchor = node.get("anchor") if isinstance(node.get("anchor"), dict) else {}
                anchor_x = number([anchor.get("x", 0)], 0, 0)
                anchor_y = number([anchor.get("y", 0)], 0, 0)
                anchor_mode = str(anchor.get("mode", "Center")).replace('"', '\\"')
                lines.append(f'#define {prefix}_{constant}_ANCHOR_MODE "{anchor_mode}"')
                lines.append(f"#define {prefix}_{constant}_ANCHOR_X {anchor_x:.4f}f")
                lines.append(f"#define {prefix}_{constant}_ANCHOR_Y {anchor_y:.4f}f")
                lines.append(f"#define {prefix}_{constant}_PIXEL_SNAP {1 if bool(node.get('pixel_snap', True)) else 0}")
                lines.append(f"#define {prefix}_{constant}_LOCK_ASPECT {1 if bool(node.get('lock_aspect', False)) else 0}")
                keyframes = node.get("animation_keyframes") if isinstance(node.get("animation_keyframes"), list) else []
                lines.append(f"#define {prefix}_{constant}_KEYFRAME_COUNT {len(keyframes)}")
                if keyframes:
                    keyframe_json = json.dumps(keyframes, ensure_ascii=False, separators=(",", ":")).replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'#define {prefix}_{constant}_KEYFRAMES_JSON "{keyframe_json}"')
                if input_binding:
                    input_bindings.append((input_binding, node_id))
                if automation_role:
                    role_bindings.append((automation_role, node_id))
            if component_rows:
                ordered_rows = sorted(component_rows, key=lambda item: item["z_index"])
                lines.append(
                    f"static const VxpDesignComponent {prefix}_DESIGN_COMPONENTS[{len(ordered_rows)}] = {{"
                )
                table_entries = [
                    '    {{"{id}", "{type}", "{asset}", "{res}", '
                    "{x:.4f}f, {y:.4f}f, {rotation:.4f}f, "
                    "{sx:.4f}f, {sy:.4f}f, "
                    "{w:.4f}f, {h:.4f}f, "
                    "{z}, {visible}}} /* z_index: {z} */".format(
                        id=row["id"].replace('"', '\\"'),
                        type=row["type"],
                        asset=row["asset"],
                        res=row["res"],
                        x=row["x"],
                        y=row["y"],
                        rotation=row["rotation"],
                        sx=row["scale_x"],
                        sy=row["scale_y"],
                        w=row["width"],
                        h=row["height"],
                        z=row["z_index"],
                        visible=row["visible"],
                    )
                    for row in ordered_rows
                ]
                lines.append(",\n".join(table_entries))
                lines.append("};")
            else:
                lines.append(f"#define {prefix}_DESIGN_COMPONENTS ((const VxpDesignComponent*)0)")
            if screen.id == active_id:
                active_prefix = prefix
            if input_bindings:
                lines.append("")
                used_actions: set[str] = set()
                for action_name, target_id in input_bindings:
                    action_constant = c_constant(action_name, "ACTION")
                    base_action = action_constant
                    action_index = 2
                    while action_constant in used_actions:
                        action_constant = f"{base_action}_{action_index}"
                        action_index += 1
                    used_actions.add(action_constant)
                    lines.append(f'#define {prefix}_CTRL_{action_constant} "{target_id}"')
            if role_bindings:
                lines.append("")
                used_roles: set[str] = set()
                for role_name, target_id in role_bindings:
                    role_constant = c_constant(role_name, "ROLE")
                    base_role = role_constant
                    role_index = 2
                    while role_constant in used_roles:
                        role_constant = f"{base_role}_{role_index}"
                        role_index += 1
                    used_roles.add(role_constant)
                    lines.append(f'#define {prefix}_ROLE_{role_constant} "{target_id}"')
            groups = scene.get("groups") if isinstance(scene.get("groups"), list) else []
            if groups:
                lines.append("")
                for group in groups:
                    if not isinstance(group, dict):
                        continue
                    constant = c_constant(f"GROUP_{group.get('name', 'Group')}", "GROUP")
                    base = constant
                    index = 2
                    while constant in used_constants:
                        constant = f"{base}_{index}"
                        index += 1
                    used_constants.add(constant)
                    lines.append(f'#define {prefix}_{constant} "{group.get("id", "")}"')
            lines.append("")
        if active_prefix is not None:
            lines.append("/* Màn đang mở trong Camera 2D (active screen) */")
            lines.append(f"#define VXP_DESIGN_ACTIVE_COMPONENTS {active_prefix}_DESIGN_COMPONENTS")
            lines.append(f"#define VXP_DESIGN_ACTIVE_COUNT {active_prefix}_COMPONENT_COUNT")
            lines.append(f"#define VXP_DESIGN_ACTIVE_HAS_DESIGN {active_prefix}_HAS_DESIGN")
            lines.append("")
        lines.append("#endif /* VXP_SCENE_BINDINGS_H */")
        content = "\n".join(lines).rstrip() + "\n"
        output = self.root / "src" / "scene_bindings.h"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        return output
