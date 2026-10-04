"""Small, dependency-free UI language registry for the VXPEngine shell."""
from __future__ import annotations

from PySide6.QtCore import QLocale


LANGUAGES = (
    ("system", "Theo hệ thống / System"),
    ("vi", "Tiếng Việt"),
    ("en", "English"),
    ("zh", "中文"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("fr", "Français"),
    ("es", "Español"),
    ("de", "Deutsch"),
)

_SUPPORTED = {code for code, _label in LANGUAGES if code != "system"}

_TEXT = {
    "vi": {
        "menu.file": "Tệp", "menu.edit": "Sửa", "menu.view": "Hiển thị",
        "menu.project": "Dự án", "menu.scene": "Cảnh", "menu.run": "Chạy",
        "menu.tools": "Công cụ", "menu.settings": "Cài đặt", "menu.help": "Trợ giúp",
        "language": "Ngôn ngữ", "tips": "Mẹo UI Design / Component Library",
        "language.changed": "Đã đổi ngôn ngữ giao diện. Một số nội dung chuyên sâu sẽ được cập nhật dần.",
    },
    "en": {
        "menu.file": "File", "menu.edit": "Edit", "menu.view": "View",
        "menu.project": "Project", "menu.scene": "Scene", "menu.run": "Run",
        "menu.tools": "Tools", "menu.settings": "Settings", "menu.help": "Help",
        "language": "Language", "tips": "UI Design / Component Library Tips",
        "language.changed": "The interface language was changed. Some specialist text remains bilingual.",
    },
    "zh": {
        "menu.file": "文件", "menu.edit": "编辑", "menu.view": "视图",
        "menu.project": "项目", "menu.scene": "场景", "menu.run": "运行",
        "menu.tools": "工具", "menu.settings": "设置", "menu.help": "帮助",
        "language": "语言", "tips": "UI 设计 / 组件库提示", "language.changed": "界面语言已更改。",
    },
    "ja": {
        "menu.file": "ファイル", "menu.edit": "編集", "menu.view": "表示",
        "menu.project": "プロジェクト", "menu.scene": "シーン", "menu.run": "実行",
        "menu.tools": "ツール", "menu.settings": "設定", "menu.help": "ヘルプ",
        "language": "言語", "tips": "UIデザイン / コンポーネントのヒント", "language.changed": "表示言語を変更しました。",
    },
    "ko": {"language": "언어", "tips": "UI 디자인 / 구성 요소 도움말"},
    "fr": {"language": "Langue", "tips": "Astuces UI Design / composants"},
    "es": {"language": "Idioma", "tips": "Consejos de diseño UI / componentes"},
    "de": {"language": "Sprache", "tips": "Tipps für UI-Design / Komponenten"},
}


def resolve_language(choice: str | None) -> str:
    """Resolve ``system`` to a supported ISO-639 language, falling back to English."""
    value = str(choice or "system").lower().replace("-", "_")
    if value == "system":
        value = QLocale.system().name().split("_", 1)[0].lower()
    return value if value in _SUPPORTED else "en"


def text(key: str, choice: str | None = "system") -> str:
    language = resolve_language(choice)
    return _TEXT.get(language, {}).get(key, _TEXT["en"].get(key, key))
