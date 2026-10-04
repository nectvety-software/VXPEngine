"""Offline documentation for the current VXPEngine ARM/VXP toolchain."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from project_store import COREMRE_VERSION, ENGINE_VERSION


@dataclass(frozen=True, slots=True)
class DocumentationTopic:
    key: str
    title: str
    icon_name: str
    category: str
    summary: str
    keywords: tuple[str, ...]
    html: str


def _code(value: str, language: str = "text") -> str:
    return f'<div class="code-head">{escape(language)}</div><pre><code>{escape(value.strip())}</code></pre>'


def _topic(key: str, title: str, icon: str, category: str, summary: str,
           keywords: tuple[str, ...], body: str) -> DocumentationTopic:
    return DocumentationTopic(key, title, icon, category, summary, keywords, f"""
    <section><div class="eyebrow">{escape(category)}</div><h1>{escape(title)}</h1>
    <p class="lead">{escape(summary)}</p>{body}</section>""")


def build_topics() -> list[DocumentationTopic]:
    return [
        _topic("overview", "Tổng quan VXPEngine", "fa5s.compass", "Bắt đầu",
               "IDE và SDK C/C++17 cho game/app S30+ MRE VXP 240×320 hoặc 320×240.",
               ("overview", "mre", "vxp", "coremre", "s30+"), f"""
               <div class="callout">VXPEngine {ENGINE_VERSION} • coremre {COREMRE_VERSION}</div>
               <ul><li>Build host bằng w64devkit.</li><li>Build thiết bị bằng ARM GCC.</li>
               <li>Runtime giả lập duy nhất: VXPEmu.</li></ul>"""),
        _topic("setup", "Cài đặt và kiểm tra", "fa5s.tools", "SDK",
               "Một lệnh chạy IDE và kiểm tra toàn bộ toolchain.",
               ("setup", "w64devkit", "arm gcc", "run_windows", "sdk"),
               _code("run_windows.bat\nrun_windows.bat check\nrun_windows.bat deps", "bat") +
               "<p>SDK tự dò w64devkit, ARM GCC, MRE API và VXPEmu.</p>"),
        _topic("build", "Build và chạy VXP", "fa5s.hammer", "Build",
               "Compile ARM, đóng gói `.vxp` và mở bằng VXPEmu.",
               ("build", "arm", "resource", "vxpemu"),
               _code("scripts\\build_arm.bat\nscripts\\run_vxpemu.bat", "bat")),
        _topic("core", "coremre 2.0", "fa5s.cubes", "Engine",
               "Core static C++17 tối ưu cho runtime MRE event-driven.",
               ("coremre", "physics", "ui", "game", "c++17"), """
               <p>Target chuẩn là <code>VXPEngine::coremre</code>. Core cung cấp scene,
               gameplay state/event, camera, UI, touch và physics; không đưa backend
               desktop/hardware không liên quan vào target MRE.</p>"""),
    ]


DOCUMENT_STYLE = """
body{background:#121722;color:#cbd5e1;font-family:'Segoe UI',sans-serif;font-size:14px;margin:0;padding:12px 26px 40px}h1{color:#f3f6fb;font-size:28px}p,li{line-height:1.55}code{color:#c6ddff;font-family:Consolas,monospace}pre{background:#0d131d;border:1px solid #29364a;border-radius:0 0 8px 8px;padding:13px;white-space:pre-wrap}.code-head{background:#192334;border:1px solid #29364a;padding:6px 10px}.eyebrow{color:#6f9fe9;font-size:11px;font-weight:700;text-transform:uppercase}.lead{color:#91a0b6;font-size:16px}.callout{background:#162941;border:1px solid #28588e;border-radius:8px;padding:12px}.warning{background:#302619;border:1px solid #66502a;border-radius:8px;padding:12px;color:#f2d49a}
"""


def render_topic_page(topic: DocumentationTopic) -> str:
    return f"<html><head><style>{DOCUMENT_STYLE}</style></head><body>{topic.html}</body></html>"


def export_markdown() -> str:
    lines = [f"# VXPEngine {ENGINE_VERSION}", "", f"Core: coremre {COREMRE_VERSION}", ""]
    for index, topic in enumerate(build_topics(), 1):
        lines.extend((f"## {index}. {topic.title}", "", topic.summary, ""))
    lines.extend(("## Lệnh nhanh", "", "```bat", "run_windows.bat check",
                  "<project>\\scripts\\build_arm.bat", "<project>\\scripts\\run_vxpemu.bat", "```", ""))
    return "\n".join(lines)
